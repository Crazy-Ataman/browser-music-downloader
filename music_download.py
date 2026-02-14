import os
import sys
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional
import yt_dlp
from yt_dlp.utils import DownloadError
from mutagen.id3 import ID3, TYER, TIT2
import app_logging
import config
from app_logging import FatalForbiddenError, FragmentLogger, init as init_logging
from browsers import ChromeBrowser, FirefoxBrowser


def clear_screen() -> None:
    """Clears terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def is_ffmpeg_installed() -> bool:
    """Checks if FFmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def is_deno_installed() -> bool:
    """Checks if Deno JavaScript runtime is available in the system PATH."""
    return shutil.which("deno") is not None


def get_deno_path() -> Optional[str]:
    """Returns the path to Deno if available, None otherwise."""
    deno_path = shutil.which("deno")
    if deno_path:
        return deno_path
    # Check common installation locations
    user_home = Path.home()
    deno_bin = user_home / ".deno" / "bin" / "deno.exe"
    if deno_bin.exists():
        return str(deno_bin)
    return None


def sanitize_text(text: str) -> str:
    """Removes common YouTube junk text from titles/filenames."""
    if not text:
        return ""

    clean_text = text
    for pattern in config.CLEANUP_PATTERNS:
        clean_text = re.sub(pattern, "", clean_text)

    # Remove trailing separators often left behind (e.g., "Song - " -> "Song")
    clean_text = re.sub(r"\s*[-|]\s*$", "", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if ".." in clean_text:
        clean_text = clean_text.replace("..", ".")

    return clean_text


def show_progress(d):
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

        # Create a visual bar [======    ]
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
            f"\r[COMPLETE]    |{'█' * 20}| 100% | Downloaded! Processing...                     "
        )
        sys.stdout.flush()


def ask_quality() -> Optional[config.QualityProfile]:
    """CLI Menu for selecting audio quality."""
    ffmpeg_available = is_ffmpeg_installed()
    app_logging.log.info(
        "Opening quality selection menu (FFmpeg available: %s)",
        ffmpeg_available,
    )
    while True:
        print("\n--- Audio Quality Settings ---")
        for key, val in config.QUALITY_OPTIONS.items():
            if not ffmpeg_available and val.convert:
                print(f"[{key}] [UNAVAILABLE - Needs FFmpeg] {val.name}")
            else:
                print(f"[{key}] {val.name} - {val.desc}")

        skip_status = (
            "ENABLED (Audio may glitch)"
            if config.ALLOW_SKIP_FRAGMENTS[0]
            else "DISABLED (Stops on error)"
        )
        print(f"\n[S] Skip Missing Blocks: {skip_status}")

        choice = input("\nSelect Quality (or 'q' to quit, 'b' back): ").strip().lower()

        if choice == "q":
            sys.exit()
        if choice == "b":
            return None

        if choice == "s":
            config.ALLOW_SKIP_FRAGMENTS[0] = not config.ALLOW_SKIP_FRAGMENTS[0]
            app_logging.log.info(
                "User toggled skip missing fragments to: %s",
                config.ALLOW_SKIP_FRAGMENTS[0],
            )
            print("Setting updated.")
            continue

        if choice in config.QUALITY_OPTIONS:
            selected = config.QUALITY_OPTIONS[choice]

            if selected.convert and not ffmpeg_available:
                app_logging.log.error(
                    "FFmpeg is missing! Cannot convert to %s.", selected.codec
                )
                print("\n[ERROR] FFmpeg is missing!")
                print("You cannot select MP3 conversion without FFmpeg installed.")
                print("Please install FFmpeg or select Option 3 (Original Audio).")
                input("Press Enter to continue...")
                continue

            return selected

        print("Invalid selection.")


