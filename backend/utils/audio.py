"""Audio file validation and metadata extraction."""

import asyncio
import io
import json
import logging
import shutil
from pathlib import Path

from mutagen import File as MutagenFile, MutagenError

from backend.config import settings

logger = logging.getLogger(__name__)

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


# Formats that all transcription services can handle natively
_COMPATIBLE_FORMATS = {"wav", "mp3", "flac", "ogg", "webm"}


async def ensure_compatible_format(file_path: Path) -> Path:
    """Probe the audio file with ffprobe and convert to WAV if needed.

    Returns the path to the (possibly converted) file.
    If conversion happened, the original file is deleted and replaced.
    """
    from backend.config import settings

    # Step 1: Probe with ffprobe
    probe_cmd = [
        settings.ffprobe_path, "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(file_path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
    except FileNotFoundError:
        logger.warning("ffprobe not found at %s — skipping format check", settings.ffprobe_path)
        return file_path  # graceful degradation: skip if ffmpeg not installed

    if proc.returncode != 0:
        logger.error("ffprobe failed: %s", stderr.decode()[:500])
        raise ValueError("Unable to read audio file — it may be corrupt")

    info = json.loads(stdout)
    format_name = info.get("format", {}).get("format_name", "")

    # Step 2: Check if already compatible
    # ffprobe format_name examples: "wav", "mp3", "flac", "ogg",
    # "matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2"
    compatible = False
    for fmt in _COMPATIBLE_FORMATS:
        if fmt in format_name.lower():
            compatible = True
            break

    if compatible:
        logger.info("Audio format '%s' is compatible — no conversion needed", format_name)
        return file_path

    # Step 3: Convert to WAV
    logger.info("Converting '%s' (format: %s) to WAV", file_path.name, format_name)
    output_path = file_path.with_suffix(".wav")
    # If the file already has .wav extension, use a temp name
    if output_path == file_path:
        output_path = file_path.with_name(file_path.stem + "_converted.wav")

    convert_cmd = [
        settings.ffmpeg_path, "-i", str(file_path),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-y",  # overwrite
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *convert_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg conversion failed: %s", stderr.decode()[:500])
        raise ValueError(f"Failed to convert audio: {stderr.decode()[:200]}")

    # Replace original with converted file
    if output_path != file_path:
        file_path.unlink(missing_ok=True)
        final_path = file_path.with_suffix(".wav")
        if final_path != output_path:
            shutil.move(str(output_path), str(final_path))
            output_path = final_path

    logger.info("Converted to WAV: %s (%.1f KB)", output_path.name, output_path.stat().st_size / 1024)
    return output_path


def get_duration(file_path: str | Path) -> float | None:
    """Return audio duration in seconds using mutagen, or None on failure."""
    try:
        audio = MutagenFile(str(file_path))
        if audio is not None and audio.info is not None:
            return round(audio.info.length, 2)
    except (MutagenError, Exception):
        pass
    return None
