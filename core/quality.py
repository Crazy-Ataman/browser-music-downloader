import sys
from typing import Optional

import app_logging
import config
from config import QualityProfile, RuntimeSettings

from .download import is_ffmpeg_installed
from .ui import (
    MSG_FFMPEG_MISSING,
    MSG_INVALID_CHOICE,
    MSG_SETTING_UPDATED,
    clear_screen,
    prompt,
    wait_enter,
)


def ask_quality(settings: RuntimeSettings) -> Optional[QualityProfile]:
    """CLI menu for selecting audio quality. Toggles settings.allow_skip_fragments on [S]."""
    ffmpeg_available = is_ffmpeg_installed()
    app_logging.log.info(
        "Opening quality selection menu (FFmpeg available: %s)",
        ffmpeg_available,
    )
    while True:
        clear_screen()
        print("\n  --- Audio quality ---\n")
        for key, val in config.QUALITY_OPTIONS.items():
            if not ffmpeg_available and val.convert:
                print("    [{}] {}  (requires FFmpeg)".format(key, val.name))
            else:
                print("    [{}] {}  —  {}".format(key, val.name, val.desc))

        skip_status = (
            "on (may skip bad fragments)"
            if settings.allow_skip_fragments
            else "off (stop on error)"
        )
        print("\n    [S] Skip missing blocks:  {}".format(skip_status))
        print("    [b] Back   [q] Quit")

        choice = prompt("Select quality", "1–3, S, b, q")

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
            print("\n  " + MSG_SETTING_UPDATED)
            continue

        if choice in config.QUALITY_OPTIONS:
            selected = config.QUALITY_OPTIONS[choice]
            if selected.convert and not ffmpeg_available:
                app_logging.log.error(
                    "FFmpeg is missing! Cannot convert to %s.", selected.codec
                )
                print("\n  " + MSG_FFMPEG_MISSING)
                wait_enter()
                continue
            return selected

        print("\n  " + MSG_INVALID_CHOICE)
