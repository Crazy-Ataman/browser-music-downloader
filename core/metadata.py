import re
from pathlib import Path
from typing import Dict, Type

import app_logging
from config import CLEANUP_PATTERNS


def _tag_frame_types() -> Dict[str, Type]:
    from mutagen.id3 import TALB, TIT2, TPE1, TPE2

    return {
        "TIT2": TIT2,
        "TPE1": TPE1,
        "TPE2": TPE2,
        "TALB": TALB,
    }


def sanitize_text(text: str) -> str:
    """Removes common YouTube junk text from titles/filenames."""
    if not text:
        return ""

    clean_text = text
    for pattern in CLEANUP_PATTERNS:
        clean_text = pattern.sub("", clean_text)

    # Remove trailing separators often left behind (e.g., "Song - " -> "Song")
    clean_text = re.sub(r"\s*[-|]\s*$", "", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if ".." in clean_text:
        clean_text = clean_text.replace("..", ".")

    return clean_text


def _sanitize_id3_text_frames(audio) -> None:
    """Apply sanitize_text to common ID3 text tags (title, artist, album)."""
    for key, frame_cls in _tag_frame_types().items():
        if key not in audio:
            continue
        original = str(audio[key].text[0])
        new_text = sanitize_text(original)
        if not new_text or new_text == original:
            continue
        audio.add(frame_cls(encoding=3, text=new_text))
        app_logging.log.info(
            "[METADATA] Cleaned %s: '%s' -> '%s'", key, original, new_text
        )


def clean_tags(filepath: Path) -> None:
    """
    Metadata cleaning for MP3s using Mutagen.
    Removes proprietary ffmpeg tags (TSSE, TENC) and comments (TXXX).
    Standardizes Year (TYER), cleans title/artist/album tags, removes TRCK.
    """
    from mutagen.id3 import ID3, TYER

    if not filepath.exists():
        return

    if filepath.suffix.lower() != ".mp3":
        return

    try:
        audio = ID3(filepath)
        found_year = None

        if "TDRC" in audio:
            found_year = str(audio["TDRC"].text[0])[:4]
        elif "TYER" in audio:
            found_year = str(audio["TYER"].text[0])[:4]

        search_text = ""
        for key in audio.keys():
            if key.startswith("TXXX:description") or key.startswith("COMM"):
                search_text += str(audio[key]) + "\n"

        if search_text:
            pattern = r"(?:℗|©|\(c\)|released\s*on|published\s*on|provided\s*to\s*youtube)[^0-9]*((?:19|20)\d{2})"
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                found_year = match.group(1)

        tags_to_remove = []

        if "TRCK" in audio:
            del audio["TRCK"]
        if "TDRC" in audio:
            del audio["TDRC"]
        if "TDAT" in audio:
            del audio["TDAT"]

        blacklist_start = ("TSSE", "TENC", "COMM", "USLT", "TDAT")
        blacklist_txxx = [
            "description",
            "synopsis",
            "purl",
            "comment",
            "producers",
            "handler",
            "major_brand",
            "minor_version",
            "compatible_brands",
        ]

        for key in list(audio.keys()):
            if key.startswith(blacklist_start):
                tags_to_remove.append(key)
                continue
            if key.startswith("TXXX"):
                desc = audio[key].desc.lower()
                if any(b in desc for b in blacklist_txxx):
                    tags_to_remove.append(key)

        for tag in tags_to_remove:
            if tag in audio:
                del audio[tag]

        if found_year:
            audio.add(TYER(encoding=3, text=found_year))

        _sanitize_id3_text_frames(audio)

        audio.save(v1=0, v2_version=3)
        app_logging.log.info("[CLEANER] Sanitized tags: %s", filepath.name)

    except Exception as e:
        app_logging.log.error("[CLEANER] Failed on %s: %s", filepath.name, e)
