import os
import json
import sys
import re
import shutil
import platform
import lz4.block
from pathlib import Path
from abc import ABC, abstractmethod
import yt_dlp
from yt_dlp.utils import DownloadError
from mutagen.id3 import ID3, TXXX, COMM, USLT, TSSE, TENC, TYER, TDRC, TDAT, TRCK, TIT2
from typing import Optional, Dict, List, Any, Set


ALLOW_SKIP_FRAGMENTS = False
QUALITY_OPTIONS = {
    "1": {
        "name": "Best MP3 (up to 320kbps)",
        "desc": "Maximum MP3 quality. Universal compatibility.",
        "codec": "mp3",
        "quality": "320",
        "convert": True,
    },
    "2": {
        "name": "Standard MP3 (192kbps)",
        "desc": "Smaller file size, good enough for most uses.",
        "codec": "mp3",
        "quality": "192",
        "convert": True,
    },
    "3": {
        "name": "Original Audio (M4A/WebM)",
        "desc": "Best audio quality (Source). No conversion time.",
        "codec": None,
        "quality": None,
        "convert": False,
    },
}


class FatalForbiddenError(Exception):
    """Custom exception to stop the script immediately on 403 errors."""

    pass


class FragmentLogger:
    """
    Custom logger for yt-dlp to track missing video fragments/blocks.
    Crucial for identifying if a download is corrupt/incomplete.
    """

    def __init__(self) -> None:
        self.skipped = 0
        self.errors = 0
        self.warnings = 0

    def debug(self, msg: str) -> None:
        if "fragment" in msg.lower() and "skipping" in msg.lower():
            self.skipped += 1

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        if "fragment" in msg.lower() or "skipping" in msg.lower():
            self.skipped += 1
            print(f"[WARN] Skipped Fragment: {msg}")
        else:
            self.warnings += 1

    def error(self, msg: str) -> None:
        if "403" in msg or "Forbidden" in msg:
            print("\n[FATAL] HTTP Error 403 Detected! YouTube blocked the connection.")
            raise FatalForbiddenError("403 Forbidden")

        print(f"[ERROR] {msg}")
        self.errors += 1
        # Treat 'fragment not found' as a skip event
        if "fragment" in msg.lower() and "not found" in msg.lower():
            self.skipped += 1


def clear_screen() -> None:
    """Clears terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def is_ffmpeg_installed() -> bool:
    """Checks if FFmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def sanitize_text(text: str) -> str:
    """Removes common YouTube junk text from titles/filenames."""
    if not text:
        return ""

    # List of patterns to remove (Case insensitive)
    patterns = [
        r"\s*[({\[]\s*official\s*video\s*[)}\]]",  # (Official Video)
        r"\s*[({\[]\s*official\s*music\s*video\s*[)}\]]",  # (Official Music Video)
        r"\s*[({\[]\s*official\s*audio\s*[)}\]]",  # (Official Audio)
        r"\s*[({\[]\s*official\s*lyric\s*video\s*[)}\]]",  # (Official Lyric Video)
        r"\s*[({\[]\s*video\s*[)}\]]",  # (Video)
        r"\s*[({\[]\s*audio\s*[)}\]]",  # (Audio)
        r"\s*[({\[]\s*lyrics\s*[)}\]]",  # (Lyrics)
        r"\s*[({\[]\s*visualizer\s*[)}\]]",  # (Visualizer)
        r"\s*[({\[]\s*hq\s*[)}\]]",  # (HQ)
        r"\s*[({\[]\s*hd\s*[)}\]]",  # (HD)
        r"\s*[({\[]\s*4k\s*[)}\]]",  # (4K)
        r"\s*[({\[]\s*new\s*single\s*[)}\]]",  # (NEW SINGLE)
        r"\s*[({\[]\s*live\s*@.*?[)}\]]",  # (Live @ ...)
        r"\s*[({\[]\s*with\s*vocals\s*[)}\]]",  # (with vocals)
    ]

    clean_text = text
    for p in patterns:
        clean_text = re.sub(p, "", clean_text, flags=re.IGNORECASE)

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
            f"\r[COMPLETE]    |{'█' * 20}| 100% | Downloaded! Processing...                     \n"
        )
        sys.stdout.flush()


