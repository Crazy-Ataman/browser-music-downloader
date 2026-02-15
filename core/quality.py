import sys
from typing import Optional

import app_logging
import config
from config import QualityProfile, RuntimeSettings

from .download import is_ffmpeg_installed


def ask_quality(settings: RuntimeSettings) -> Optional[QualityProfile]:
    """CLI menu for selecting audio quality. Toggles settings.allow_skip_fragments on [S]."""
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
            if settings.allow_skip_fragments
            else "DISABLED (Stops on error)"
        )
        print(f"\n[S] Skip Missing Blocks: {skip_status}")

        choice = input("\nSelect Quality (or 'q' to quit, 'b' back): ").strip().lower()

        if choice == "q":
            sys.exit()
        if choice == "b":
            return None

        if choice == "s":
            settings.allow_skip_fragments = not settings.allow_skip_fragments
            app_logging.log.info(
                "User toggled skip missing fragments to: %s",
                settings.allow_skip_fragments,
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
