import os
import platform
from pathlib import Path
from typing import Dict, List
from .base import BrowserBackend


class FirefoxBrowser(BrowserBackend):
    @property
    def name(self) -> str:
        return "Mozilla Firefox"

    def get_profiles(self) -> List[Path]:
        """Locates Firefox profiles (Standard, Snap, Flatpak)."""
        system = platform.system()
        potential_base_paths = []

        if system == "Windows":
            potential_base_paths.append(
                Path(os.getenv("APPDATA")) / "Mozilla" / "Firefox" / "Profiles"
            )
        elif system == "Darwin":
            potential_base_paths.append(
                Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
            )
        elif system == "Linux":
            potential_base_paths.append(Path.home() / ".mozilla" / "firefox")
            potential_base_paths.append(
                Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
            )
            potential_base_paths.append(
                Path.home()
                / ".var"
                / "app"
                / "org.mozilla.firefox"
                / ".mozilla"
                / "firefox"
            )

        valid_profiles = []
        for base in potential_base_paths:
            if base.exists():
                valid_profiles.extend([p for p in base.glob("*.*") if p.is_dir()])

        if valid_profiles:
            return sorted(
                valid_profiles, key=lambda p: os.path.getmtime(p), reverse=True
            )
        return []

    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        """Reads sessionstore/recovery.jsonlz4 to find active Tab Groups."""
        files = [
            profile_path / "sessionstore-backups" / "recovery.jsonlz4",
            profile_path / "sessionstore-backups" / "previous.jsonlz4",
            profile_path / "sessionstore.jsonlz4",
        ]

        json_data = None
        for f in files:
            json_data = self._safe_read_json(f)
            if json_data:
                break

        if not json_data:
            return {}

        organized_groups = {}
        seen_video_ids = set()

        if "windows" not in json_data:
            return {}

        for window in json_data["windows"]:
            group_metadata = {}
            raw_groups = window.get("groups", [])

            for g in raw_groups:
                g_id = g.get("id")
                g_title = g.get("title") or g.get("name") or "Untitled Group"
                if g_id:
                    group_metadata[g_id] = g_title

            if not group_metadata:
                continue

            for tab in window.get("tabs", []):
                group_id = tab.get("groupId")
                if group_id:
                    group_id = str(group_id)

                if not group_id or group_id not in group_metadata:
                    continue

                entries = tab.get("entries", [])
                if not entries:
                    continue

                active_idx = tab.get("index", 1) - 1
                if 0 <= active_idx < len(entries):
                    url = entries[active_idx].get("url", "")

                    if self._is_youtube_video(url):
                        vid_id = self._extract_video_id(url)

                        if vid_id and vid_id not in seen_video_ids:
                            seen_video_ids.add(vid_id)
                            group_name = group_metadata[group_id]
                            if group_name not in organized_groups:
                                organized_groups[group_name] = []
                            organized_groups[group_name].append(url)

        return organized_groups
