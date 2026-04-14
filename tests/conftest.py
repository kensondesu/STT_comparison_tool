"""
Pytest fixtures for MAI_transcribe backend tests.

Provides:
- FastAPI TestClient (async via httpx)
- Temporary upload directory
- Mock audio files (wav, mp3, various sizes)
- Mock transcription service fixtures (no real Azure/OpenAI calls)

These tests are TDD-first: they define the expected behaviour from
ARCHITECTURE.md and API_CONTRACT.md.  When the backend modules are not
yet implemented the test suite will skip or fail with clear import errors
telling the developer exactly what to build.
"""

import io
import os
import struct
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Global safety net — prevent DefaultAzureCredential from real auth
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _block_azure_credentials(monkeypatch):
    """Ensure no test accidentally triggers real Azure authentication.

    Sets fake API keys on the settings singleton so every service takes the
    key-based auth path.  Also mocks DefaultAzureCredential and the shared
    token helper as a belt-and-suspenders safety net.
    """
    try:
        from backend import config

        # Fake keys → services always take the key/connection-string path
        monkeypatch.setattr(config.settings, "azure_speech_key", "fake-test-key")
        monkeypatch.setattr(config.settings, "azure_speech_region", "eastus")
        monkeypatch.setattr(
            config.settings,
            "azure_storage_connection_string",
            "DefaultEndpointsProtocol=https;AccountName=faketest;AccountKey=ZmFrZWtleQ==;",
        )
        monkeypatch.setattr(config.settings, "azure_storage_container_name", "test-container")
        monkeypatch.setattr(config.settings, "azure_openai_api_key", "fake-test-key")
        monkeypatch.setattr(config.settings, "azure_openai_endpoint", "https://fake.openai.azure.com/")
        monkeypatch.setattr(config.settings, "azure_openai_deployment_name", "gpt-4o-transcribe")
        monkeypatch.setattr(config.settings, "whisper_speech_key", "fake-test-key")
        monkeypatch.setattr(config.settings, "whisper_speech_region", "eastus")
        monkeypatch.setattr(config.settings, "whisper_speech_endpoint", "https://fake.whisper.azure.com")
        monkeypatch.setattr(config.settings, "voxtral_endpoint_key", "fake-test-key")
        monkeypatch.setattr(config.settings, "voxtral_endpoint_url", "https://fake.voxtral.endpoint/")

        # Safety net: mock the shared token helper so it never creates a credential
        monkeypatch.setattr(config, "get_cognitive_services_token", lambda: "fake-token")

        # Safety net: mock DefaultAzureCredential in service modules
        mock_cred = MagicMock()
        mock_cred.get_token.return_value = MagicMock(token="fake-token", expires_on=9999999999)
        try:
            import backend.services.azure_stt_batch as _batch_mod
            monkeypatch.setattr(_batch_mod, "DefaultAzureCredential", lambda: mock_cred)
        except (ImportError, AttributeError):
            pass
    except ImportError:
        pass

# ---------------------------------------------------------------------------
# Schema stubs — used ONLY until the real backend models exist.
# These mirror the contract in ARCHITECTURE.md so tests can reference the
# types before production code is written.  Once backend.models.schemas
# provides Segment and TranscriptionResult, they take precedence.
# ---------------------------------------------------------------------------
try:
    from backend.models.schemas import Segment
except ImportError:
    from pydantic import BaseModel

    class Segment(BaseModel):
        start_time: float
        end_time: float
        text: str

try:
    from backend.services.base import TranscriptionResult
except ImportError:
    from pydantic import BaseModel as _BaseModel
    from typing import Optional

    class TranscriptionResult(_BaseModel):
        full_text: str
        segments: list = []
        duration_seconds: Optional[float] = None
        detected_language: Optional[str] = None

# ---------------------------------------------------------------------------
# FastAPI app — import or skip
# ---------------------------------------------------------------------------
try:
    from backend.main import app as _app
except ImportError:
    _app = None


