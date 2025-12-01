import os
import json
import sys
import re
import shutil
import platform
import lz4.block
from pathlib import Path
import yt_dlp
import mutagen
from mutagen.id3 import ID3, TXXX, COMM, USLT, TSSE, TENC, TYER, TDRC, TDAT, TRCK


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


class FragmentLogger:
    """
    Custom logger for yt-dlp to track missing video fragments/blocks.
    Crucial for identifying if a download is corrupt/incomplete.
    """

    def __init__(self):
        self.skipped = 0
        self.errors = 0
        self.warnings = 0

    def debug(self, msg):
        if "fragment" in msg.lower() and "skipping" in msg.lower():
            self.skipped += 1

    def info(self, msg):
        pass

    def warning(self, msg):
        if "fragment" in msg.lower() or "skipping" in msg.lower():
            self.skipped += 1
            print(f"[WARN] Skipped Fragment: {msg}")
        else:
            self.warnings += 1

    def error(self, msg):
        print(f"[ERROR] {msg}")
        self.errors += 1
        # Treat 'fragment not found' as a skip event
        if "fragment" in msg.lower() and "not found" in msg.lower():
            self.skipped += 1


def clear_screen():
    """Clears terminal screen cross-platform."""
    os.system("cls" if os.name == "nt" else "clear")


def is_ffmpeg_installed():
    """Checks if FFmpeg is available in the system PATH."""
    return shutil.which("ffmpeg") is not None


def get_firefox_profile_path():
    """
    Locates the most recently modified Firefox profile.
    Supports Windows, macOS, and Linux (Standard, Snap, Flatpak).
    """
    system = platform.system()
    potential_paths = []
    if system == "Windows":
        potential_paths.append(
            Path(os.getenv("APPDATA")) / "Mozilla" / "Firefox" / "Profiles"
        )
    elif system == "Darwin":
        potential_paths.append(
            Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
        )
    elif system == "Linux":
        # Standard
        potential_paths.append(Path.home() / ".mozilla" / "firefox")
        # Snap
        potential_paths.append(
            Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
        )
        # Flatpak
        potential_paths.append(
            Path.home()
            / ".var"
            / "app"
            / "org.mozilla.firefox"
            / ".mozilla"
            / "firefox"
        )
    else:
        return None

    valid_base_paths = [p for p in potential_paths if p.exists()]

    if not valid_base_paths:
        return None

    all_profiles = []
    for base in valid_base_paths:
        all_profiles.extend(list(base.glob("*.*")))

    if not all_profiles:
        return None

    # Return the one modified most recently
    return max(all_profiles, key=os.path.getmtime)


def load_session_data(profile_path):
    """
    Reads Firefox session data. Firefox compresses this using a non-standard LZ4 format.
    Requires header offset skipping (b"mozLz40\\0").
    """
    # Priority:
    # 1. recovery.jsonlz4 - Live session (if Firefox is running/crashed)
    # 2. previous.jsonlz4 - Backup of the last session
    # 3. sessionstore.jsonlz4 - Saved state when Firefox is closed cleanly
    files = [
        profile_path / "sessionstore-backups" / "recovery.jsonlz4",
        profile_path / "sessionstore-backups" / "previous.jsonlz4",
        profile_path / "sessionstore.jsonlz4",
    ]

    for f in files:
        if f.exists():
            try:
                with open(f, "rb") as file:
                    data = file.read()
                    if data[:8] == b"mozLz40\0":
                        decompressed = lz4.block.decompress(data[8:])
                        return json.loads(decompressed)
            except Exception as e:
                print(f"[ERROR] Could not read {f.name}: {e}")
    return None


def extract_named_groups(json_data):
    """
    Parses the massive JSON session object to find 'Tab Groups' (specific to Firefox).
    Returns a dict: {'Group Name': [url1, url2, ...]}
    """
    organized_groups = {}
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
            if group_id is not None:
                group_id = str(group_id)

            if not group_id or group_id not in group_metadata:
                continue

            entries = tab.get("entries", [])
            if not entries:
                continue

            active_idx = tab.get("index", 1) - 1
            if 0 <= active_idx < len(entries):
                url = entries[active_idx].get("url", "")
                group_name = group_metadata[group_id]
                if group_name not in organized_groups:
                    organized_groups[group_name] = []
                organized_groups[group_name].append(url)

    return organized_groups


def ask_quality():
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