class BrowserBackend(ABC):
    """
    Abstract base class for adding future browsers (Edge, Brave, Opera, etc).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_profiles(self) -> List[Path]:
        """Returns a list of Path objects representing browser profiles."""
        pass

    @abstractmethod
    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        """
        Returns a dict: {'Group Name': [url1, url2, ...]}
        """
        pass

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Shared utility to extract video ID from URL."""
        if "youtube.com/watch" in url:
            match = re.search(r"[?&]v=([^&]+)", url)
            return match.group(1) if match else None
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/shorts/" in url:
            return url.split("shorts/")[1].split("?")[0]
        return None

    def _is_youtube_video(self, url: str) -> bool:
        """Shared utility to check if a URL is a valid video (not search/home)."""
        if not url:
            return False

        if "youtube.com" not in url and "youtu.be" not in url:
            return False

        # Blacklist search, results, and settings pages
        if any(
            x in url
            for x in [
                "search_query=",
                "/results",
                "accounts.google",
                "google.com/settings",
            ]
        ):
            return False

        # Ignore the home page
        clean_check = url.replace("www.", "").replace("https://", "").strip("/")
        if clean_check == "youtube.com":
            return False

        # Must be a watch link, short, or shortened link
        if "/watch" in url or "/shorts/" in url or "youtu.be" in url:
            return True

        return False


