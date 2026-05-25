import os
import re
from pathlib import Path
from typing import Dict, Tuple, Type

import app_logging
from config import CLEANUP_PATTERNS

_INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_UPLOADER_HINTS = re.compile(
    r"official|канал|channel|records|vevo|entertainment|topic|release",
    re.IGNORECASE,
)
_CHANNEL_SUFFIX_PATTERNS = [
    re.compile(r"\s+официальный\s+канал\s*$", re.IGNORECASE),
    re.compile(r"\s+official\s+channel\s*$", re.IGNORECASE),
    re.compile(r"\s+официальный\s*$", re.IGNORECASE),
]


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


def safe_filename_stem(text: str) -> str:
    """Strip characters invalid on Windows filenames."""
    if not text:
        return ""
    clean = _INVALID_WIN_CHARS.sub("", text)
    return clean.strip().rstrip(". ")


def normalize_artist_name(artist: str) -> str:
    """Drop YouTube channel suffixes like 'официальный канал' from the artist tag."""
    name = sanitize_text(artist)
    for pattern in _CHANNEL_SUFFIX_PATTERNS:
        name = pattern.sub("", name).strip()
    return name


def _is_likely_uploader(tag_artist: str, embedded_artist: str) -> bool:
    """Guess whether TPE1 is a YouTube channel, not the musical artist."""
    if not tag_artist or not embedded_artist:
        return False
    if tag_artist.casefold() == embedded_artist.casefold():
        return False
    if _UPLOADER_HINTS.search(tag_artist):
        return True
    # e.g. StarPro vs Смысловые Галлюцинации — names differ and title carries the band
    return True


def _split_embedded_artist_title(title: str) -> Tuple[str, str]:
    """Parse 'Artist - Song' from a combined title string."""
    parts = re.split(r"\s[-–—]\s", title, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    artist = sanitize_text(parts[0].strip())
    song = sanitize_text(parts[1].strip())
    return artist, song


def resolve_artist_title(artist: str, title: str) -> Tuple[str, str]:
    """
    Pick the best artist and song name for filenames/tags.
    Prefers an embedded 'Artist - Song' in TIT2 when TPE1 looks like a channel.
    """
    artist = normalize_artist_name(artist)
    title = sanitize_text(title)

    embedded_artist, embedded_song = _split_embedded_artist_title(title)
    if embedded_artist and embedded_song:
        if not artist or _is_likely_uploader(artist, embedded_artist):
            return embedded_artist, embedded_song
        return artist, embedded_song

    if artist:
        return artist, strip_artist_from_title(artist, title) or title
    return "", title


def strip_artist_from_title(artist: str, title: str) -> str:
    """Remove a leading 'Artist -' or 'Artist-Song' prefix already present in the title tag."""
    title = title.strip()
    if not title:
        return title

    for name in (normalize_artist_name(artist), sanitize_text(artist)):
        if not name:
            continue

        pattern = re.compile(
            r"^\s*" + re.escape(name) + r"\s*[-–—]\s*",
            re.IGNORECASE,
        )
        stripped = pattern.sub("", title, count=1).strip()
        if stripped and stripped != title:
            return stripped

        pattern_tight = re.compile(
            r"^\s*" + re.escape(name) + r"\s*[-–—]",
            re.IGNORECASE,
        )
        stripped = pattern_tight.sub("", title, count=1).strip()
        if stripped and stripped != title:
            return stripped

        if title.casefold().startswith(name.casefold()):
            remainder = title[len(name) :].lstrip()
            if remainder[:1] in "-–—":
                return remainder[1:].strip()

    return title


def artist_title_stem(artist: str, title: str) -> str:
    """Build 'Artist - Title' stem (Anamnez-style spacing)."""
    artist_name, song_name = resolve_artist_title(artist, title)
    artist_clean = safe_filename_stem(artist_name)
    title_clean = safe_filename_stem(song_name)
    if artist_clean and title_clean:
        return f"{artist_clean} - {title_clean}"
    return safe_filename_stem(title_clean or artist_clean)


def _read_id3_artist_title(filepath: Path) -> Tuple[str, str]:
    from mutagen.id3 import ID3

    try:
        audio = ID3(filepath)
    except Exception:
        return "", ""

    artist = ""
    title = ""
    if "TPE1" in audio:
        artist = str(audio["TPE1"].text[0])
    elif "TPE2" in audio:
        artist = str(audio["TPE2"].text[0])
    if "TIT2" in audio:
        title = str(audio["TIT2"].text[0])
    return sanitize_text(artist), sanitize_text(title)


def _apply_rename(filepath: Path, stem: str, index: int) -> Path:
    new_path = filepath.parent / f"{stem}{filepath.suffix}"
    if new_path.exists() and new_path.resolve() != filepath.resolve():
        new_path = filepath.parent / f"{stem}_{index}{filepath.suffix}"
    try:
        os.rename(filepath, new_path)
        app_logging.log.info("[RENAME] '%s' -> '%s'", filepath.name, new_path.name)
        return new_path
    except OSError as e:
        app_logging.log.error("Could not rename %s: %s", filepath.name, e)
        return filepath


def rename_from_tags(filepath: Path, index: int = 0) -> Path:
    """Rename MP3 to 'Artist - Title' when both ID3 tags are present."""
    if not filepath.exists() or filepath.suffix.lower() != ".mp3":
        return filepath

    artist, title = _read_id3_artist_title(filepath)
    if not artist or not title:
        clean_stem = safe_filename_stem(sanitize_text(filepath.stem))
        if clean_stem and clean_stem != filepath.stem:
            return _apply_rename(filepath, clean_stem, index)
        return filepath

    target_stem = artist_title_stem(artist, title)
    if not target_stem or filepath.stem.casefold() == target_stem.casefold():
        return filepath

    return _apply_rename(filepath, target_stem, index)


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

        from mutagen.id3 import TIT2, TPE1

        tag_artist = str(audio["TPE1"].text[0]) if "TPE1" in audio else ""
        tag_title = str(audio["TIT2"].text[0]) if "TIT2" in audio else ""
        resolved_artist, resolved_title = resolve_artist_title(tag_artist, tag_title)
        if resolved_artist and resolved_artist != tag_artist:
            audio.add(TPE1(encoding=3, text=resolved_artist))
            app_logging.log.info(
                "[METADATA] Artist '%s' -> '%s'", tag_artist, resolved_artist
            )
        if resolved_title and resolved_title != tag_title:
            audio.add(TIT2(encoding=3, text=resolved_title))
            app_logging.log.info(
                "[METADATA] Title '%s' -> '%s'", tag_title, resolved_title
            )

        audio.save(v1=0, v2_version=3)
        app_logging.log.info("[CLEANER] Sanitized tags: %s", filepath.name)

    except Exception as e:
        app_logging.log.error("[CLEANER] Failed on %s: %s", filepath.name, e)