def clean_tags(filepath):
    """
    Metadata cleaning for MP3s using Mutagen.
    Removes proprietary ffmpeg tags (TSSE, TENC) and comments (TXXX).
    Standardizes Year (TYER) and removes Track Numbers (TRCK).
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

        # Save (Force ID3v2.3 for max Windows/Car compatibility)
        audio.save(v1=0, v2_version=3)
        print(f"[CLEANER] Sanitized tags: {filepath.name}")

    except Exception as e:
        print(f"[CLEANER ERROR] Failed on {filepath.name}: {e}")


def download_audio(urls, group_name, quality_settings):
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

    ydl_opts = {
        "outtmpl": str(download_path / "%(title)s.%(ext)s"),
        "restrictfilenames": False,
        "windowsfilenames": True,
        "overwrites": True,
        "verbose": False,
        "quiet": False,
        "logger": frag_logger,
        "progress_hooks": [],
        "socket_timeout": 30,
        "retries": 15,
        "fragment_retries": 15,
        "keepfragments": False,
        "skip_unavailable_fragments": ALLOW_SKIP_FRAGMENTS,
        "cookiesfrombrowser": ("firefox",),
        "writethumbnail": False,
        "noplaylist": True,
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
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"].insert(
                0,
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": quality_settings["codec"],
                    # '0' means Best Variable Bitrate (VBR) in FFmpeg/LAME (~240-260 kbps)
                    "preferredquality": "0",
                },
            )
        else:
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

    else:
        print("\n[INFO] FFmpeg not detected. Downloading raw audio only.")
        print("       (Metadata, Covers, and SponsorBlock disabled)")
        ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"

    print(f"\n[STARTING] Downloading {len(urls)} items to: {download_path}")

    downloaded_files = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                final_path = Path(filename)

                if quality_settings["convert"]:
                    final_path = final_path.with_suffix(f".{quality_settings['codec']}")

                downloaded_files.append(final_path)

    except Exception as e:
        print(f"\n[ERROR] {e}")

    if has_ffmpeg:
        print("\n[POST-PROCESSING] Cleaning tags...")
        for file_path in downloaded_files:
            if file_path.exists():
                clean_tags(file_path)

    files_after = set(download_path.glob("*"))
    new_files_count = len(files_after - files_before)

    return {
        "new_files": new_files_count,
        "skipped_fragments": frag_logger.skipped,
        "warnings": frag_logger.warnings,
    }


def main():
    try:
        profile = get_firefox_profile_path()
        if not profile:
            print("Error: Firefox profile not found. Is Firefox installed?")
            print("Searched in standard, Snap, and Flatpak locations.")
            input("Press Enter to exit...")
            return

        while True:
            clear_screen()
            print("==========================================")
            print("   FIREFOX TAB GROUP MUSIC DOWNLOADER")
            print("==========================================")
            print(f"Profile: {profile.name}")

            data = load_session_data(profile)
            if not data:
                print("Error: Could not load session data.")
                print("Tip: If Firefox is running, recovery.jsonlz4 handles the data.")
                input("Press Enter to retry...")
                continue

            groups = extract_named_groups(data)

            # Filter only groups that have YouTube links
            valid_groups = {}
            for name, links in groups.items():
                yt_links = [u for u in links if "youtube.com" in u or "youtu.be" in u]
                if yt_links:
                    valid_groups[name] = yt_links

            if not valid_groups:
                print("\nNo Tab Groups with YouTube links found.")
                print("Options: [r] Refresh Data, [q] Quit")
                choice = input("Choice: ").strip().lower()
                if choice == "q":
                    sys.exit()
                continue

            group_names = list(valid_groups.keys())
            print(f"\nAvailable Groups (with YouTube links):")
            for i, name in enumerate(group_names):
                count = len(valid_groups[name])
                print(f"[{i + 1}] {name} ({count} videos)")

            print("\n------------------------------------------")
            print("[Number] Select Group")
            print("[r]      Refresh Data (if you added tabs)")
            print("[q]      Quit Script")

            choice_input = input("\nChoice: ").strip().lower()

            if choice_input == "q":
                sys.exit()

            if choice_input == "r":
                print("Reloading...")
                continue

            target_group = None
            try:
                choice_idx = int(choice_input) - 1
                if 0 <= choice_idx < len(group_names):
                    target_group = group_names[choice_idx]
                else:
                    print("Invalid number!")
                    input("Press Enter to continue...")
                    continue
            except ValueError:
                print("Invalid input!")
                input("Press Enter to continue...")
                continue

            urls = valid_groups[target_group]

            print(f"\nSelected: '{target_group}'")
            print(f"Preparing to download {len(urls)} links...")

            quality = ask_quality()
            if quality is None:
                continue

            try:
                stats = download_audio(urls, target_group, quality)

                print("\n==========================================")
                print("             JOB COMPLETE                 ")
                print("==========================================")
                print(f"Processed: {len(urls)} links")
                print(f"New Files: {stats['new_files']} added")

                if stats["skipped_fragments"] > 0:
                    print(
                        f"WARNING: {stats['skipped_fragments']} audio blocks were MISSING."
                    )
                    if ALLOW_SKIP_FRAGMENTS:
                        print("         (Files saved with possible glitches/silence)")
                    else:
                        print("         (Some downloads may have aborted)")
                else:
                    print("Status:    Perfect Stream (0 blocks skipped)")

                print("==========================================")
            except Exception as e:
                print(f"\nCRITICAL ERROR: {e}")

            input("\nPress Enter to return to menu...")

    except KeyboardInterrupt:
        print("\n\nExiting gracefully...")
        sys.exit(0)


if __name__ == "__main__":
    main()
