import os
import re
import platform
from pathlib import Path
from typing import Dict, List
from .base import BrowserBackend


class ChromeBrowser(BrowserBackend):
    @property
    def name(self) -> str:
        return "Google Chrome"

    def get_profiles(self) -> List[Path]:
        system = platform.system()
        base_path = None
        if system == "Windows":
            base_path = (
                Path(os.getenv("LOCALAPPDATA")) / "Google" / "Chrome" / "User Data"
            )
        elif system == "Darwin":
            base_path = (
                Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
            )
        elif system == "Linux":
            base_path = Path.home() / ".config" / "google-chrome"

        if not base_path or not base_path.exists():
            return []

        profiles = []
        if (base_path / "Default").exists():
            profiles.append(base_path / "Default")
        profiles.extend(list(base_path.glob("Profile *")))

        def get_pref_mtime(p):
            pref = p / "Preferences"
            return pref.stat().st_mtime if pref.exists() else 0

        return sorted(profiles, key=get_pref_mtime, reverse=True)

    def _get_active_session_urls(self, profile_path: Path) -> List[str]:
        """
        Scrapes the binary 'Current Session' (SNSS format) using Regex.
        Filters navigation history and duplicates.
        """
        from app_logging import log

        sessions_dir = profile_path / "Sessions"
        if not sessions_dir.exists():
            return []

        target_file = sessions_dir / "Current Session"

        if not target_file.exists() or target_file.stat().st_size == 0:
            session_files = list(sessions_dir.glob("Session_*"))
            if session_files:
                target_file = max(session_files, key=os.path.getmtime)
            else:
                return []

        final_urls = []
        seen_video_ids = set()
        url_pattern = re.compile(rb'(https?://[^\x00-\x20\x7f"<>|\^`{\}]+)')

        try:
            with open(target_file, "rb") as f:
                content = f.read()
                matches = url_pattern.findall(content)

                for match in reversed(matches):
                    try:
                        dec_url = match.decode("utf-8")

                        if self._is_youtube_video(dec_url):
                            vid_id = self._extract_video_id(dec_url)
                            if vid_id and vid_id not in seen_video_ids:
                                seen_video_ids.add(vid_id)
                                final_urls.append(dec_url)

                    except UnicodeDecodeError:
                        continue
        except Exception as e:
            log.warning(f"Could not read Chrome Session file: {e}")

        return final_urls

    def extract_groups(self, profile_path: Path) -> Dict[str, List[str]]:
        from app_logging import log

        organized_groups = {}

        active_urls = self._get_active_session_urls(profile_path)
        if active_urls:
            organized_groups["[Active Session] Open Tabs"] = active_urls

        bookmarks_path = profile_path / "Bookmarks"
        data = self._safe_read_json(bookmarks_path)

        if data:
            try:
                seen_bookmark_vids = set()

                def recurse_nodes(node, current_folder_name=None):
                    my_name = node.get("name", "")
                    if "children" in node:
                        next_group = (
                            my_name
                            if node.get("id") != "0"
                            and my_name
                            not in [
                                "Bookmarks bar",
                                "Other bookmarks",
                                "Mobile bookmarks",
                            ]
                            else current_folder_name
                        )
                        for child in node["children"]:
                            recurse_nodes(child, next_group)
                    elif "url" in node:
                        url = node["url"]
                        if self._is_youtube_video(url):
                            vid_id = self._extract_video_id(url)
                            if vid_id and vid_id not in seen_bookmark_vids:
                                seen_bookmark_vids.add(vid_id)
                                if current_folder_name:
                                    if current_folder_name not in organized_groups:
                                        organized_groups[current_folder_name] = []
                                    organized_groups[current_folder_name].append(url)

                roots = data.get("roots", {})
                for root_key in roots:
                    recurse_nodes(roots[root_key])
            except Exception as e:
                log.warning(f"Failed to parse Chrome bookmarks for {profile_path}: {e}")

        return organized_groups
