class FatalForbiddenError(Exception):
    """Custom exception to stop the script immediately on 403 errors."""

    pass


class FragmentLogger:
    """
    Custom logger for yt-dlp to track missing video fragments/blocks.
    Crucial for identifying if a download is corrupt/incomplete.
    """

    def __init__(self) -> None:
        self.skipped = 0
        self.errors = 0
        self.warnings = 0
        self.signature_solving_failed = False
        self.only_images_available = False

    def _log(self):
        from . import log

        return log

    def debug(self, msg: str) -> None:
        if "fragment" in msg.lower() and "skipping" in msg.lower():
            self.skipped += 1

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log = self._log()
        msg_lower = msg.lower()

        # Detect signature solving failures
        if "signature solving failed" in msg_lower or "challenge solving failed" in msg_lower:
            self.signature_solving_failed = True
            log.warning(f"Signature solving issue detected: {msg}")

        # Detect "only images available" warnings
        if "only images are available" in msg_lower:
            self.only_images_available = True
            log.warning("Only storyboard images available - no audio/video formats")

        if "fragment" in msg_lower or "skipping" in msg_lower:
            self.skipped += 1
            log.warning(f"Skipped Fragment: {msg}")
        else:
            self.warnings += 1

    def error(self, msg: str) -> None:
        log = self._log()
        msg_lower = msg.lower()

        if "403" in msg or "Forbidden" in msg:
            error_msg = "HTTP Error 403 Detected! YouTube blocked the connection."
            print(f"\n[FATAL] {error_msg}")
            log.critical(error_msg)
            raise FatalForbiddenError("403 Forbidden")

        # Detect format availability issues
        if "requested format is not available" in msg_lower:
            # Check if this is due to signature solving failure
            if self.signature_solving_failed or self.only_images_available:
                log.warning("Format unavailable likely due to signature solving failure")

        log.error(msg)
        self.errors += 1
        if "fragment" in msg_lower and "not found" in msg_lower:
            self.skipped += 1