# ---------------------------------------------------------------------------
# App / client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client(upload_dir):
    """Async test client wired to the FastAPI app."""
    if _app is None:
        pytest.skip("backend.main.app not yet implemented")
    transport = ASGITransport(app=_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _clear_app_state():
    """Reset in-memory state between tests so they don't leak."""
    if _app is None:
        yield
        return
    # Clear any in-memory stores the app uses (files_store, jobs_store)
    for attr in ("files_store", "jobs_store"):
        store = getattr(_app.state, attr, None)
        if store is not None and isinstance(store, dict):
            store.clear()
    yield


# ---------------------------------------------------------------------------
# Upload directory
# ---------------------------------------------------------------------------


@pytest.fixture
def upload_dir(monkeypatch):
    """Create a temporary upload directory scoped to this test and patch config."""
    test_dir = Path(__file__).resolve().parent / "_test_uploads" / uuid.uuid4().hex[:8]
    test_dir.mkdir(parents=True, exist_ok=True)

    # Patch wherever the backend reads its upload path
    monkeypatch.setenv("UPLOAD_DIR", str(test_dir))
    try:
        from backend import config
        if hasattr(config, "settings"):
            monkeypatch.setattr(config.settings, "upload_dir", test_dir, raising=False)
        if hasattr(config, "UPLOAD_DIR"):
            monkeypatch.setattr(config, "UPLOAD_DIR", str(test_dir), raising=False)
    except Exception:
        pass

    yield test_dir

    # Cleanup
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Audio file factories
# ---------------------------------------------------------------------------


def _make_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Generate a minimal valid WAV file in memory."""
    bits_per_sample = 16
    num_samples = int(sample_rate * duration_sec)
    data_size = num_samples * channels * (bits_per_sample // 8)
    # RIFF header
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    # fmt chunk
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))  # chunk size
    buf.write(struct.pack("<H", 1))   # PCM
    buf.write(struct.pack("<H", channels))
    buf.write(struct.pack("<I", sample_rate))
    buf.write(struct.pack("<I", sample_rate * channels * bits_per_sample // 8))
    buf.write(struct.pack("<H", channels * bits_per_sample // 8))
    buf.write(struct.pack("<H", bits_per_sample))
    # data chunk — silence
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(b"\x00" * data_size)
    return buf.getvalue()


def _make_mp3_bytes() -> bytes:
    """Minimal bytes with an ID3 tag header — not playable, but valid enough for upload tests."""
    # ID3v2 header: "ID3" + version + flags + size
    return b"ID3" + b"\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 1013


def _make_ogg_bytes() -> bytes:
    """Minimal OGG container header bytes."""
    # OGG capture pattern
    return b"OggS" + b"\x00" * 1020


def _make_flac_bytes() -> bytes:
    """Minimal FLAC stream marker."""
    return b"fLaC" + b"\x00" * 1020


def _make_m4a_bytes() -> bytes:
    """Minimal M4A/MP4 container header (ftyp box at offset 4)."""
    # size (4 bytes big-endian) + 'ftyp' + brand + padding
    return b"\x00\x00\x00\x20" + b"ftyp" + b"M4A " + b"\x00" * 1012


def _make_webm_bytes() -> bytes:
    """Minimal WebM/EBML header."""
    return b"\x1a\x45\xdf\xa3" + b"\x00" * 1020


# Map format extension to byte-generator for parametrized tests
_FORMAT_BYTES_MAP = {
    "wav": _make_wav_bytes,
    "mp3": _make_mp3_bytes,
    "flac": _make_flac_bytes,
    "ogg": _make_ogg_bytes,
    "m4a": _make_m4a_bytes,
    "webm": _make_webm_bytes,
}


@pytest.fixture
def wav_bytes():
    return _make_wav_bytes()


@pytest.fixture
def mp3_bytes():
    return _make_mp3_bytes()


@pytest.fixture
def ogg_bytes():
    return _make_ogg_bytes()


@pytest.fixture
def flac_bytes():
    return _make_flac_bytes()


@pytest.fixture
def m4a_bytes():
    return _make_m4a_bytes()


@pytest.fixture
def webm_bytes():
    return _make_webm_bytes()


@pytest.fixture
def large_wav_bytes():
    """A 5-second WAV — larger but still small for tests."""
    return _make_wav_bytes(duration_sec=5.0)


@pytest.fixture
def empty_bytes():
    """Zero-length file content."""
    return b""


# ---------------------------------------------------------------------------
# Mock transcription results
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_transcription_result():
    """A realistic transcription result usable as a return value for mocked services."""
    return TranscriptionResult(
        full_text="Hello, welcome to the demo. This is a transcription test.",
        segments=[
            Segment(start_time=0.0, end_time=2.54, text="Hello, welcome to the demo."),
            Segment(start_time=2.54, end_time=5.12, text="This is a transcription test."),
        ],
        detected_language="en-US",
    )


@pytest.fixture
def mock_all_services(mock_transcription_result):
    """Patch every transcription service so no real API calls are made.

    Returns a dict mapping method name → its AsyncMock so tests can inspect calls.
    """
    service_paths = {
        "azure_stt_batch": "backend.services.azure_stt_batch.AzureSttBatchService.transcribe",
        "azure_stt_fast": "backend.services.azure_stt_fast.AzureSttFastService.transcribe",
        "mai_transcribe": "backend.services.mai_transcribe.MaiTranscribeService.transcribe",
        "aoai_transcribe": "backend.services.aoai_transcribe.AoaiTranscribeService.transcribe",
        "voxtral": "backend.services.voxtral_transcribe.VoxtralTranscribeService.transcribe",
    }
    mocks = {}
    patchers = []
    for name, path in service_paths.items():
        m = AsyncMock(return_value=mock_transcription_result)
        p = patch(path, m)
        p.start()
        patchers.append(p)
        mocks[name] = m

    yield mocks

    for p in patchers:
        p.stop()