def clean_tags(filepath: Path) -> None:
    """
    Metadata cleaning for MP3s using Mutagen.
    Removes proprietary ffmpeg tags (TSSE, TENC) and comments (TXXX).
    Standardizes Year (TYER), clean title and removes Track Numbers (TRCK).
    """
    if not filepath.exists():
        return

    if not filepath.suffix.lower() == ".mp3":
        return

    try:
        audio = ID3(filepath)
        found_year = None

        if "TDRC" in audio:
            found_year = str(audio["TDRC"].text[0])[:4]
        elif "TYER" in audio:
            found_year = str(audio["TYER"].text[0])[:4]

        search_text = ""
        for key in audio.keys():
            if key.startswith("TXXX:description") or key.startswith("COMM"):
                search_text += str(audio[key]) + "\n"

        if search_text:
            # Regex to find patterns like: ℗ 2008, (C) 2008, Released on 2008
            # Matches 19xx or 20xx
            # Purpose: Extract the original song release year instead of YouTube upload date
            pattern = r"(?:℗|©|\(c\)|released\s*on|published\s*on|provided\s*to\s*youtube)[^0-9]*((?:19|20)\d{2})"
            match = re.search(pattern, search_text, re.IGNORECASE)

            if match:
                real_year = match.group(1)
                # print(f"[METADATA] Found original release year: {real_year} (replacing {found_year})")
                found_year = real_year

        tags_to_remove = []

        # Delete track number (very often incorrect number)
        if "TRCK" in audio:
            del audio["TRCK"]

        if "TDRC" in audio:
            del audio["TDRC"]
        if "TDAT" in audio:
            del audio["TDAT"]

        blacklist_start = ("TSSE", "TENC", "COMM", "USLT", "TDAT")
        blacklist_txxx = [
            "description",
            "synopsis",
            "purl",
            "comment",
            "producers",
            "handler",
            "major_brand",
            "minor_version",
            "compatible_brands",
        ]

        for key in audio.keys():
            # Delete technical keys
            if key.startswith(blacklist_start):
                tags_to_remove.append(key)
                continue

            # Delete custom text frames (TXXX) containing junk
            if key.startswith("TXXX"):
                desc = audio[key].desc.lower()
                if any(b in desc for b in blacklist_txxx):
                    tags_to_remove.append(key)

        for tag in tags_to_remove:
            if tag in audio:
                del audio[tag]

        if found_year:
            audio.add(TYER(encoding=3, text=found_year))

        if "TIT2" in audio:
            original_title = str(audio["TIT2"].text[0])
            new_title = sanitize_text(original_title)
            if new_title != original_title:
                audio.add(TIT2(encoding=3, text=new_title))
                app_logging.log.info(
                    f"[METADATA] Renamed Title: '{original_title}' -> '{new_title}'"
                )

        # Save (Force ID3v2.3 for max Windows/Car compatibility)
        audio.save(v1=0, v2_version=3)
        app_logging.log.info(f"[CLEANER] Sanitized tags: {filepath.name}")

    except Exception as e:
        app_logging.log.error(f"[CLEANER] Failed on {filepath.name}: {e}")


