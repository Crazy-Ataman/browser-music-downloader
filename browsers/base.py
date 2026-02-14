import json
import os
import re
import shutil
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
import lz4.block


class BrowserBackend(ABC):
    """
    Abstract base class for adding future browsers (Edge, Brave, Opera, etc).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def get_profiles(self) -> List[Path]:
        """Returns a list of Path objects representing browser profiles."""
        pass

    @abstractmethod
    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        """
        Returns a dict: {'Group Name': [url1, url2, ...]}
        """
        pass

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Shared utility to extract video ID from URL."""
        if "youtube.com/watch" in url:
            match = re.search(r"[?&]v=([^&]+)", url)
            return match.group(1) if match else None
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "youtube.com/shorts/" in url:
            return url.split("shorts/")[1].split("?")[0]
        return None

    def _is_youtube_video(self, url: str) -> bool:
        """Shared utility to check if a URL is a valid video (not search/home)."""
        if not url:
            return False

        if "youtube.com" not in url and "youtu.be" not in url:
            return False

        if any(
            x in url
            for x in [
                "search_query=",
                "/results",
                "accounts.google",
                "google.com/settings",
            ]
        ):
            return False

        clean_check = url.replace("www.", "").replace("https://", "").strip("/")
        if clean_check == "youtube.com":
            return False

        if "/watch" in url or "/shorts/" in url or "youtu.be" in url:
            return True

        return False

    def _safe_read_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Copies a file to temp storage before reading to avoid lock errors."""
        from app_logging import log

        if not path.exists():
            return None

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)

        try:
            shutil.copy2(path, temp_path)
            with open(temp_path, "rb") as f:
                content = f.read()

            if content.startswith(b"mozLz40"):
                try:
                    decompressed = lz4.block.decompress(content[8:])
                    return json.loads(decompressed)
                except Exception as e:
                    log.debug(f"LZ4 Decompression failed: {e}")
                    return None
            else:
                try:
                    return json.loads(content.decode("utf-8"))
                except Exception:
                    return None
        except Exception as e:
            log.warning(f"Safe read failed for {path}: {e}")
            return None
        finally:
            if temp_path.exists():
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
