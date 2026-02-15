import os

# Layout
SEP_LINE = "=" * 50
SEP_THIN = "-" * 40
TITLE_BORDER = "=" * 50


def clear_screen() -> None:
    """Clears the terminal screen (cross-platform)."""
    os.system("cls" if os.name == "nt" else "clear")


# Prompts
def prompt(message: str, hint: str = "") -> str:
    """Single input prompt. Optional hint on next line in parentheses."""
    if hint:
        return input(f"\n{message} ({hint}): ").strip().lower()
    return input(f"\n{message}: ").strip().lower()


def wait_enter(message: str = "Press Enter to continue") -> None:
    """Pause until user presses Enter."""
    input(f"\n{message}...")


# Messages (user-facing)
MSG_NO_GROUPS = "No YouTube links found in this profile."
MSG_SELECT_GROUP = "Enter group number, or use a key below."
MSG_INVALID_CHOICE = "Invalid choice. Try again."
MSG_JOB_DONE = "Job complete."
MSG_FFMPEG_MISSING = (
    "FFmpeg is not installed. Install it for MP3 conversion, or choose Original Audio (3)."
)
MSG_SETTING_UPDATED = "Setting updated."
MSG_NO_PROFILES = "No profiles found for this browser."
MSG_STRATEGY_FAILED = "This method failed; trying next option..."
MSG_ALL_FAILED = "All download attempts failed. Check connection or update yt-dlp."
MSG_FILES_SAVED = "Files saved to: {path}"
