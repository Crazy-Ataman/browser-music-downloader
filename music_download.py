"""Entry point: CLI and orchestration only."""

import sys

import app_logging
import config
from app_logging import init as init_logging
from browsers import ChromeBrowser, FirefoxBrowser
from config import get_config, RuntimeSettings
from core import (
    download_audio,
    get_deno_path,
    is_deno_installed,
    ask_quality,
    clear_screen,
    SEP_LINE,
    SEP_THIN,
    wait_enter,
    prompt,
    MSG_NO_GROUPS,
    MSG_SELECT_GROUP,
    MSG_INVALID_CHOICE,
    MSG_JOB_DONE,
    MSG_NO_PROFILES,
    MSG_FILES_SAVED,
)


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
            print(SEP_LINE)
            print("     UNIVERSAL TAB GROUP DOWNLOADER       ")
            print(SEP_LINE)
            print("\n  Select browser (sources for tabs/bookmarks):\n")
            for i, b in enumerate(browsers):
                print(f"    [{i + 1}] {b.name}")
            print("    [q] Quit")

            choice = prompt("Choice", "1–{}, q".format(len(browsers)))
            if choice == "q":
                sys.exit()

            backend = None
            try:
                if choice.isdigit():
                    backend = browsers[int(choice) - 1]
                else:
                    continue
            except (ValueError, IndexError):
                print("\n  " + MSG_INVALID_CHOICE)
                wait_enter()
                continue

            app_logging.log.info("User selected browser backend: %s", backend.name)
            profiles = backend.get_profiles()

            if not profiles:
                app_logging.log.warning(
                    "No profiles found for backend: %s", backend.name
                )
                print("\n  " + MSG_NO_PROFILES)
                wait_enter()
                continue

            current_profile_idx = 0
            back_to_browser_menu = False

            while True:
                if back_to_browser_menu:
                    break

                selected_profile = profiles[current_profile_idx]

                while True:
                    clear_screen()
                    print(SEP_LINE)
                    print("  {}  —  {}".format(backend.name, selected_profile.name))
                    print(SEP_THIN)
                    print("  Reading tabs and bookmarks...")

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
                        print("\n  " + MSG_NO_GROUPS)

                        if backend.name == "Google Chrome":
                            print("\n  Tips for Chrome:")
                            print("    • Right-click tabs → \"Add tabs to new group\".")
                            print("    • Ctrl+Shift+D bookmarks all open tabs into a folder.")
                            print("    • Current profile: " + selected_profile.name)

                        print(SEP_THIN)
                        print("  [r] Refresh   [p] Switch profile ({})   [b] Back   [q] Quit".format(len(profiles)))

                        choice_input = prompt("Choice", "r, p, b, q")
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
                    print("\n  Found {} group(s):\n".format(len(group_names)))
                    for i, name in enumerate(group_names):
                        print("    [{}] {}  ({} video{})".format(
                            i + 1, name, len(valid_groups[name]),
                            "s" if len(valid_groups[name]) != 1 else ""
                        ))

                    print(SEP_THIN)
                    print("  " + MSG_SELECT_GROUP)
                    print("  [r] Refresh   [p] Switch profile   [b] Back   [q] Quit")

                    choice_input = prompt("Choice", "1–{}, r, p, b, q".format(len(group_names)))
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
                        print("\n  " + MSG_INVALID_CHOICE)
                        wait_enter()
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

                    new_files = stats.get("new_files", 0)
                    warnings = stats.get("warnings", 0)
                    skipped = stats.get("skipped_fragments", 0)
                    safe_name = "".join(
                        c for c in target_group if c.isalpha() or c.isdigit() or c == " "
                    ).strip()
                    save_path = app_cfg.download_dir / (safe_name or "downloads")

                    print("\n  " + MSG_FILES_SAVED.format(path=save_path))
                    print("  Downloaded {} file(s).".format(new_files))
                    if warnings or skipped:
                        print("  ({} warning(s), {} skipped fragment(s))".format(warnings, skipped))
                    print("\n  " + MSG_JOB_DONE)
                    wait_enter()

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
