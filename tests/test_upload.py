"""
Upload endpoint tests — POST /api/upload

Tests validate:
- Successful upload of every accepted format (wav, mp3, flac, ogg, m4a, webm)
- Rejection of unsupported formats (txt, pdf, exe)
- Upload response schema (file_id, filename, size_bytes, duration_seconds, format)
- Empty file handling
- Missing file in request body
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

ACCEPTED_FORMATS = ["wav", "mp3", "flac", "ogg", "m4a", "webm"]
REJECTED_FORMATS = ["txt", "pdf", "exe", "py", "docx"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_file(client: AsyncClient, content: bytes, filename: str):
    """Return a coroutine that POSTs a file to /api/upload."""
    return client.post(
        "/api/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )


# ---------------------------------------------------------------------------
# Successful uploads
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", ACCEPTED_FORMATS)
async def test_upload_accepted_format(client, ext):
    """Each accepted audio format should return 200 with upload metadata."""
    from tests.conftest import _FORMAT_BYTES_MAP
    content = _FORMAT_BYTES_MAP[ext]()
    resp = await _upload_file(client, content, f"test_audio.{ext}")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert "file_id" in body
    assert body["filename"] == f"test_audio.{ext}"
    assert body["size_bytes"] > 0
    assert body["format"] == ext
    assert "uploaded_at" in body
    # duration_seconds may be None for non-wav stubs, but the key must exist
    assert "duration_seconds" in body


async def test_upload_wav_response_schema(client, wav_bytes):
    """Verify every field in the upload response matches the API contract."""
    resp = await _upload_file(client, wav_bytes, "recording.wav")
    assert resp.status_code == 200

    body = resp.json()
    required_keys = {"file_id", "filename", "size_bytes", "duration_seconds", "format", "uploaded_at"}
    assert required_keys.issubset(body.keys()), f"Missing keys: {required_keys - body.keys()}"

    assert isinstance(body["file_id"], str)
    assert len(body["file_id"]) > 0
    assert isinstance(body["size_bytes"], int)
    assert body["size_bytes"] == len(wav_bytes)
    assert body["format"] == "wav"


async def test_upload_mp3(client, mp3_bytes):
    """MP3 upload should succeed."""
    resp = await _upload_file(client, mp3_bytes, "song.mp3")
    assert resp.status_code == 200
    assert resp.json()["format"] == "mp3"


async def test_upload_preserves_original_filename(client, wav_bytes):
    """The response filename should match what was sent."""
    resp = await _upload_file(client, wav_bytes, "My Recording (final) v2.wav")
    assert resp.status_code == 200
    assert resp.json()["filename"] == "My Recording (final) v2.wav"


# ---------------------------------------------------------------------------
# Rejected formats
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", REJECTED_FORMATS)
async def test_upload_rejected_format(client, ext):
    """Non-audio formats should be rejected with 400."""
    content = b"not audio data"
    resp = await _upload_file(client, content, f"document.{ext}")
    assert resp.status_code == 400

    body = resp.json()
    assert "detail" in body
    # The error message should mention accepted formats
    assert any(fmt in body["detail"].lower() for fmt in ["wav", "mp3", "accepted", "unsupported"])


async def test_upload_no_extension(client):
    """A file with no extension should be rejected."""
    resp = await _upload_file(client, b"some data", "noextension")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_upload_empty_file(client, empty_bytes):
    """An empty (zero-byte) file should be rejected."""
    resp = await _upload_file(client, empty_bytes, "empty.wav")
    # Could be 400 (bad request) or 422 (unprocessable)
    assert resp.status_code in (400, 422), f"Expected 400/422, got {resp.status_code}: {resp.text}"


async def test_upload_missing_file_field(client):
    """A request without the 'file' field should fail."""
    resp = await client.post("/api/upload")
    assert resp.status_code == 422, "Missing file field should produce a validation error"


async def test_upload_returns_unique_file_ids(client, wav_bytes):
    """Two uploads of the same file should get different file_ids."""
    r1 = await _upload_file(client, wav_bytes, "same.wav")
    r2 = await _upload_file(client, wav_bytes, "same.wav")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["file_id"] != r2.json()["file_id"]


async def test_upload_file_persisted_to_disk(client, wav_bytes, upload_dir):
    """The uploaded file should actually exist in the upload directory."""
    resp = await _upload_file(client, wav_bytes, "check_disk.wav")
    assert resp.status_code == 200

    file_id = resp.json()["file_id"]
    # File should exist somewhere under the upload dir
    matches = list(upload_dir.glob(f"*{file_id}*"))
    assert len(matches) >= 1, f"No file matching file_id {file_id} found in {upload_dir}"
