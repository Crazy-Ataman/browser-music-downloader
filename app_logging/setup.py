import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from config.constants import (
    LOG_FILE_BACKUP_COUNT,
    LOG_FILE_MAX_BYTES,
    LOG_ROTATION_MODE,
    LOG_TIME_BACKUP_COUNT,
    LOG_TIME_INTERVAL,
    LOG_TIME_WHEN,
)

_LEVEL_NAMES = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}


def setup_logging(base_dir: Path, console_level: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger("MusicDownloader")

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / "log.txt"

    if LOG_ROTATION_MODE == "size":
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUP_COUNT,
            encoding="utf-8",
        )
    elif LOG_ROTATION_MODE == "time":
        file_handler = TimedRotatingFileHandler(
            log_file_path,
            when=LOG_TIME_WHEN,
            interval=LOG_TIME_INTERVAL,
            backupCount=LOG_TIME_BACKUP_COUNT,
            encoding="utf-8",
        )
    else:
        file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")

    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s"
    )
    file_handler.setFormatter(file_format)

    console_handler = logging.StreamHandler()
    level = _LEVEL_NAMES.get((console_level or "INFO").upper(), logging.INFO)
    console_handler.setLevel(level)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
