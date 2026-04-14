"""Audio file validation and metadata extraction."""

import io
from pathlib import Path

from mutagen import File as MutagenFile, MutagenError

from backend.config import settings

# Magic bytes for quick header validation
_MAGIC = {
    "wav": b"RIFF",
    "mp3": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    "flac": b"fLaC",
    "ogg": b"OggS",
    "m4a": [b"ftyp", b"\x00\x00\x00"],  # offset 4 for ftyp
    "webm": b"\x1a\x45\xdf\xa3",
}


def validate_extension(filename: str) -> str | None:
    """Return lowercase extension without dot if valid, else None."""
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext in settings.accepted_formats:
        return ext
    return None


def validate_header(data: bytes, ext: str) -> bool:
    """Basic magic-byte check. Returns True if the header looks plausible for any supported format.

    Some files have mismatched extensions (e.g., a .wav that is actually an
    MP4 container).  We accept the file as long as its header matches *any*
    supported audio format.
    """
    if len(data) < 12:
        return False

    # Check all known audio signatures regardless of extension
    # RIFF/WAV
    if data[:4] == b"RIFF":
        return True
    # MP3: ID3v2 tag or MPEG sync word
    if data[:3] == b"ID3":
        return True
    if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return True
    # FLAC
    if data[:4] == b"fLaC":
        return True
    # OGG
    if data[:4] == b"OggS":
        return True
    # M4A / MP4 (ftyp box at offset 4)
    if data[4:8] == b"ftyp":
        return True
    # WebM / EBML
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return True

    return False


def get_duration(file_path: str | Path) -> float | None:
    """Return audio duration in seconds using mutagen, or None on failure."""
    try:
        audio = MutagenFile(str(file_path))
        if audio is not None and audio.info is not None:
            return round(audio.info.length, 2)
    except (MutagenError, Exception):
        pass
    return None
