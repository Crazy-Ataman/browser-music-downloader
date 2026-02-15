import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import app_logging
import yt_dlp
from yt_dlp.utils import DownloadError

from app_logging import FatalForbiddenError, FragmentLogger
from config import QualityProfile, RuntimeSettings

from .metadata import clean_tags, sanitize_text


def is_ffmpeg_installed() -> bool:
    """Checks if FFmpeg is available in the system PATH."""
    import shutil
    return shutil.which("ffmpeg") is not None


def is_deno_installed() -> bool:
    """Checks if Deno JavaScript runtime is available in the system PATH."""
    import shutil
    return shutil.which("deno") is not None


def get_deno_path() -> Optional[str]:
    """Returns the path to Deno if available, None otherwise."""
    import shutil
    deno_path = shutil.which("deno")
    if deno_path:
        return deno_path
    user_home = Path.home()
    deno_bin = user_home / ".deno" / "bin" / "deno.exe"
    if deno_bin.exists():
        return str(deno_bin)
    return None


def show_progress(d: Dict[str, Any]) -> None:
    """
    Custom hook to show a single-line progress bar.
    Prevents the terminal from scrolling/stacking endlessly.
    """
    if d["status"] == "downloading":
        p = d.get("_percent_str", "0%").replace("%", "")
        speed = d.get("_speed_str", "N/A")
        eta = d.get("_eta_str", "N/A")
        filename = d.get("filename", "").split(os.sep)[-1]
        if len(filename) > 30:
            filename = filename[:27] + "..."
        try:
            percent = float(p)
            bar_length = 20
            filled_length = int(bar_length * percent // 100)
            bar = "█" * filled_length + "-" * (bar_length - filled_length)
        except ValueError:
            bar = "-" * 20
            p = "??"
        sys.stdout.write(
            f"\r[DOWNLOADING] |{bar}| {p}% | {speed} | ETA: {eta} | {filename}    "
        )
        sys.stdout.flush()
    elif d["status"] == "finished":
        sys.stdout.write(
            "\r[COMPLETE]    |" + "█" * 20 + "| 100% | Downloaded! Processing...                     "
        )
        sys.stdout.flush()


def download_audio(
    urls: List[str],
    group_name: str,
    quality_settings: QualityProfile,
    settings: RuntimeSettings,
    download_base: Path,
) -> Dict[str, int]:
    """
    Orchestrates the download process using yt-dlp.
    Handles filename generation, conversions, and metadata post-processing.
    """
    app_logging.log.info(
        "Starting download for group '%s' with %d URL(s). Quality: %s (convert=%s, codec=%s)",
        group_name,
        len(urls),
        quality_settings.name,
        quality_settings.convert,
        quality_settings.codec,
    )

    safe_name = "".join(
        [c for c in group_name if c.isalpha() or c.isdigit() or c == " "]
    ).strip()
    download_path = download_base / safe_name
    download_path.mkdir(parents=True, exist_ok=True)

    files_before = set(download_path.glob("*"))
    frag_logger = FragmentLogger()
    has_ffmpeg = is_ffmpeg_installed()
    browser_strategies = [None, "firefox", "chrome"]
    player_client_configs = [
        ["tv", "web"],
        ["web"],
        ["ios"],
    ]

    success = False
    downloaded_files: List[Path] = []
    remaining_urls = urls.copy()

    for current_browser in browser_strategies:
        if not remaining_urls:
            break
        if success:
            break

        browser_name = current_browser if current_browser else "Anonymous (No Cookies)"
        print("\n" + "=" * 50)
        app_logging.log.info("[ATTEMPT] Trying download via: %s", browser_name.upper())
        print("=" * 50)

        use_cookies = bool(current_browser)
        player_client_idx = 0
        succeeded_in_this_pass: List[str] = []

        try:
            while player_client_idx < len(player_client_configs) if use_cookies else 1:
                frag_logger.signature_solving_failed = False
                frag_logger.only_images_available = False

                if use_cookies:
                    player_clients = player_client_configs[player_client_idx]
                else:
                    player_clients = ["default", "-web_safari"]

                ydl_opts = {
                    "outtmpl": str(download_path / "%(title)s.%(ext)s"),
                    "restrictfilenames": False,
                    "windowsfilenames": True,
                    "overwrites": True,
                    "force_overwrites": True,
                    "verbose": False,
                    "quiet": False,
                    "logger": frag_logger,
                    "progress_hooks": [show_progress],
                    "socket_timeout": 30,
                    "retries": 15,
                    "fragment_retries": 15,
                    "keepfragments": False,
                    "skip_unavailable_fragments": settings.allow_skip_fragments,
                    "writethumbnail": False,
                    "noplaylist": True,
                    "extractor_args": {
                        "youtube": {"player_client": player_clients}
                    },
                    "parse_metadata": [
                        ":(?P<meta_synopsis>)",
                        ":(?P<meta_description>)",
                        ":(?P<meta_comment>)",
                        ":(?P<meta_purl>)",
                        ":(?P<meta_encoder>)",
                        ":(?P<meta_copyright>)",
                    ],
                    "postprocessors": [],
                    "postprocessor_args": {},
                }

                deno_path = get_deno_path()
                if deno_path and not is_deno_installed():
                    ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}}
                    app_logging.log.debug(
                        "Using Deno for signature solving (custom path): %s", deno_path
                    )
                elif is_deno_installed():
                    app_logging.log.debug(
                        "Using Deno for signature solving (auto-detected from PATH)"
                    )
                else:
                    app_logging.log.debug(
                        "Deno not found - signature solving may fail"
                    )

                if current_browser:
                    ydl_opts["cookiesfrombrowser"] = (current_browser,)
                else:
                    ydl_opts.pop("cookiesfrombrowser", None)

                if has_ffmpeg:
                    ydl_opts["writethumbnail"] = True
                    ydl_opts["postprocessor_args"] = {
                        "FFmpegExtractAudio": ["-bitexact", "-map_metadata", "-1"],
                        "FFmpegMetadata": ["-id3v2_version", "3", "-write_id3v1", "0"],
                        "EmbedThumbnail": ["-map_metadata", "-1"],
                    }
                    ydl_opts["postprocessors"] = [
                        {"key": "SponsorBlock"},
                        {
                            "key": "ModifyChapters",
                            "remove_sponsor_segments": [
                                "sponsor",
                                "intro",
                                "outro",
                                "selfpromo",
                                "interaction",
                                "music_offtopic",
                            ],
                        },
                        {"key": "EmbedThumbnail"},
                        {"key": "FFmpegMetadata", "add_metadata": True},
                    ]
                    if quality_settings.convert:
                        if use_cookies:
                            ydl_opts["format"] = (
                                "bestaudio/bestvideo+bestaudio/"
                                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
                            )
                        else:
                            ydl_opts["format"] = "bestaudio/bestvideo+bestaudio/best"
                        ydl_opts["postprocessors"].insert(
                            0,
                            {
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": quality_settings.codec,
                                "preferredquality": "0",
                            },
                        )
                    else:
                        if use_cookies:
                            ydl_opts["format"] = (
                                "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
                            )
                        else:
                            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
                else:
                    app_logging.log.info("FFmpeg not detected. Downloading raw audio only.")
                    ydl_opts["format"] = (
                        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best"
                        if use_cookies
                        else "bestaudio[ext=m4a]/bestaudio/best"
                    )

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        for url in remaining_urls:
                            if url in succeeded_in_this_pass:
                                continue
                            try:
                                try:
                                    info = ydl.extract_info(url, download=False)
                                    formats = info.get("formats", [])
                                    has_real_formats = False
                                    for fmt in formats:
                                        acodec = fmt.get("acodec", "none")
                                        vcodec = fmt.get("vcodec", "none")
                                        fmt_id = fmt.get("format_id", "")
                                        if fmt_id.startswith("sb"):
                                            continue
                                        if acodec != "none" or vcodec != "none":
                                            has_real_formats = True
                                            break
                                    if not has_real_formats and formats:
                                        if frag_logger.signature_solving_failed or frag_logger.only_images_available:
                                            if use_cookies and player_client_idx < len(player_client_configs) - 1:
                                                app_logging.log.info(
                                                    "No formats available with player_client %s, trying next configuration...",
                                                    player_clients,
                                                )
                                                raise FatalForbiddenError(
                                                    "No Formats Available (Signature Solving Failed - Try Next Config)"
                                                )
                                            raise FatalForbiddenError(
                                                "No Formats Available (Signature Solving Failed)"
                                            )
                                        raise FatalForbiddenError(
                                            "No Formats Available (Video Restricted)"
                                        )
                                except FatalForbiddenError:
                                    raise
                                except Exception as e:
                                    app_logging.log.debug(
                                        "Info extraction failed, trying download: %s", e
                                    )

                                info = ydl.extract_info(url, download=True)
                                filename = ydl.prepare_filename(info)
                                final_path = Path(filename)
                                if quality_settings.convert:
                                    final_path = final_path.with_suffix(
                                        f".{quality_settings.codec}"
                                    )
                                succeeded_in_this_pass.append(url)
                                downloaded_files.append(final_path)
                                app_logging.log.info(
                                    "[SUCCESS] Downloaded '%s' via %s (player_client: %s)",
                                    final_path.name,
                                    browser_name.upper(),
                                    player_clients,
                                )
                            except DownloadError as e:
                                err_msg = str(e)
                                if "403" in err_msg or "Forbidden" in err_msg:
                                    raise FatalForbiddenError("403 Forbidden (IP Block)")
                                if "Requested format is not available" in err_msg:
                                    if frag_logger.signature_solving_failed or frag_logger.only_images_available:
                                        if use_cookies and player_client_idx < len(player_client_configs) - 1:
                                            app_logging.log.info(
                                                "Format unavailable with player_client %s, trying next configuration...",
                                                player_clients,
                                            )
                                            raise FatalForbiddenError(
                                                "Format Unavailable (Signature Solving Failed - Try Next Config)"
                                            )
                                        raise FatalForbiddenError(
                                            "Format Unavailable (Signature Solving Failed)"
                                        )
                                    raise FatalForbiddenError(
                                        "Format Unavailable (Cookie Soft Ban)"
                                    )
                                if "Failed to decrypt" in err_msg or "database is locked" in err_msg:
                                    raise FatalForbiddenError(
                                        "Cookie Access Failed (Browser Open/Encrypted)"
                                    )
                                app_logging.log.error("Download failed for %s: %s", url, e)
                            except PermissionError as e:
                                app_logging.log.error(
                                    "Windows locked the file (Antivirus/FFmpeg race condition) for URL %s: %s",
                                    url,
                                    e,
                                )
                                print(f"\n[ERROR] File locked by Windows. Skipping: {url}")
                            except FatalForbiddenError:
                                raise
                            except Exception as e:
                                app_logging.log.error(
                                    "Failed to process %s: %s", url, e, exc_info=True
                                )
                                print(f"\n[ERROR] Skipped due to error: {e}")

                    if succeeded_in_this_pass:
                        success = True
                        break
                    if use_cookies and player_client_idx < len(player_client_configs) - 1:
                        app_logging.log.info(
                            "No files downloaded with player_client %s, trying next configuration...",
                            player_clients,
                        )
                        player_client_idx += 1
                        continue
                    break

                except FatalForbiddenError as e:
                    err_str = str(e)
                    if (
                        "Signature Solving Failed" in err_str or "No Formats Available" in err_str
                    ) and use_cookies and player_client_idx < len(player_client_configs) - 1:
                        if "Try Next Config" in err_str:
                            player_client_idx += 1
                            continue
                        app_logging.log.info(
                            "Signature solving failed with player_client %s, trying next configuration...",
                            player_clients,
                        )
                        player_client_idx += 1
                        continue
                    raise
                except Exception as e:
                    app_logging.log.error(
                        "Unexpected error during download loop: %s", e, exc_info=True
                    )
                    if use_cookies and player_client_idx < len(player_client_configs) - 1:
                        player_client_idx += 1
                        continue
                    break

        except FatalForbiddenError as e:
            err_str = str(e)
            app_logging.log.warning(
                "\n[WARN] Strategy '%s' failed: %s", browser_name, err_str
            )
            app_logging.log.info("[INFO] Switching to next browser strategy...")
            print(f"\n[WARN] Strategy '{browser_name}' failed: {e}")
            print("[INFO] Switching to next browser strategy...")
            if current_browser == "chrome" and "Cookie Access Failed" in err_str:
                hint = (
                    "Tip: Close Chrome completely, then try again. "
                    "Or use Firefox instead. "
                    "See https://github.com/yt-dlp/yt-dlp/issues/10927"
                )
                print(hint)
                app_logging.log.info("[HINT] %s", hint)
            elif "Signature Solving Failed" in err_str or "No Formats Available" in err_str:
                hint = (
                    "Tip: YouTube signature solving failed. "
                    "Install Node.js for better compatibility, or update yt-dlp: pip install -U yt-dlp"
                )
                print(hint)
                app_logging.log.info("[HINT] %s", hint)
            elif "Format Unavailable" in err_str:
                hint = "Tip: Update yt-dlp: pip install -U yt-dlp"
                print(hint)
                app_logging.log.info("[HINT] %s", hint)
        except Exception as e:
            app_logging.log.error(
                "Unexpected error during download loop: %s", e, exc_info=True
            )
            break

        for url in succeeded_in_this_pass:
            if url in remaining_urls:
                remaining_urls.remove(url)

    if not success:
        app_logging.log.warning(
            "All browser strategies failed to download the content."
        )
        app_logging.log.info("Please check your internet or try updating yt-dlp.")

    if has_ffmpeg and downloaded_files:
        print("\n" + "=" * 50)
        app_logging.log.info("[POST-PROCESSING] Cleaning tags and renaming files...")
        print("=" * 50)
        total = len(downloaded_files)
        for i, file_path in enumerate(downloaded_files):
            if not file_path.exists():
                continue
            app_logging.log.info(
                "[PROCESSING] Item %d/%d: %s...    ",
                i + 1,
                total,
                file_path.name,
            )
            sys.stdout.flush()
            original_stem = file_path.stem
            clean_stem = sanitize_text(original_stem)
            if clean_stem != original_stem:
                new_filename = f"{clean_stem}{file_path.suffix}"
                new_path = file_path.parent / new_filename
                try:
                    if new_path.exists():
                        new_path = file_path.parent / f"{clean_stem}_{i}{file_path.suffix}"
                    os.rename(file_path, new_path)
                    file_path = new_path
                except OSError as e:
                    app_logging.log.error("Could not rename %s: %s", file_path.name, e)
                    print(f"[RENAME ERROR] Could not rename {file_path.name}: {e}")
            clean_tags(file_path)

    files_after = set(download_path.glob("*"))
    new_files_count = len(files_after - files_before)

    return {
        "new_files": new_files_count,
        "skipped_fragments": frag_logger.skipped,
        "warnings": frag_logger.warnings,
    }
