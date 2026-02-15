import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .constants import BASE_DIR


@dataclass
class RuntimeSettings:
    """Mutable settings used during a run (e.g. quality menu toggle)."""

    allow_skip_fragments: bool = False


@dataclass
class AppConfig:
    """Application config loaded from file or defaults."""

    download_dir: Path = field(default_factory=lambda: BASE_DIR / "downloads")
    default_quality: Optional[str] = None  # "1", "2", "3" or None
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    allow_skip_fragments: bool = False


_CONFIG_PATH = BASE_DIR / "config.json"
_loaded: Optional[AppConfig] = None


def load_config() -> AppConfig:
    """Load config from config.json if present, else return defaults. Cached."""
    global _loaded
    if _loaded is not None:
        return _loaded

    defaults = AppConfig()
    if not _CONFIG_PATH.exists():
        _loaded = defaults
        return _loaded

    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        _loaded = defaults
        return _loaded

    download_dir = defaults.download_dir
    if "download_dir" in data and data["download_dir"]:
        raw = data["download_dir"]
        p = Path(raw)
        if not p.is_absolute():
            p = BASE_DIR / p
        download_dir = p.resolve()

    default_quality = data.get("default_quality")
    if default_quality is not None and default_quality not in ("1", "2", "3"):
        default_quality = None

    log_level = (data.get("log_level") or "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        log_level = "INFO"

    allow_skip_fragments = bool(data.get("allow_skip_fragments", False))

    _loaded = AppConfig(
        download_dir=download_dir,
        default_quality=default_quality,
        log_level=log_level,
        allow_skip_fragments=allow_skip_fragments,
    )
    return _loaded


def get_config() -> AppConfig:
    """Return current config (loads from file on first call)."""
    return load_config()
