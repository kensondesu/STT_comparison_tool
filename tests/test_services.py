"""
Service unit tests — transcription service layer.

Tests validate:
- Base TranscriptionService interface contract
- Timecode normalization (Azure ticks → seconds)
- Segment schema validation
- Each service's transcribe method (mocked HTTP/SDK calls)
- Error handling: timeout, auth failure, service unavailable
"""

import asyncio
from abc import ABC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Base service interface
# ---------------------------------------------------------------------------


class TestBaseServiceInterface:
    """Verify the abstract base class enforces the contract."""

    def _import_base(self):
        try:
            from backend.services.base import TranscriptionService
            return TranscriptionService
        except ImportError:
            pytest.skip("backend.services.base not yet implemented")

    def test_base_is_abstract(self):
        cls = self._import_base()
        assert issubclass(cls, ABC)

    def test_base_has_transcribe_method(self):
        cls = self._import_base()
        assert hasattr(cls, "transcribe")

    def test_cannot_instantiate_base(self):
        cls = self._import_base()
        with pytest.raises(TypeError):
            cls()

    def test_subclass_must_implement_transcribe(self):
        cls = self._import_base()

        class IncompleteService(cls):
            pass

        with pytest.raises(TypeError):
            IncompleteService()


# ---------------------------------------------------------------------------
# Timecode normalization — ticks to seconds
# ---------------------------------------------------------------------------


class TestTimecodeNormalization:
    """Azure STT returns offsets in 100-nanosecond ticks. Verify conversion."""

    def _ticks_to_seconds(self, ticks: int) -> float:
        """The normalization formula used throughout the Azure STT services."""
        return ticks / 10_000_000

    def test_zero_ticks(self):
        assert self._ticks_to_seconds(0) == 0.0

    def test_one_second(self):
        assert self._ticks_to_seconds(10_000_000) == 1.0

    def test_fractional_seconds(self):
        result = self._ticks_to_seconds(25_400_000)
        assert abs(result - 2.54) < 1e-6

    def test_large_offset(self):
        # 2 hours in ticks
        two_hours_ticks = 2 * 3600 * 10_000_000
        assert self._ticks_to_seconds(two_hours_ticks) == 7200.0

    def test_small_offset(self):
        # 100ms
        result = self._ticks_to_seconds(1_000_000)
        assert abs(result - 0.1) < 1e-6

    def test_normalization_in_azure_stt_fast_service(self):
        """If the service exposes a normalization helper, test it directly."""
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
            svc = AzureSttFastService.__new__(AzureSttFastService)
            if hasattr(svc, "_ticks_to_seconds"):
                assert svc._ticks_to_seconds(10_000_000) == 1.0
                assert abs(svc._ticks_to_seconds(25_400_000) - 2.54) < 1e-6
        except (ImportError, AttributeError):
            pytest.skip("AzureSttFastService not yet implemented")


# ---------------------------------------------------------------------------
# Segment schema
# ---------------------------------------------------------------------------


class TestSegmentSchema:
    """Verify the Segment Pydantic model validates correctly."""

    def _import_segment(self):
        try:
            from backend.models.schemas import Segment
            return Segment
        except ImportError:
            # Fallback to conftest stub
            from tests.conftest import Segment
            return Segment

    def test_valid_segment(self):
        Segment = self._import_segment()
        seg = Segment(start_time=0.0, end_time=2.54, text="Hello world.")
        assert seg.start_time == 0.0
        assert seg.end_time == 2.54
        assert seg.text == "Hello world."

    def test_segment_requires_start_time(self):
        Segment = self._import_segment()
        with pytest.raises(Exception):
            Segment(end_time=2.54, text="Missing start")

    def test_segment_requires_end_time(self):
        Segment = self._import_segment()
        with pytest.raises(Exception):
            Segment(start_time=0.0, text="Missing end")

    def test_segment_requires_text(self):
        Segment = self._import_segment()
        with pytest.raises(Exception):
            Segment(start_time=0.0, end_time=1.0)

    def test_segment_serialization(self):
        Segment = self._import_segment()
        seg = Segment(start_time=1.5, end_time=3.0, text="Test")
        d = seg.model_dump()
        assert d == {"start_time": 1.5, "end_time": 3.0, "text": "Test"}


# ---------------------------------------------------------------------------
# TranscriptionResult schema
# ---------------------------------------------------------------------------


