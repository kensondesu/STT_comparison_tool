"""
Transcription endpoint tests — POST/GET/DELETE /api/transcribe

Tests validate:
- Start transcription with all / single method(s)
- Invalid method name → 400
- Invalid file_id → 404
- Job status polling lifecycle (pending → processing → completed)
- Results endpoint schema
- Results filtered by method query param
- Language parameter handling (null for auto-detect, explicit code)
- Delete job endpoint
"""

import asyncio

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

VALID_METHODS = [
    "azure_stt_batch",
    "azure_stt_fast",
    "mai_transcribe",
    "aoai_transcribe",
    "voxtral",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _upload_wav(client: AsyncClient, wav_bytes: bytes) -> str:
    """Upload a WAV file and return the file_id."""
    resp = await client.post(
        "/api/upload",
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    return resp.json()["file_id"]


async def _start_transcription(
    client: AsyncClient,
    file_id: str,
    methods: list[str] | None = None,
    language: str | None = None,
):
    """POST /api/transcribe and return the response."""
    payload: dict = {"file_id": file_id, "methods": methods or ["azure_stt_fast"]}
    if language is not None:
        payload["language"] = language
    return await client.post("/api/transcribe", json=payload)


# ---------------------------------------------------------------------------
# Start transcription
# ---------------------------------------------------------------------------


async def test_start_transcription_all_methods(client, wav_bytes, mock_all_services):
    """Starting a job with all 5 methods should return 202 with each method listed."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=VALID_METHODS)
    assert resp.status_code == 202, resp.text

    body = resp.json()
    assert "job_id" in body
    assert body["file_id"] == file_id
    assert set(body["methods"].keys()) == set(VALID_METHODS)
    assert "created_at" in body


async def test_start_transcription_single_method(client, wav_bytes, mock_all_services):
    """Starting a job with a single method should succeed."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    assert resp.status_code == 202

    body = resp.json()
    assert list(body["methods"].keys()) == ["azure_stt_fast"]


async def test_start_transcription_invalid_method(client, wav_bytes):
    """An invalid method name should return 400 or 422."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=["nonexistent_method"])
    assert resp.status_code in (400, 422)

    body = resp.json()
    assert "detail" in body


async def test_start_transcription_invalid_file_id(client):
    """A non-existent file_id should return 404."""
    resp = await _start_transcription(
        client,
        file_id="00000000-0000-0000-0000-000000000000",
        methods=["azure_stt_fast"],
    )
    assert resp.status_code == 404


async def test_start_transcription_empty_methods(client, wav_bytes):
    """An empty methods list should be rejected or accepted based on backend implementation."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=[])
    # Backend accepts empty methods list (creates job with no tasks)
    assert resp.status_code in (202, 400, 422), f"Expected 202/400/422, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Language parameter
# ---------------------------------------------------------------------------


async def test_language_explicit(client, wav_bytes, mock_all_services):
    """Explicit language code should be reflected in the job."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"], language="en-US")
    assert resp.status_code == 202
    assert resp.json()["language"] == "en-US"


async def test_language_null_auto_detect(client, wav_bytes, mock_all_services):
    """Omitting language should default to auto-detect (null)."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    assert resp.status_code == 202
    assert resp.json().get("language") is None


async def test_language_non_english(client, wav_bytes, mock_all_services):
    """Non-English language codes should be accepted."""
    file_id = await _upload_wav(client, wav_bytes)
    resp = await _start_transcription(client, file_id, methods=["mai_transcribe"], language="ja-JP")
    assert resp.status_code == 202
    assert resp.json()["language"] == "ja-JP"


# ---------------------------------------------------------------------------
# Job status polling
# ---------------------------------------------------------------------------


async def test_get_job_status(client, wav_bytes, mock_all_services):
    """GET /api/transcribe/{job_id} should return the job with its status."""
    file_id = await _upload_wav(client, wav_bytes)
    start_resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    job_id = start_resp.json()["job_id"]

    status_resp = await client.get(f"/api/transcribe/{job_id}")
    assert status_resp.status_code == 200

    body = status_resp.json()
    assert body["job_id"] == job_id
    assert body["file_id"] == file_id
    assert body["status"] in ("pending", "processing", "completed", "failed")
    assert "methods" in body
    assert "azure_stt_fast" in body["methods"]


async def test_get_job_status_not_found(client):
    """A non-existent job_id should return 404."""
    resp = await client.get("/api/transcribe/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_job_reaches_completed(client, wav_bytes, mock_all_services):
    """After mocked services finish, job status should eventually be 'completed'."""
    file_id = await _upload_wav(client, wav_bytes)
    start_resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    job_id = start_resp.json()["job_id"]

    # Give async tasks a moment to complete
    for _ in range(20):
        await asyncio.sleep(0.1)
        status_resp = await client.get(f"/api/transcribe/{job_id}")
        body = status_resp.json()
        if body["status"] in ("completed", "failed"):
            break

    assert body["status"] == "completed", f"Job did not complete: {body}"
    assert body["methods"]["azure_stt_fast"] == "completed"


# ---------------------------------------------------------------------------
# Results endpoint
# ---------------------------------------------------------------------------


async def test_get_results(client, wav_bytes, mock_all_services):
    """GET /api/transcribe/{job_id}/results should return transcription data."""
    file_id = await _upload_wav(client, wav_bytes)
    start_resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    job_id = start_resp.json()["job_id"]

    # Wait for completion
    for _ in range(20):
        await asyncio.sleep(0.1)
        s = await client.get(f"/api/transcribe/{job_id}")
        if s.json()["status"] in ("completed", "failed"):
            break

    results_resp = await client.get(f"/api/transcribe/{job_id}/results")
    assert results_resp.status_code == 200

    body = results_resp.json()
    assert body["job_id"] == job_id
    assert "results" in body

    method_result = body["results"]["azure_stt_fast"]
    assert method_result["status"] == "completed"
    assert isinstance(method_result["full_text"], str)
    assert len(method_result["full_text"]) > 0
    assert isinstance(method_result["segments"], list)
    assert len(method_result["segments"]) > 0

    seg = method_result["segments"][0]
    assert "start_time" in seg
    assert "end_time" in seg
    assert "text" in seg
    assert isinstance(seg["start_time"], (int, float))
    assert seg["end_time"] >= seg["start_time"]


async def test_get_results_filtered_by_method(client, wav_bytes, mock_all_services):
    """GET /api/transcribe/{job_id}/results?method=X should return only that method."""
    file_id = await _upload_wav(client, wav_bytes)
    start_resp = await _start_transcription(
        client, file_id, methods=["azure_stt_fast", "mai_transcribe"]
    )
    job_id = start_resp.json()["job_id"]

    for _ in range(20):
        await asyncio.sleep(0.1)
        s = await client.get(f"/api/transcribe/{job_id}")
        if s.json()["status"] in ("completed", "failed"):
            break

    resp = await client.get(f"/api/transcribe/{job_id}/results?method=azure_stt_fast")
    assert resp.status_code == 200

    body = resp.json()
    assert list(body["results"].keys()) == ["azure_stt_fast"]


async def test_get_results_not_found(client):
    """Results for non-existent job should return 404."""
    resp = await client.get("/api/transcribe/00000000-0000-0000-0000-000000000000/results")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete job
# ---------------------------------------------------------------------------


async def test_delete_job(client, wav_bytes, mock_all_services):
    """DELETE /api/transcribe/{job_id} should remove the job."""
    file_id = await _upload_wav(client, wav_bytes)
    start_resp = await _start_transcription(client, file_id, methods=["azure_stt_fast"])
    job_id = start_resp.json()["job_id"]

    del_resp = await client.delete(f"/api/transcribe/{job_id}")
    assert del_resp.status_code == 200
    assert job_id in del_resp.json().get("detail", "")

    # Subsequent GET should 404
    status_resp = await client.get(f"/api/transcribe/{job_id}")
    assert status_resp.status_code == 404


async def test_delete_job_not_found(client):
    """Deleting a non-existent job should return 404."""
    resp = await client.delete("/api/transcribe/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
