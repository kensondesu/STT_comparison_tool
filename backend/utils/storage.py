"""Local file storage helpers."""

import os
from pathlib import Path

from backend.config import settings

MIME_MAP: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
    "webm": "audio/webm",
}


def ensure_upload_dir() -> Path:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings.upload_dir


def save_file(file_id: str, ext: str, data: bytes) -> Path:
    """Save uploaded bytes to uploads/{file_id}.{ext}. Returns the full path."""
    dest = ensure_upload_dir() / f"{file_id}.{ext}"
    dest.write_bytes(data)
    return dest


def find_file(file_id: str) -> Path | None:
    """Find the stored file for a given file_id (any extension). Returns path or None."""
    upload_dir = settings.upload_dir
    if not upload_dir.exists():
        return None
    for entry in upload_dir.iterdir():
        if entry.stem == file_id and entry.is_file():
            return entry
    return None


def delete_file(file_id: str) -> bool:
    """Delete the stored file. Returns True if a file was deleted."""
    path = find_file(file_id)
    if path and path.exists():
        path.unlink()
        return True
    return False


def get_mime_type(ext: str) -> str:
    return MIME_MAP.get(ext.lower(), "application/octet-stream")
