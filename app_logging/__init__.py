from pathlib import Path
from typing import Any
from .fragment_logger import FatalForbiddenError, FragmentLogger
from .setup import setup_logging

log: Any = None


def init(base_dir: Path) -> Any:
    """Initialize logging. Must be called before using log or FragmentLogger."""
    global log
    log = setup_logging(Path(base_dir))
    return log


__all__ = [
    "setup_logging",
    "init",
    "log",
    "FragmentLogger",
    "FatalForbiddenError",
]
