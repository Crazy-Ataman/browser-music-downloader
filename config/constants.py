import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass
class QualityProfile:
    name: str
    desc: str
    codec: Optional[str]
    quality: Optional[str]
    convert: bool


QUALITY_OPTIONS = {
    "1": QualityProfile(
        name="Best MP3 (up to 320kbps)",
        desc="Maximum MP3 quality. Universal compatibility.",
        codec="mp3",
        quality="320",
        convert=True,
    ),
    "2": QualityProfile(
        name="Standard MP3 (192kbps)",
        desc="Smaller file size, good enough for most uses.",
        codec="mp3",
        quality="192",
        convert=True,
    ),
    "3": QualityProfile(
        name="Original Audio (M4A/WebM)",
        desc="Best audio quality (Source). No conversion time.",
        codec=None,
        quality=None,
        convert=False,
    ),
}

# Title/filename cleanup patterns
CLEANUP_PATTERNS = [
    re.compile(r"\s*[({\[]\s*official\s*video\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*official\s*music\s*video\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*official\s*audio\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*official\s*lyric\s*video\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*video\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*audio\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*lyrics\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*visualizer\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*hq\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*hd\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*4k\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*new\s*single\s*[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*live\s*@.*?[)}\]]", re.IGNORECASE),
    re.compile(r"\s*[({\[]\s*with\s*vocals\s*[)}\]]", re.IGNORECASE),
]

# Logging
LOG_ROTATION_MODE = "size"
LOG_FILE_MAX_BYTES = 5 * 1024 * 1024
LOG_FILE_BACKUP_COUNT = 5
LOG_TIME_WHEN = "midnight"
LOG_TIME_INTERVAL = 1
LOG_TIME_BACKUP_COUNT = 30
