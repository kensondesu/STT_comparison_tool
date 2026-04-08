"""Upload router — POST /api/upload and GET /api/audio/{file_id}."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from backend.config import settings
from backend.models.schemas import UploadResponse
from backend.utils.audio import validate_extension, validate_header, get_duration
from backend.utils.storage import save_file, find_file, get_mime_type

router = APIRouter(prefix="/api", tags=["upload"])

# In-memory registry: file_id -> UploadResponse metadata
file_registry: dict[str, UploadResponse] = {}


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(file: UploadFile = File(...)):
    """Upload an audio file for later transcription."""
    filename = file.filename or "unknown"
    ext = validate_extension(filename)
    if ext is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format. Accepted: {', '.join(settings.accepted_formats)}",
        )

    data = await file.read()

    if len(data) > settings.max_file_size_bytes:
        raise HTTPException(status_code=413, detail="File size exceeds 300MB limit")

    if not validate_header(data, ext):
        raise HTTPException(
            status_code=400,
            detail=f"File header does not match expected format for .{ext}",
        )

    file_id = str(uuid.uuid4())
    path = save_file(file_id, ext, data)

    duration = get_duration(path)

    response = UploadResponse(
        file_id=file_id,
        filename=filename,
        size_bytes=len(data),
        duration_seconds=duration,
        format=ext,
        uploaded_at=datetime.now(timezone.utc),
    )
    file_registry[file_id] = response
    return response


@router.get("/audio/{file_id}")
async def stream_audio(file_id: str):
    """Stream uploaded audio file for playback."""
    path = find_file(file_id)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")

    ext = path.suffix.lstrip(".").lower()
    return FileResponse(
        path=str(path),
        media_type=get_mime_type(ext),
        filename=path.name,
    )