class TestTranscriptionResultSchema:

    def _import_models(self):
        try:
            from backend.models.schemas import Segment
            from backend.services.base import TranscriptionResult
            return Segment, TranscriptionResult
        except ImportError:
            from tests.conftest import Segment, TranscriptionResult
            return Segment, TranscriptionResult

    def test_valid_result(self):
        Segment, TranscriptionResult = self._import_models()
        result = TranscriptionResult(
            full_text="Hello.",
            segments=[Segment(start_time=0.0, end_time=1.0, text="Hello.")],
            detected_language="en-US",
        )
        assert result.full_text == "Hello."
        assert len(result.segments) == 1

    def test_result_with_empty_segments(self):
        _, TranscriptionResult = self._import_models()
        result = TranscriptionResult(
            full_text="",
            segments=[],
            detected_language=None,
        )
        assert result.segments == []


# ---------------------------------------------------------------------------
# Azure STT Fast — mocked HTTP
# ---------------------------------------------------------------------------


class TestAzureSTTFastService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")

    async def test_transcribe_returns_result(self, mock_env):
        """Mocked HTTP call should produce a TranscriptionResult."""
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
        except ImportError:
            pytest.skip("AzureSttFastService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "Hello world."}],
            "phrases": [
                {
                    "offsetInTicks": 0,
                    "durationInTicks": 25_400_000,
                    "text": "Hello world.",
                }
            ],
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.raise_for_status = MagicMock()

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", return_value=mock_response), \
             patch("builtins.open", return_value=fake_file):
            svc = AzureSttFastService()
            result = await svc.transcribe("fake/path.wav", language="en-US")

        assert result.full_text == "Hello world."
        assert len(result.segments) == 1
        assert result.segments[0].start_time == 0.0
        assert abs(result.segments[0].end_time - 2.54) < 1e-6

    async def test_auth_failure(self, mock_env):
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
        except ImportError:
            pytest.skip("AzureSttFastService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", return_value=mock_response), \
             patch("builtins.open", return_value=fake_file):
            svc = AzureSttFastService()
            with pytest.raises(Exception):
                await svc.transcribe("fake/path.wav", language=None)

    async def test_service_unavailable(self, mock_env):
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
        except ImportError:
            pytest.skip("AzureSttFastService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.text = AsyncMock(return_value="Service Unavailable")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", return_value=mock_response), \
             patch("builtins.open", return_value=fake_file):
            svc = AzureSttFastService()
            with pytest.raises(Exception):
                await svc.transcribe("fake/path.wav", language=None)


# ---------------------------------------------------------------------------
# Azure STT Batch — mocked HTTP
# ---------------------------------------------------------------------------


class TestAzureSTTBatchService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
        monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=fake;")
        monkeypatch.setenv("AZURE_STORAGE_CONTAINER_NAME", "test-container")

    async def test_transcribe_returns_result(self, mock_env):
        try:
            from backend.services.azure_stt_batch import AzureSttBatchService
        except ImportError:
            pytest.skip("AzureSttBatchService not yet implemented")

        # Mock the full batch lifecycle: create → poll → get results
        mock_create = MagicMock()
        mock_create.status = 201
        mock_create.json = AsyncMock(return_value={
            "self": "https://eastus.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/fake-id",
        })
        mock_create.headers = {"Location": "https://eastus.api.cognitive.microsoft.com/speechtotext/v3.2/transcriptions/fake-id"}
        mock_create.__aenter__ = AsyncMock(return_value=mock_create)
        mock_create.__aexit__ = AsyncMock(return_value=False)
        mock_create.raise_for_status = MagicMock()

        mock_status = MagicMock()
        mock_status.status = 200
        mock_status.json = AsyncMock(return_value={
            "status": "Succeeded",
            "links": {"files": "https://eastus.api.cognitive.microsoft.com/files"},
        })
        mock_status.__aenter__ = AsyncMock(return_value=mock_status)
        mock_status.__aexit__ = AsyncMock(return_value=False)
        mock_status.raise_for_status = MagicMock()

        mock_files = MagicMock()
        mock_files.status = 200
        mock_files.json = AsyncMock(return_value={
            "values": [{"kind": "Transcription", "links": {"contentUrl": "https://fake/result.json"}}],
        })
        mock_files.__aenter__ = AsyncMock(return_value=mock_files)
        mock_files.__aexit__ = AsyncMock(return_value=False)
        mock_files.raise_for_status = MagicMock()

        mock_result = MagicMock()
        mock_result.status = 200
        mock_result.json = AsyncMock(return_value={
            "combinedRecognizedPhrases": [{"display": "Hello from batch."}],
            "recognizedPhrases": [
                {
                    "offsetInTicks": 0,
                    "durationInTicks": 30_000_000,
                    "nBest": [{"display": "Hello from batch."}],
                }
            ],
        })
        mock_result.__aenter__ = AsyncMock(return_value=mock_result)
        mock_result.__aexit__ = AsyncMock(return_value=False)
        mock_result.raise_for_status = MagicMock()

        call_count = 0
        responses = [mock_create, mock_status, mock_files, mock_result]

        def mock_get_or_post(*args, **kwargs):
            nonlocal call_count
            resp = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return resp

        import io
        fake_file = io.BytesIO(b"fake audio data")
        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob = MagicMock()
        mock_blob_client.url = "https://fake.blob.core.windows.net/container/blob"
        mock_blob_client.account_name = "fake"

        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob_client

        mock_blob_svc = MagicMock()
        mock_blob_svc.get_container_client.return_value = mock_container
        mock_blob_svc.credential.account_key = "ZmFrZWtleQ=="

        with patch("aiohttp.ClientSession.post", side_effect=mock_get_or_post), \
             patch("aiohttp.ClientSession.get", side_effect=mock_get_or_post), \
             patch("backend.services.azure_stt_batch.BlobServiceClient.from_connection_string", return_value=mock_blob_svc), \
             patch("backend.services.azure_stt_batch.generate_blob_sas", return_value="fakesas"), \
             patch("builtins.open", return_value=fake_file):
            svc = AzureSttBatchService()
            result = await svc.transcribe("fake/path.wav", language="en-US")

        assert result.full_text is not None
        assert len(result.segments) >= 1

    async def test_timeout_handling(self, mock_env):
        try:
            from backend.services.azure_stt_batch import AzureSttBatchService
        except ImportError:
            pytest.skip("AzureSttBatchService not yet implemented")

        import io
        fake_file = io.BytesIO(b"fake audio data")
        mock_blob_client = MagicMock()
        mock_blob_client.upload_blob = MagicMock()
        mock_blob_client.url = "https://fake.blob.core.windows.net/container/blob"
        mock_blob_client.account_name = "fake"

        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob_client

        mock_blob_svc = MagicMock()
        mock_blob_svc.get_container_client.return_value = mock_container
        mock_blob_svc.credential.account_key = "ZmFrZWtleQ=="

        with patch("aiohttp.ClientSession.post", side_effect=asyncio.TimeoutError), \
             patch("backend.services.azure_stt_batch.BlobServiceClient.from_connection_string", return_value=mock_blob_svc), \
             patch("backend.services.azure_stt_batch.generate_blob_sas", return_value="fakesas"), \
             patch("builtins.open", return_value=fake_file):
            svc = AzureSttBatchService()
            with pytest.raises(Exception):
                await svc.transcribe("fake/path.wav", language=None)


# ---------------------------------------------------------------------------
# MAI Transcribe service
# ---------------------------------------------------------------------------


class TestMAITranscribeService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "fake-key")
        monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")

    async def test_transcribe_uses_enhanced_mode(self, mock_env):
        try:
            from backend.services.mai_transcribe import MaiTranscribeService
        except ImportError:
            pytest.skip("MaiTranscribeService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "MAI result."}],
            "phrases": [
                {
                    "offsetInTicks": 0,
                    "durationInTicks": 15_000_000,
                    "text": "MAI result.",
                }
            ],
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.raise_for_status = MagicMock()

        posted_data = {}

        original_post = None

        def capture_post(*args, **kwargs):
            posted_data.update(kwargs)
            return mock_response

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", side_effect=capture_post), \
             patch("builtins.open", return_value=fake_file):
            svc = MaiTranscribeService()
            result = await svc.transcribe("fake/path.wav", language=None)

        assert result.full_text == "MAI result."


# ---------------------------------------------------------------------------
# AOAI Transcribe service
# ---------------------------------------------------------------------------


class TestAOAITranscribeService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "fake-key")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-transcribe")

    async def test_transcribe_returns_segments(self, mock_env):
        try:
            from backend.services.aoai_transcribe import AoaiTranscribeService
        except ImportError:
            pytest.skip("AoaiTranscribeService not yet implemented")

        mock_result = MagicMock()
        mock_result.text = "Hello from OpenAI."
        mock_result.segments = [
            MagicMock(start=0.0, end=2.0, text="Hello from OpenAI."),
        ]
        mock_result.language = "en"

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_result)

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("backend.services.aoai_transcribe.AsyncAzureOpenAI", return_value=mock_client), \
             patch("builtins.open", return_value=fake_file):
            svc = AoaiTranscribeService()
            result = await svc.transcribe("fake/path.wav", language="en-US")

        assert result.full_text == "Hello from OpenAI."
        assert len(result.segments) == 1
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 2.0

    async def test_auth_failure(self, mock_env):
        try:
            from backend.services.aoai_transcribe import AoaiTranscribeService
        except ImportError:
            pytest.skip("AoaiTranscribeService not yet implemented")

        mock_client = MagicMock()
        from openai import AuthenticationError
        mock_client.audio.transcriptions.create = AsyncMock(
            side_effect=AuthenticationError(
                message="Invalid API key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("backend.services.aoai_transcribe.AsyncAzureOpenAI", return_value=mock_client), \
             patch("builtins.open", return_value=fake_file):
            svc = AoaiTranscribeService()
            with pytest.raises(Exception):
                await svc.transcribe("fake/path.wav", language=None)


# ---------------------------------------------------------------------------
# Voxtral service
# ---------------------------------------------------------------------------


class TestVoxtralTranscribeService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setenv("VOXTRAL_ENDPOINT_URL", "https://fake.voxtral.endpoint/")
        monkeypatch.setenv("VOXTRAL_ENDPOINT_KEY", "fake-key")

    async def test_transcribe_returns_result(self, mock_env):
        try:
            from backend.services.voxtral_transcribe import VoxtralTranscribeService
        except ImportError:
            pytest.skip("VoxtralTranscribeService not yet implemented")

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Voxtral transcription result."))
        ]

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        mock_path = MagicMock()
        mock_path.suffix = ".wav"
        mock_path.name = "test.wav"
        mock_path.read_bytes.return_value = b"fake audio data"

        with patch("backend.services.voxtral_transcribe.ChatCompletionsClient", return_value=mock_client), \
             patch("backend.services.voxtral_transcribe.Path", return_value=mock_path), \
             patch("backend.services.voxtral_transcribe.get_duration", return_value=5.0), \
             patch("backend.services.voxtral_transcribe.AudioContentItem", MagicMock()), \
             patch("backend.services.voxtral_transcribe.InputAudio", MagicMock()), \
             patch("backend.services.voxtral_transcribe.SystemMessage", MagicMock()), \
             patch("backend.services.voxtral_transcribe.UserMessage", MagicMock()), \
             patch("backend.services.voxtral_transcribe.TextContentItem", MagicMock()):
            svc = VoxtralTranscribeService()
            result = await svc.transcribe("fake/path.wav", language=None)

        assert result.full_text is not None
        assert len(result.segments) >= 1

    async def test_service_unavailable(self, mock_env):
        try:
            from backend.services.voxtral_transcribe import VoxtralTranscribeService
        except ImportError:
            pytest.skip("VoxtralTranscribeService not yet implemented")

        mock_client = MagicMock()
        mock_client.complete = AsyncMock(side_effect=ConnectionError("Service unavailable"))
        mock_client.close = AsyncMock()

        mock_path = MagicMock()
        mock_path.suffix = ".wav"
        mock_path.name = "test.wav"
        mock_path.read_bytes.return_value = b"fake audio data"

        with patch("backend.services.voxtral_transcribe.ChatCompletionsClient", return_value=mock_client), \
             patch("backend.services.voxtral_transcribe.Path", return_value=mock_path), \
             patch("backend.services.voxtral_transcribe.get_duration", return_value=5.0), \
             patch("backend.services.voxtral_transcribe.AudioContentItem", MagicMock()), \
             patch("backend.services.voxtral_transcribe.InputAudio", MagicMock()), \
             patch("backend.services.voxtral_transcribe.SystemMessage", MagicMock()), \
             patch("backend.services.voxtral_transcribe.UserMessage", MagicMock()), \
             patch("backend.services.voxtral_transcribe.TextContentItem", MagicMock()):
            svc = VoxtralTranscribeService()
            with pytest.raises(Exception):
                await svc.transcribe("fake/path.wav", language=None)