class FirefoxBrowser(BrowserBackend):
    @property
    def name(self) -> str:
        return "Mozilla Firefox"

    def get_profiles(self) -> List[Path]:
        """Locates Firefox profiles (Standard, Snap, Flatpak)."""
        system = platform.system()
        potential_base_paths = []

        if system == "Windows":
            potential_base_paths.append(
                Path(os.getenv("APPDATA")) / "Mozilla" / "Firefox" / "Profiles"
            )
        elif system == "Darwin":
            potential_base_paths.append(
                Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
            )
        elif system == "Linux":
            potential_base_paths.append(Path.home() / ".mozilla" / "firefox")
            potential_base_paths.append(
                Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
            )
            potential_base_paths.append(
                Path.home()
                / ".var"
                / "app"
                / "org.mozilla.firefox"
                / ".mozilla"
                / "firefox"
            )

        valid_profiles = []
        for base in potential_base_paths:
            if base.exists():
                # Get all subdirectories that look like profiles
                valid_profiles.extend([p for p in base.glob("*.*") if p.is_dir()])

        # Return sorted by modification time (newest first)
        if valid_profiles:
            return sorted(
                valid_profiles, key=lambda p: os.path.getmtime(p), reverse=True
            )
        return []

    def _load_lz4_json(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Decompress Mozilla LZ4 JSON."""
        try:
            with open(file_path, "rb") as file:
                data = file.read()
                if data[:8] == b"mozLz40\0":
                    decompressed = lz4.block.decompress(data[8:])
                    return json.loads(decompressed)
        except Exception as e:
            return None
        return None

    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        """Reads sessionstore/recovery.jsonlz4 to find active Tab Groups."""
        files = [
            profile_path / "sessionstore-backups" / "recovery.jsonlz4",
            profile_path / "sessionstore-backups" / "previous.jsonlz4",
            profile_path / "sessionstore.jsonlz4",
        ]

        json_data = None
        for f in files:
            if f.exists():
                json_data = self._load_lz4_json(f)
                if json_data:
                    break

        if not json_data:
            return {}

        organized_groups = {}
        seen_video_ids = set()

        if "windows" not in json_data:
            return {}

        for window in json_data["windows"]:
            group_metadata = {}
            raw_groups = window.get("groups", [])

            for g in raw_groups:
                g_id = g.get("id")
                g_title = g.get("title") or g.get("name") or "Untitled Group"
                if g_id:
                    group_metadata[g_id] = g_title

            if not group_metadata:
                continue

            for tab in window.get("tabs", []):
                group_id = tab.get("groupId")
                if group_id:
                    group_id = str(group_id)

                if not group_id or group_id not in group_metadata:
                    continue

                entries = tab.get("entries", [])
                if not entries:
                    continue

                active_idx = tab.get("index", 1) - 1
                if 0 <= active_idx < len(entries):
                    url = entries[active_idx].get("url", "")

                    if self._is_youtube_video(url):
                        vid_id = self._extract_video_id(url)

                        if vid_id and vid_id not in seen_video_ids:
                            seen_video_ids.add(vid_id)
                            group_name = group_metadata[group_id]
                            if group_name not in organized_groups:
                                organized_groups[group_name] = []
                            organized_groups[group_name].append(url)

        return organized_groups


class ChromeBrowser(BrowserBackend):
    @property
    def name(self) -> str:
        return "Google Chrome"

    def get_profiles(self) -> List[Path]:
        system = platform.system()
        base_path = None
        if system == "Windows":
            base_path = (
                Path(os.getenv("LOCALAPPDATA")) / "Google" / "Chrome" / "User Data"
            )
        elif system == "Darwin":
            base_path = (
                Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
            )
        elif system == "Linux":
            base_path = Path.home() / ".config" / "google-chrome"

        if not base_path or not base_path.exists():
            return []

        profiles = []
        if (base_path / "Default").exists():
            profiles.append(base_path / "Default")
        profiles.extend(list(base_path.glob("Profile *")))

        def get_pref_mtime(p):
            pref = p / "Preferences"
            return pref.stat().st_mtime if pref.exists() else 0

        # Sort by recently used
        return sorted(profiles, key=get_pref_mtime, reverse=True)

    def _get_active_session_urls(self, profile_path: Path) -> List[str]:
        """
        Scrapes the binary 'Current Session' (SNSS format) using Regex.
        Filters navigation history and duplicates.
        """
        sessions_dir = profile_path / "Sessions"
        if not sessions_dir.exists():
            return []

        target_file = sessions_dir / "Current Session"

        # If the Current Session file is locked or empty, try to find the last Session_*
        if not target_file.exists() or target_file.stat().st_size == 0:
            session_files = list(sessions_dir.glob("Session_*"))
            if session_files:
                target_file = max(session_files, key=os.path.getmtime)
            else:
                return []

        final_urls = []
        seen_video_ids = set()

        url_pattern = re.compile(rb'(https?://[^\x00-\x20\x7f"<>|\^`{\}]+)')

        try:
            with open(target_file, "rb") as f:
                content = f.read()
                matches = url_pattern.findall(content)

                # Read the file from the end, since the current tabs are usually at the end of the file
                for match in reversed(matches):
                    try:
                        dec_url = match.decode("utf-8")

                        if self._is_youtube_video(dec_url):
                            vid_id = self._extract_video_id(dec_url)
                            if vid_id and vid_id not in seen_video_ids:
                                seen_video_ids.add(vid_id)
                                final_urls.append(dec_url)

                    except UnicodeDecodeError:
                        continue
        except Exception as e:
            print(f"[WARN] Could not read Chrome Session file: {e}")

        return final_urls

    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        organized_groups = {}

        active_urls = self._get_active_session_urls(profile_path)
        if active_urls:
            organized_groups["[Active Session] Open Tabs"] = active_urls

        bookmarks_path = profile_path / "Bookmarks"

        if bookmarks_path.exists():
            try:
                with open(bookmarks_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                seen_bookmark_vids = set()

                def recurse_nodes(node, current_folder_name=None):
                    my_name = node.get("name", "")
                    if "children" in node:
                        next_group = (
                            my_name
                            if node.get("id") != "0"
                            and my_name
                            not in [
                                "Bookmarks bar",
                                "Other bookmarks",
                                "Mobile bookmarks",
                            ]
                            else current_folder_name
                        )
                        for child in node["children"]:
                            recurse_nodes(child, next_group)
                    elif "url" in node:
                        url = node["url"]
                        if self._is_youtube_video(url):
                            vid_id = self._extract_video_id(url)
                            if vid_id and vid_id not in seen_bookmark_vids:
                                seen_bookmark_vids.add(vid_id)
                                if current_folder_name:
                                    if current_folder_name not in organized_groups:
                                        organized_groups[current_folder_name] = []
                                    organized_groups[current_folder_name].append(url)

                roots = data.get("roots", {})
                for root_key in roots:
                    recurse_nodes(roots[root_key])
            except Exception:
                pass

        return organized_groups


def ask_quality() -> Optional[Dict[str, Any]]:
    """CLI Menu for selecting audio quality."""
    global ALLOW_SKIP_FRAGMENTS
    ffmpeg_available = is_ffmpeg_installed()
    while True:
        print("\n--- Audio Quality Settings ---")
        for key, val in QUALITY_OPTIONS.items():
            if not ffmpeg_available and val["convert"]:
                print(f"[{key}] [UNAVAILABLE - Needs FFmpeg] {val['name']}")
            else:
                print(f"[{key}] {val['name']} - {val['desc']}")

        skip_status = (
            "ENABLED (Audio may glitch)"
            if ALLOW_SKIP_FRAGMENTS
            else "DISABLED (Stops on error)"
        )
        print(f"\n[S] Skip Missing Blocks: {skip_status}")

        choice = input("\nSelect Quality (or 'q' to quit, 'b' back): ").strip().lower()

        if choice == "q":
            sys.exit()
        if choice == "b":
            return None

        if choice == "s":
            ALLOW_SKIP_FRAGMENTS = not ALLOW_SKIP_FRAGMENTS
            print("Setting updated.")
            continue

        if choice in QUALITY_OPTIONS:
            selected = QUALITY_OPTIONS[choice]

            if selected["convert"] and not ffmpeg_available:
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
                print(f"[METADATA] Renamed Title: '{original_title}' -> '{new_title}'")

        # Save (Force ID3v2.3 for max Windows/Car compatibility)
        audio.save(v1=0, v2_version=3)
        print(f"[CLEANER] Sanitized tags: {filepath.name}")

    except Exception as e:
        print(f"[CLEANER ERROR] Failed on {filepath.name}: {e}")


def download_audio(
    urls: List[str], group_name: str, quality_settings: Dict[str, Any]
) -> Dict[str, int]:
    """
    Orchestrates the download process using yt-dlp.
    Handles filename generation, conversions, and metadata post-processing.
    """
    safe_name = "".join(
        [c for c in group_name if c.isalpha() or c.isdigit() or c == " "]
    ).strip()
    download_path = Path("downloads") / safe_name
    download_path.mkdir(parents=True, exist_ok=True)

    files_before = set(download_path.glob("*"))
    frag_logger = FragmentLogger()
    has_ffmpeg = is_ffmpeg_installed()
    browser_strategies = [None, "firefox", "chrome"]

    success = False
    downloaded_files = []

    for current_browser in browser_strategies:
        if success:
            break

        browser_name = current_browser if current_browser else "Anonymous (No Cookies)"
        print(f"\n" + "=" * 50)
        print(f"[ATTEMPT] Trying download via: {browser_name.upper()}")
        print("=" * 50)

        ydl_opts = {
            "outtmpl": str(download_path / "%(title)s.%(ext)s"),
            "restrictfilenames": False,
            "windowsfilenames": True,
            "overwrites": True,
            "verbose": False,
            "quiet": False,
            "logger": frag_logger,
            "progress_hooks": [show_progress],
            "socket_timeout": 30,
            "retries": 15,
            "fragment_retries": 15,
            "keepfragments": False,
            "skip_unavailable_fragments": ALLOW_SKIP_FRAGMENTS,
            "writethumbnail": False,
            "noplaylist": True,
            "extractor_args": {
                "youtube": {"player_client": ["default", "-web_safari"]}
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

            if quality_settings["convert"]:
                ydl_opts["format"] = "bestaudio/bestvideo+bestaudio/best"
                ydl_opts["postprocessors"].insert(
                    0,
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": quality_settings["codec"],
                        "preferredquality": "0",
                    },
                )
            else:
                ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
        else:
            print("\n[INFO] FFmpeg not detected. Downloading raw audio only.")
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for url in urls:
                    try:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        final_path = Path(filename)

                        if quality_settings["convert"]:
                            final_path = final_path.with_suffix(
                                f".{quality_settings['codec']}"
                            )

                        downloaded_files.append(final_path)

                    except DownloadError as e:
                        err_msg = str(e)

                        if "403" in err_msg or "Forbidden" in err_msg:
                            raise FatalForbiddenError("403 Forbidden (IP Block)")

                        if "Requested format is not available" in err_msg:
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

                        print(f"\n[ERROR] Download failed for {url}: {e}")

            success = True

        except FatalForbiddenError as e:
            print(f"\n[WARN] Strategy '{browser_name}' failed: {e}")
            print("[INFO] Switching to next browser strategy...")
        except Exception as e:
            print(f"\n[CRITICAL] Unexpected error: {e}")
            break

    if not success:
        print("\n[FAILED] All browser strategies failed to download the content.")
        print("Please check your internet or try updating yt-dlp.")

    if has_ffmpeg and downloaded_files:
        print("\n" + "=" * 50)
        print("\n[POST-PROCESSING] Cleaning tags and renaming files...")
        print("=" * 50)

        total = len(downloaded_files)

        for i, file_path in enumerate(downloaded_files):
            if not file_path.exists():
                continue

            sys.stdout.write(
                f"\r[PROCESSING] Item {i + 1}/{total}: {file_path.name[:40]}...    "
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
    try:
        browsers = [FirefoxBrowser(), ChromeBrowser()]

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

            profiles = backend.get_profiles()
            if not profiles:
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

                    groups = backend.extract_groups(selected_profile)

                    valid_groups = {}
                    for name, links in groups.items():
                        yt_links = [
                            u for u in links if "youtube.com" in u or "youtu.be" in u
                        ]
                        if yt_links:
                            valid_groups[name] = yt_links

                    if not valid_groups:
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
                    except (ValueError, IndexError):
                        continue

                    quality = ask_quality()
                    if quality is None:
                        continue

                    stats = download_audio(
                        valid_groups[target_group], target_group, quality
                    )

                    print(f"Downloaded {stats['new_files']} files")
                    print("\nJob Complete.")
                    input("Press Enter to continue...")

    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
