"""Entry point: CLI and orchestration only."""

import sys

import app_logging
import config
from app_logging import init as init_logging
from browsers import ChromeBrowser, FirefoxBrowser
from config import get_config, RuntimeSettings
from core import download_audio, get_deno_path, is_deno_installed, ask_quality


def clear_screen() -> None:
    """Clears terminal screen cross-platform."""
    import os
    os.system("cls" if os.name == "nt" else "clear")


def main() -> None:
    app_logging.log.info(
        "Music Downloader started. Base directory: %s", config.BASE_DIR
    )

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

        app_cfg = get_config()
        settings = RuntimeSettings(allow_skip_fragments=app_cfg.allow_skip_fragments)

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

                    quality = ask_quality(settings)
                    if quality is None:
                        continue

                    app_logging.log.info(
                        "User selected Quality: %s (Convert: %s)",
                        quality.name,
                        quality.convert,
                    )

                    stats = download_audio(
                        valid_groups[target_group],
                        target_group,
                        quality,
                        settings,
                        app_cfg.download_dir,
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
