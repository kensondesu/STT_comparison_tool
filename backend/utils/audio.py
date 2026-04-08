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
    """Basic magic-byte check. Returns True if the header looks plausible."""
    if len(data) < 12:
        return False

    if ext == "wav":
        return data[:4] == b"RIFF"
    if ext == "mp3":
        # ID3v2 tag header
        if data[:3] == b"ID3":
            return True
        # MPEG sync word: 11 set bits = 0xFF followed by 0xE0+ mask
        if data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
            return True
        return False
    if ext == "flac":
        return data[:4] == b"fLaC"
    if ext == "ogg":
        return data[:4] == b"OggS"
    if ext == "m4a":
        return data[4:8] == b"ftyp" or data[:3] == b"\x00\x00\x00"
    if ext == "webm":
        return data[:4] == b"\x1a\x45\xdf\xa3"

    # Unknown extension — passed extension check so allow it
    return True


def get_duration(file_path: str | Path) -> float | None:
    """Return audio duration in seconds using mutagen, or None on failure."""
    try:
        audio = MutagenFile(str(file_path))
        if audio is not None and audio.info is not None:
            return round(audio.info.length, 2)
    except (MutagenError, Exception):
        pass
    return None