def download_audio(
    urls: List[str], group_name: str, quality_settings: config.QualityProfile
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
    download_path = config.BASE_DIR / "downloads" / safe_name
    download_path.mkdir(parents=True, exist_ok=True)

    files_before = set(download_path.glob("*"))
    frag_logger = FragmentLogger()
    has_ffmpeg = is_ffmpeg_installed()
    browser_strategies = [None, "firefox", "chrome"]

    # Player client configurations to try as fallback when signature solving fails
    player_client_configs = [
        ["tv", "web"],  # Default for cookies
        ["web"],        # Simpler fallback
        ["ios"],        # Alternative client
    ]

    success = False
    downloaded_files = []
    remaining_urls = urls.copy()

    for current_browser in browser_strategies:
        if not remaining_urls:
            break
        if success:
            break

        browser_name = current_browser if current_browser else "Anonymous (No Cookies)"
        print(f"\n" + "=" * 50)
        app_logging.log.info(f"[ATTEMPT] Trying download via: {browser_name.upper()}")
        print("=" * 50)

        use_cookies = bool(current_browser)
        # Try different player_client configurations if signature solving fails
        player_client_idx = 0
        succeeded_in_this_pass = []

        try:
            while player_client_idx < len(player_client_configs) if use_cookies else 1:
                # Reset logger state for each attempt
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
                    "skip_unavailable_fragments": config.ALLOW_SKIP_FRAGMENTS[0],
                    "writethumbnail": False,
                    "noplaylist": True,
                    "extractor_args": {
                        "youtube": {
                            "player_client": player_clients
                        }
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

                # Enable Deno for JavaScript signature solving (recommended by yt-dlp)
                # Deno is enabled by default in yt-dlp, so we don't need to set it explicitly
                # Only set js_runtimes if Deno is not in PATH but we found it at a custom location
                deno_path = get_deno_path()
                if deno_path and not is_deno_installed():
                    # Deno found at custom location but not in PATH - specify path explicitly
                    # Format: {runtime_name: {config_dict}}
                    ydl_opts["js_runtimes"] = {"deno": {"path": deno_path}}
                    app_logging.log.debug(f"Using Deno for signature solving (custom path): {deno_path}")
                elif is_deno_installed():
                    # Deno is in PATH - yt-dlp will auto-detect it (enabled by default)
                    app_logging.log.debug("Using Deno for signature solving (auto-detected from PATH)")
                else:
                    # No Deno found - yt-dlp will try to use it if available, or fall back
                    app_logging.log.debug("Deno not found - signature solving may fail")

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
                                # First, try to get info without downloading to check formats
                                try:
                                    info = ydl.extract_info(url, download=False)
                                    formats = info.get('formats', [])

                                    # Check if we have actual audio/video formats (not just storyboards)
                                    has_real_formats = False
                                    for fmt in formats:
                                        acodec = fmt.get('acodec', 'none')
                                        vcodec = fmt.get('vcodec', 'none')
                                        fmt_id = fmt.get('format_id', '')
                                        # Skip storyboard formats
                                        if fmt_id.startswith('sb'):
                                            continue
                                        if acodec != 'none' or vcodec != 'none':
                                            has_real_formats = True
                                            break

                                    if not has_real_formats and formats:
                                        # Only storyboard images available
                                        if frag_logger.signature_solving_failed or frag_logger.only_images_available:
                                            # Try next player_client config if available
                                            if use_cookies and player_client_idx < len(player_client_configs) - 1:
                                                app_logging.log.info(
                                                    "No formats available with player_client %s, trying next configuration...",
                                                    player_clients
                                                )
                                                raise FatalForbiddenError(
                                                    "No Formats Available (Signature Solving Failed - Try Next Config)"
                                                )
                                            else:
                                                raise FatalForbiddenError(
                                                    "No Formats Available (Signature Solving Failed)"
                                                )
                                        else:
                                            raise FatalForbiddenError(
                                                "No Formats Available (Video Restricted)"
                                            )

                                except FatalForbiddenError:
                                    raise  # Re-raise format availability errors
                                except Exception as e:
                                    # If info extraction fails, try downloading anyway
                                    app_logging.log.debug(f"Info extraction failed, trying download: {e}")

                                # Now try actual download
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
                                    # Check if this is due to signature solving failure
                                    if frag_logger.signature_solving_failed or frag_logger.only_images_available:
                                        # Try next player_client config if available
                                        if use_cookies and player_client_idx < len(player_client_configs) - 1:
                                            app_logging.log.info(
                                                "Format unavailable with player_client %s, trying next configuration...",
                                                player_clients
                                            )
                                            # Raise exception to be caught by outer handler to try next config
                                            raise FatalForbiddenError(
                                                "Format Unavailable (Signature Solving Failed - Try Next Config)"
                                            )
                                        else:
                                            raise FatalForbiddenError(
                                                "Format Unavailable (Signature Solving Failed)"
                                            )
                                    else:
                                        raise FatalForbiddenError(
                                            "Format Unavailable (Cookie Soft Ban)"
                                        )

                                if (
                                    "Failed to decrypt" in err_msg
                                    or "database is locked" in err_msg
                                ):
                                    raise FatalForbiddenError(
                                        "Cookie Access Failed (Browser Open/Encrypted)"
                                    )

                                app_logging.log.error(f"Download failed for {url}: {e}")

                            except PermissionError as e:
                                app_logging.log.error(
                                    "Windows locked the file (Antivirus/FFmpeg race condition) for URL %s: %s",
                                    url,
                                    e,
                                )
                                print(f"\n[ERROR] File locked by Windows. Skipping: {url}")

                            except FatalForbiddenError:
                                raise  # Let outer handler switch browser strategy

                            except Exception as e:
                                app_logging.log.error(
                                    f"Failed to process {url}: {e}", exc_info=True
                                )
                                print(f"\n[ERROR] Skipped due to error: {e}")

                    # If we got here, check if we actually downloaded anything
                    # Only set success if we downloaded at least one file
                    if succeeded_in_this_pass:
                        success = True
                        break  # Exit player_client loop
                    # If no files downloaded, continue to next player_client config if available
                    elif use_cookies and player_client_idx < len(player_client_configs) - 1:
                        app_logging.log.info(
                            "No files downloaded with player_client %s, trying next configuration...",
                            player_clients
                        )
                        player_client_idx += 1
                        continue
                    else:
                        # No more configs to try, exit loop
                        break

                except FatalForbiddenError as e:
                    err_str = str(e)

                    # If signature solving failed and we have more player_client configs to try
                    if ("Signature Solving Failed" in err_str or "No Formats Available" in err_str) and \
                       use_cookies and player_client_idx < len(player_client_configs) - 1:
                        # Check if this is specifically asking to try next config
                        if "Try Next Config" in err_str:
                            player_client_idx += 1
                            continue  # Try next player_client config
                        else:
                            app_logging.log.info(
                                "Signature solving failed with player_client %s, trying next configuration...",
                                player_clients
                            )
                            player_client_idx += 1
                            continue  # Try next player_client config
                    else:
                        # No more configs to try, raise error to switch browser strategy
                        raise
                except Exception as e:
                    app_logging.log.error(
                        f"Unexpected error during download loop: {e}", exc_info=True
                    )
                    # If we have more player_client configs, try them
                    if use_cookies and player_client_idx < len(player_client_configs) - 1:
                        player_client_idx += 1
                        continue
                    else:
                        break

                # Handle FatalForbiddenError after player_client loop
                if success:
                    break  # Successfully downloaded, exit browser strategy loop

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
                f"Unexpected error during download loop: {e}", exc_info=True
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
                f"[PROCESSING] Item {i + 1}/{total}: {file_path.name}...    "
            )
            sys.stdout.flush()

            original_stem = file_path.stem
            clean_stem = sanitize_text(original_stem)

            if clean_stem != original_stem:
                new_filename = f"{clean_stem}{file_path.suffix}"
                new_path = file_path.parent / new_filename

                try:
                    if new_path.exists():
                        new_path = (
                            file_path.parent / f"{clean_stem}_{i}{file_path.suffix}"
                        )

                    os.rename(file_path, new_path)
                    file_path = new_path

                except OSError as e:
                    app_logging.log.error(f"Could not rename {file_path.name}: {e}")
                    print(f"[RENAME ERROR] Could not rename {file_path.name}: {e}")

            clean_tags(file_path)

    files_after = set(download_path.glob("*"))
    new_files_count = len(files_after - files_before)

    return {
        "new_files": new_files_count,
        "skipped_fragments": frag_logger.skipped,
        "warnings": frag_logger.warnings,
    }


def main() -> None:
    app_logging.log.info(
        "Music Downloader started. Base directory: %s", config.BASE_DIR
    )

    # Check for Deno installation
    if is_deno_installed():
        deno_path = get_deno_path()
        app_logging.log.info(
            "Deno JavaScript runtime detected: %s", deno_path or "PATH"
        )
    else:
        app_logging.log.warning(
            "Deno JavaScript runtime not found. YouTube signature solving may fail. "
            "Install Deno: Run windows\\install_deno.bat or visit https://deno.land"
        )

    try:
        browsers = [FirefoxBrowser(), ChromeBrowser()]
        app_logging.log.info(
            "Detected browser backends: %s", ", ".join(b.name for b in browsers)
        )

        while True:
            clear_screen()
            print("==========================================")
            print("     UNIVERSAL TAB GROUP DOWNLOADER       ")
            print("==========================================")

            print("\nSelect Browser:")
            for i, b in enumerate(browsers):
                print(f"[{i + 1}] {b.name}")
            print("[q] Quit")

            choice = input("\nChoice: ").strip().lower()
            if choice == "q":
                sys.exit()

            backend = None
            try:
                if choice.isdigit():
                    backend = browsers[int(choice) - 1]
                else:
                    continue
            except (ValueError, IndexError):
                continue

            app_logging.log.info("User selected browser backend: %s", backend.name)
            profiles = backend.get_profiles()

            if not profiles:
                app_logging.log.warning(
                    "No profiles found for backend: %s", backend.name
                )
                print(f"\nNo profiles found for {backend.name}.")
                input("Press Enter to back...")
                continue

            current_profile_idx = 0
            back_to_browser_menu = False

            while True:
                if back_to_browser_menu:
                    break

                selected_profile = profiles[current_profile_idx]

                while True:
                    clear_screen()
                    print(f"Browser: {backend.name}")
                    print(f"Profile: {selected_profile.name}")
                    print(f"Path:    {selected_profile}")
                    print("-" * 40)
                    print("Reading data...")

                    app_logging.log.info(
                        "Reading data for profile '%s' at path '%s'",
                        selected_profile.name,
                        selected_profile,
                    )
                    groups = backend.extract_groups(selected_profile)

                    valid_groups = {}
                    for name, links in groups.items():
                        yt_links = [
                            u for u in links if "youtube.com" in u or "youtu.be" in u
                        ]
                        if yt_links:
                            valid_groups[name] = yt_links

                    if not valid_groups:
                        app_logging.log.info(
                            "No valid YouTube groups found for profile '%s' (%s)",
                            selected_profile.name,
                            backend.name,
                        )
                        print("\nNo YouTube links found in this profile's Bookmarks.")

                        if backend.name == "Google Chrome":
                            print("\n[!] TIPS FOR CHROME:")
                            print(" 1. To detect links while Chrome is running:")
                            print("    - Right-click tabs and 'Add tabs to new group'.")
                            print(
                                "    - Press (Ctrl+Shift+D) to bookmark all tabs into a folder."
                            )
                            print(
                                " 2. Note: The script will prioritize Group Tab names."
                            )
                            print(" 3. Current profile: " + selected_profile.name)
                            print("    Press [p] to switch profiles if needed.")

                        print("-" * 40)
                        print("[r] Refresh Data")
                        print("[p] Switch Profile (Found " + str(len(profiles)) + ")")
                        print("[b] Back to Browser Selection")
                        print("[q] Quit")

                        choice_input = input("Choice: ").strip().lower()
                        if choice_input == "q":
                            sys.exit()
                        if choice_input == "b":
                            back_to_browser_menu = True
                            break
                        if choice_input == "p":
                            current_profile_idx = (current_profile_idx + 1) % len(
                                profiles
                            )
                            break
                        if choice_input == "r":
                            continue

                        continue

                    group_names = list(valid_groups.keys())
                    app_logging.log.info(
                        "Found %d group(s)/folder(s) for profile '%s'.",
                        len(group_names),
                        selected_profile.name,
                    )
                    print(f"\nFound Groups/Folders:")
                    for i, name in enumerate(group_names):
                        print(f"[{i + 1}] {name} ({len(valid_groups[name])} videos)")

                    print("\n------------------------------------------")
                    print("[#] Select Group")
                    print("[r] Refresh Data")
                    print("[p] Switch Profile")
                    print("[b] Back")
                    print("[q] Quit")

                    choice_input = input("\nChoice: ").strip().lower()
                    if choice_input == "q":
                        sys.exit()
                    if choice_input == "b":
                        back_to_browser_menu = True
                        break
                    if choice_input == "p":
                        current_profile_idx = (current_profile_idx + 1) % len(profiles)
                        break
                    if choice_input == "r":
                        continue

                    try:
                        target_group = group_names[int(choice_input) - 1]
                        app_logging.log.info(
                            "User selected group '%s' containing %d link(s).",
                            target_group,
                            len(valid_groups[target_group]),
                        )
                    except (ValueError, IndexError):
                        continue

                    quality = ask_quality()
                    if quality is None:
                        continue

                    app_logging.log.info(
                        f"User selected Quality: {quality.name} (Convert: {quality.convert})"
                    )

                    stats = download_audio(
                        valid_groups[target_group], target_group, quality
                    )

                    app_logging.log.info(
                        "Download finished for group '%s'. New files: %d, skipped fragments: %d, warnings: %d",
                        target_group,
                        stats.get("new_files", 0),
                        stats.get("skipped_fragments", 0),
                        stats.get("warnings", 0),
                    )

                    print(f"Downloaded {stats['new_files']} files")
                    print("\nJob Complete.")
                    input("Press Enter to continue...")

    except KeyboardInterrupt:
        app_logging.log.info("Execution interrupted by user via KeyboardInterrupt.")
        sys.exit(0)


if __name__ == "__main__":
    init_logging(config.BASE_DIR)
    try:
        main()
    except Exception as e:
        app_logging.log.exception("Unhandled exception in Music Downloader: %s", e)
        sys.exit(1)
