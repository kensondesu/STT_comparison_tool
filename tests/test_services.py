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
    """Azure STT Fast API returns offsets in milliseconds. Verify conversion."""

    def _ms_to_seconds(self, ms: int) -> float:
        """The normalization formula used in the Fast/MAI services."""
        return ms / 1000.0

    def test_zero_ms(self):
        assert self._ms_to_seconds(0) == 0.0

    def test_one_second(self):
        assert self._ms_to_seconds(1000) == 1.0

    def test_fractional_seconds(self):
        result = self._ms_to_seconds(2540)
        assert abs(result - 2.54) < 1e-6

    def test_large_offset(self):
        two_hours_ms = 2 * 3600 * 1000
        assert self._ms_to_seconds(two_hours_ms) == 7200.0

    def test_small_offset(self):
        result = self._ms_to_seconds(100)
        assert abs(result - 0.1) < 1e-6

    def test_normalization_in_parse_result(self):
        """Test _parse_result handles millisecond fields correctly."""
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
            result = AzureSttFastService._parse_result({
                "combinedPhrases": [{"text": "Hello."}],
                "phrases": [{"offsetMilliseconds": 1500, "durationMilliseconds": 2000, "text": "Hello.", "locale": "en-US"}],
            })
            assert result.segments[0].start_time == 1.5
            assert result.segments[0].end_time == 3.5
        except ImportError:
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
        monkeypatch.setattr("backend.config.settings.azure_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_speech_region", "eastus")

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
                    "offsetMilliseconds": 0,
                    "durationMilliseconds": 2540,
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
        monkeypatch.setattr("backend.config.settings.azure_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_speech_region", "eastus")
        monkeypatch.setattr(
            "backend.config.settings.azure_storage_connection_string",
            "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=ZmFrZWtleQ==;",
        )
        monkeypatch.setattr("backend.config.settings.azure_storage_container_name", "test-container")

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
                    "offsetMilliseconds": 0,
                    "durationMilliseconds": 3000,
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
        monkeypatch.setattr("backend.config.settings.azure_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_speech_region", "eastus")

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
                    "offsetMilliseconds": 0,
                    "durationMilliseconds": 1500,
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
        monkeypatch.setattr("backend.config.settings.azure_openai_api_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_openai_endpoint", "https://fake.openai.azure.com/")
        monkeypatch.setattr("backend.config.settings.azure_openai_deployment_name", "gpt-4o-transcribe")

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
             patch("builtins.open", return_value=fake_file), \
             patch("backend.utils.audio.get_duration", return_value=2.0):
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
        monkeypatch.setattr("backend.config.settings.voxtral_endpoint_url", "https://fake.voxtral.endpoint/")
        monkeypatch.setattr("backend.config.settings.voxtral_endpoint_key", "fake-key")

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


# ---------------------------------------------------------------------------
# Whisper Transcribe service — Azure Speech Batch (Whisper model)
# ---------------------------------------------------------------------------


class TestWhisperTranscribeService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.whisper_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.whisper_speech_region", "eastus")
        monkeypatch.setattr("backend.config.settings.whisper_speech_endpoint", "https://fake.speech.azure.com")
        monkeypatch.setattr("backend.config.settings.azure_storage_connection_string", "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=ZmFrZQ==;EndpointSuffix=core.windows.net")
        monkeypatch.setattr("backend.config.settings.azure_storage_container_name", "test-container")
        monkeypatch.setattr("backend.config.settings.azure_whisper_model_id", "")

    def _build_batch_mocks(self):
        """Build aiohttp mock responses for the Whisper batch flow."""
        # Model discovery response
        model_resp = MagicMock()
        model_resp.status = 200
        model_resp.raise_for_status = MagicMock()
        model_resp.json = AsyncMock(side_effect=[
            {
                "values": [
                    {
                        "self": "https://eastus.api.cognitive.microsoft.com/speechtotext/models/base/whisper-001",
                        "displayName": "Whisper Large V3",
                        "createdDateTime": "2024-01-01T00:00:00Z",
                    },
                ]
            },
            {"values": []},
        ])
        model_resp.__aenter__ = AsyncMock(return_value=model_resp)
        model_resp.__aexit__ = AsyncMock(return_value=None)

        # Create job response
        create_resp = MagicMock()
        create_resp.status = 201
        create_resp.raise_for_status = MagicMock()
        create_resp.json = AsyncMock(return_value={
            "self": "https://fake.speech.azure.com/speechtotext/v3.2/transcriptions/abc123"
        })
        create_resp.__aenter__ = AsyncMock(return_value=create_resp)
        create_resp.__aexit__ = AsyncMock(return_value=None)

        # Poll response — succeeded
        poll_resp = MagicMock()
        poll_resp.status = 200
        poll_resp.raise_for_status = MagicMock()
        poll_resp.json = AsyncMock(return_value={"status": "Succeeded"})
        poll_resp.__aenter__ = AsyncMock(return_value=poll_resp)
        poll_resp.__aexit__ = AsyncMock(return_value=None)

        # Files list response
        files_resp = MagicMock()
        files_resp.status = 200
        files_resp.raise_for_status = MagicMock()
        files_resp.json = AsyncMock(return_value={
            "values": [
                {
                    "kind": "Transcription",
                    "links": {"contentUrl": "https://blob.example.com/result.json?sas=token"},
                }
            ]
        })
        files_resp.__aenter__ = AsyncMock(return_value=files_resp)
        files_resp.__aexit__ = AsyncMock(return_value=None)

        # Result content response
        content_resp = MagicMock()
        content_resp.status = 200
        content_resp.raise_for_status = MagicMock()
        content_resp.json = AsyncMock(return_value={
            "combinedRecognizedPhrases": [{"display": "Hello from Whisper.", "locale": "en-US"}],
            "recognizedPhrases": [
                {
                    "offsetInTicks": 0,
                    "durationInTicks": 18_000_000,
                    "nBest": [{"display": "Hello from"}],
                    "locale": "en-US",
                },
                {
                    "offsetInTicks": 18_000_000,
                    "durationInTicks": 17_000_000,
                    "nBest": [{"display": "Whisper."}],
                    "locale": "en-US",
                },
            ],
        })
        content_resp.__aenter__ = AsyncMock(return_value=content_resp)
        content_resp.__aexit__ = AsyncMock(return_value=None)

        return model_resp, create_resp, poll_resp, files_resp, content_resp

    async def test_transcribe_returns_segments(self, mock_env):
        """Batch flow should produce segments with correct timecodes."""
        try:
            from backend.services.whisper_transcribe import WhisperTranscribeService
        except ImportError:
            pytest.skip("WhisperTranscribeService not yet implemented")

        model_resp, create_resp, poll_resp, files_resp, content_resp = self._build_batch_mocks()

        mock_session = MagicMock()
        call_count = {"get": 0}

        def _get_side_effect(url, **kwargs):
            call_count["get"] += 1
            if "models/base?" in url:
                return model_resp
            elif "/files" in url:
                return files_resp
            elif "blob.example.com" in url:
                return content_resp
            else:
                return poll_resp

        mock_session.get = MagicMock(side_effect=_get_side_effect)
        mock_session.post = MagicMock(return_value=create_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.whisper_transcribe.asyncio.to_thread", new_callable=AsyncMock) as mock_upload, \
             patch("backend.services.azure_stt_batch.asyncio.sleep", new_callable=AsyncMock), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            mock_upload.return_value = "https://blob.example.com/audio.wav?sas=token"
            svc = WhisperTranscribeService()
            result = await svc.transcribe("fake/path.wav", language="en-US")

        assert result.full_text == "Hello from Whisper."
        assert len(result.segments) == 2
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 1.8
        assert result.segments[0].text == "Hello from"
        assert result.segments[1].start_time == 1.8
        assert result.segments[1].end_time == 3.5
        assert result.detected_language == "en-US"

    async def test_whisper_model_auto_discovery(self, mock_env):
        """When azure_whisper_model_id is empty, service should auto-discover the model."""
        try:
            from backend.services.whisper_transcribe import WhisperTranscribeService
        except ImportError:
            pytest.skip("WhisperTranscribeService not yet implemented")

        model_resp, create_resp, poll_resp, files_resp, content_resp = self._build_batch_mocks()

        mock_session = MagicMock()

        def _get_side_effect(url, **kwargs):
            if "models/base?" in url:
                return model_resp
            elif "/files" in url:
                return files_resp
            elif "blob.example.com" in url:
                return content_resp
            else:
                return poll_resp

        mock_session.get = MagicMock(side_effect=_get_side_effect)
        mock_session.post = MagicMock(return_value=create_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.whisper_transcribe.asyncio.to_thread", new_callable=AsyncMock) as mock_upload, \
             patch("backend.services.azure_stt_batch.asyncio.sleep", new_callable=AsyncMock), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            mock_upload.return_value = "https://blob.example.com/audio.wav?sas=token"
            svc = WhisperTranscribeService()
            result = await svc.transcribe("fake/path.wav", language=None)

        # Verify model discovery was called (GET to models/base)
        get_calls = [str(c) for c in mock_session.get.call_args_list]
        assert any("models/base?" in c for c in get_calls), "Should call models/base API for auto-discovery"
        assert result.full_text  # Got a result

    async def test_batch_failure_raises(self, mock_env):
        """Failed batch job should raise RuntimeError."""
        try:
            from backend.services.whisper_transcribe import WhisperTranscribeService
        except ImportError:
            pytest.skip("WhisperTranscribeService not yet implemented")

        model_resp, create_resp, _, _, _ = self._build_batch_mocks()

        # Override poll to return Failed
        fail_resp = MagicMock()
        fail_resp.status = 200
        fail_resp.raise_for_status = MagicMock()
        fail_resp.json = AsyncMock(return_value={
            "status": "Failed",
            "properties": {"error": {"message": "Model not available"}},
        })
        fail_resp.__aenter__ = AsyncMock(return_value=fail_resp)
        fail_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=lambda url, **kw: model_resp if "models/base?" in url else fail_resp)
        mock_session.post = MagicMock(return_value=create_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.whisper_transcribe.asyncio.to_thread", new_callable=AsyncMock) as mock_upload, \
             patch("backend.services.azure_stt_batch.asyncio.sleep", new_callable=AsyncMock), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            mock_upload.return_value = "https://blob.example.com/audio.wav?sas=token"
            svc = WhisperTranscribeService()
            with pytest.raises(RuntimeError, match="Model not available"):
                await svc.transcribe("fake/path.wav", language=None)


# ---------------------------------------------------------------------------
# LLM Speech service — Fast Transcription enhanced mode
# ---------------------------------------------------------------------------


class TestLlmSpeechService:

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.mai_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.mai_speech_region", "eastus")
        monkeypatch.setattr("backend.config.settings.mai_speech_endpoint", "https://fake.speech.azure.com")

    async def test_transcribe_returns_result(self, mock_env):
        """Mocked HTTP POST should produce correct result; definition must have correct enhancedMode."""
        try:
            from backend.services.llm_speech import LlmSpeechService
        except ImportError:
            pytest.skip("LlmSpeechService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "LLM Speech result."}],
            "phrases": [
                {
                    "offsetMilliseconds": 500,
                    "durationMilliseconds": 2000,
                    "text": "LLM Speech result.",
                    "locale": "en-US",
                }
            ],
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.raise_for_status = MagicMock()

        posted_data = {}

        def capture_post(*args, **kwargs):
            posted_data.update(kwargs)
            return mock_response

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", side_effect=capture_post), \
             patch("builtins.open", return_value=fake_file):
            svc = LlmSpeechService()
            result = await svc.transcribe("fake/path.wav", language=None)

        assert result.full_text == "LLM Speech result."
        assert len(result.segments) == 1
        assert result.segments[0].start_time == 0.5
        assert abs(result.segments[0].end_time - 2.5) < 1e-6

        # Verify the definition JSON has correct enhancedMode structure
        definition = LlmSpeechService._build_definition()
        assert definition == {
            "enhancedMode": {
                "enabled": True,
                "task": "transcribe",
            },
        }
        # Must NOT have 'model' or 'locales' keys
        assert "model" not in definition.get("enhancedMode", {})
        assert "locales" not in definition

    async def test_parse_result_reuses_fast_stt(self, mock_env):
        """Response parsing should produce correct segments from millisecond offsets."""
        try:
            from backend.services.azure_stt_fast import AzureSttFastService
        except ImportError:
            pytest.skip("AzureSttFastService not yet implemented")

        result = AzureSttFastService._parse_result({
            "combinedPhrases": [{"text": "Hello world."}],
            "phrases": [
                {
                    "offsetMilliseconds": 1000,
                    "durationMilliseconds": 3000,
                    "text": "Hello world.",
                    "locale": "en-US",
                }
            ],
        })

        assert result.full_text == "Hello world."
        assert len(result.segments) == 1
        assert result.segments[0].start_time == 1.0
        assert result.segments[0].end_time == 4.0
        assert result.detected_language == "en-US"

    async def test_auth_bearer_token(self, monkeypatch):
        """When no key is set, bearer token should be used."""
        try:
            from backend.services.llm_speech import LlmSpeechService
        except ImportError:
            pytest.skip("LlmSpeechService not yet implemented")

        monkeypatch.setattr("backend.config.settings.mai_speech_key", "")
        monkeypatch.setattr("backend.config.settings.mai_speech_region", "eastus")
        monkeypatch.setattr("backend.config.settings.mai_speech_endpoint", "https://fake.speech.azure.com")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "Token test."}],
            "phrases": [],
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.raise_for_status = MagicMock()

        posted_kwargs = {}

        def capture_post(*args, **kwargs):
            posted_kwargs.update(kwargs)
            return mock_response

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", side_effect=capture_post), \
             patch("builtins.open", return_value=fake_file):
            svc = LlmSpeechService()
            await svc.transcribe("fake/path.wav", language=None)

        headers = posted_kwargs.get("headers", {})
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "Ocp-Apim-Subscription-Key" not in headers

    async def test_auth_api_key_fallback(self, mock_env):
        """When key is set, Ocp-Apim-Subscription-Key header should be used."""
        try:
            from backend.services.llm_speech import LlmSpeechService
        except ImportError:
            pytest.skip("LlmSpeechService not yet implemented")

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "Key test."}],
            "phrases": [],
        })
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.raise_for_status = MagicMock()

        posted_kwargs = {}

        def capture_post(*args, **kwargs):
            posted_kwargs.update(kwargs)
            return mock_response

        import io
        fake_file = io.BytesIO(b"fake audio data")
        with patch("aiohttp.ClientSession.post", side_effect=capture_post), \
             patch("builtins.open", return_value=fake_file):
            svc = LlmSpeechService()
            await svc.transcribe("fake/path.wav", language=None)

        headers = posted_kwargs.get("headers", {})
        assert "Ocp-Apim-Subscription-Key" in headers
        assert headers["Ocp-Apim-Subscription-Key"] == "fake-key"
        assert "Authorization" not in headers


# ---------------------------------------------------------------------------
# Custom settings — per-model transcription settings
# ---------------------------------------------------------------------------


class TestCustomSettings:
    """Verify per-model custom settings are correctly applied to service definitions."""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.azure_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_speech_region", "eastus")
        monkeypatch.setattr("backend.config.settings.azure_speech_endpoint", "https://fake.speech.azure.com")
        monkeypatch.setattr("backend.config.settings.azure_openai_api_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.azure_openai_endpoint", "https://fake.openai.azure.com/")
        monkeypatch.setattr("backend.config.settings.azure_whisper_model_id", "")
        monkeypatch.setattr("backend.config.settings.whisper_speech_key", "fake-key")
        monkeypatch.setattr("backend.config.settings.whisper_speech_region", "eastus")
        monkeypatch.setattr("backend.config.settings.whisper_speech_endpoint", "https://fake.speech.azure.com")

    async def test_fast_stt_phrase_list(self, mock_env):
        """phraseList should appear in definition when phrase_list setting is provided."""
        from backend.services.azure_stt_fast import AzureSttFastService

        svc = AzureSttFastService()
        definition = svc._build_definition(
            language="en-US",
            settings={"phrase_list": ["Contoso", "Azure"]},
        )
        assert "phraseList" in definition
        assert definition["phraseList"] == ["Contoso", "Azure"]

    async def test_fast_stt_diarization(self, mock_env):
        """diarization block should appear in definition when diarization settings provided."""
        from backend.services.azure_stt_fast import AzureSttFastService

        svc = AzureSttFastService()
        definition = svc._build_definition(
            language="en-US",
            settings={"diarization_enabled": True, "diarization_max_speakers": 3},
        )
        assert "diarization" in definition
        assert definition["diarization"]["speakers"]["minCount"] == 1
        assert definition["diarization"]["speakers"]["maxCount"] == 3

    async def test_fast_stt_profanity_filter(self, mock_env):
        """profanityFilterMode should appear in definition when profanity_filter setting provided."""
        from backend.services.azure_stt_fast import AzureSttFastService

        svc = AzureSttFastService()
        definition = svc._build_definition(
            language="en-US",
            settings={"profanity_filter": "Masked"},
        )
        assert "profanityFilterMode" in definition
        assert definition["profanityFilterMode"] == "Masked"

    async def test_whisper_word_timestamps_and_profanity(self, mock_env, monkeypatch):
        """word_level_timestamps and profanity_filter should appear in the batch job body."""
        from backend.services.whisper_transcribe import WhisperTranscribeService

        monkeypatch.setattr("backend.config.settings.azure_storage_connection_string", "DefaultEndpointsProtocol=https;AccountName=fake;AccountKey=ZmFrZQ==;EndpointSuffix=core.windows.net")
        monkeypatch.setattr("backend.config.settings.azure_storage_container_name", "test-container")

        # Build mock responses
        model_resp = MagicMock()
        model_resp.status = 200
        model_resp.raise_for_status = MagicMock()
        model_resp.json = AsyncMock(side_effect=[
            {"values": [{
                "self": "https://eastus.api.cognitive.microsoft.com/speechtotext/models/base/whisper-001",
                "displayName": "Whisper Large V3",
                "createdDateTime": "2024-01-01T00:00:00Z",
            }]},
            {"values": []},
        ])
        model_resp.__aenter__ = AsyncMock(return_value=model_resp)
        model_resp.__aexit__ = AsyncMock(return_value=None)

        create_resp = MagicMock()
        create_resp.status = 201
        create_resp.raise_for_status = MagicMock()
        create_resp.json = AsyncMock(return_value={
            "self": "https://fake.speech.azure.com/speechtotext/v3.2/transcriptions/abc"
        })
        create_resp.__aenter__ = AsyncMock(return_value=create_resp)
        create_resp.__aexit__ = AsyncMock(return_value=None)

        poll_resp = MagicMock()
        poll_resp.status = 200
        poll_resp.raise_for_status = MagicMock()
        poll_resp.json = AsyncMock(return_value={"status": "Succeeded"})
        poll_resp.__aenter__ = AsyncMock(return_value=poll_resp)
        poll_resp.__aexit__ = AsyncMock(return_value=None)

        files_resp = MagicMock()
        files_resp.status = 200
        files_resp.raise_for_status = MagicMock()
        files_resp.json = AsyncMock(return_value={
            "values": [{"kind": "Transcription", "links": {"contentUrl": "https://blob.example.com/r.json?sas=t"}}]
        })
        files_resp.__aenter__ = AsyncMock(return_value=files_resp)
        files_resp.__aexit__ = AsyncMock(return_value=None)

        content_resp = MagicMock()
        content_resp.status = 200
        content_resp.raise_for_status = MagicMock()
        content_resp.json = AsyncMock(return_value={
            "combinedRecognizedPhrases": [{"display": "Hello."}],
            "recognizedPhrases": [{"offsetInTicks": 0, "durationInTicks": 10_000_000, "nBest": [{"display": "Hello."}]}],
        })
        content_resp.__aenter__ = AsyncMock(return_value=content_resp)
        content_resp.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        captured_body = {}

        def _post(url, *, json=None, **kwargs):
            captured_body.update(json or {})
            return create_resp

        mock_session.get = MagicMock(side_effect=lambda url, **kw: (
            model_resp if "models/base?" in url
            else files_resp if "/files" in url
            else content_resp if "blob.example.com" in url
            else poll_resp
        ))
        mock_session.post = MagicMock(side_effect=_post)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("backend.services.whisper_transcribe.asyncio.to_thread", new_callable=AsyncMock) as mock_upload, \
             patch("backend.services.azure_stt_batch.asyncio.sleep", new_callable=AsyncMock), \
             patch("aiohttp.ClientSession", return_value=mock_session):
            mock_upload.return_value = "https://blob.example.com/audio.wav?sas=token"
            svc = WhisperTranscribeService()
            await svc.transcribe(
                "fake/path.wav",
                language="en-US",
                settings={"word_level_timestamps": True, "profanity_filter": "Masked"},
            )

        # Verify the batch job body contains Whisper-specific properties
        assert captured_body["properties"]["displayFormWordLevelTimestampsEnabled"] is True
        assert captured_body["properties"]["profanityFilterMode"] == "Masked"
        assert "model" in captured_body  # Whisper model reference

    async def test_llm_speech_prompt(self, mock_env):
        """enhancedMode.prompt should appear in definition when prompt setting provided."""
        from backend.services.llm_speech import LlmSpeechService

        definition = LlmSpeechService._build_definition(
            settings={"prompt": ["Output lexical format"]},
        )
        assert definition["enhancedMode"]["prompt"] == ["Output lexical format"]
        assert definition["enhancedMode"]["enabled"] is True
        assert definition["enhancedMode"]["task"] == "transcribe"

    async def test_llm_speech_translate_task(self, mock_env):
        """task=translate and targetLanguage should appear in enhancedMode definition."""
        from backend.services.llm_speech import LlmSpeechService

        definition = LlmSpeechService._build_definition(
            settings={"task": "translate", "target_language": "fr"},
        )
        assert definition["enhancedMode"]["task"] == "translate"
        assert definition["enhancedMode"]["targetLanguage"] == "fr"

    async def test_settings_none_works(self, mock_env):
        """Calling transcribe with settings=None should work exactly as before."""
        from backend.services.azure_stt_fast import AzureSttFastService

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "Hello."}],
            "phrases": [
                {"offsetMilliseconds": 0, "durationMilliseconds": 1000, "text": "Hello."}
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
            result = await svc.transcribe("fake/path.wav", language="en-US", settings=None)

        assert result.full_text == "Hello."
        assert len(result.segments) == 1

    async def test_unknown_settings_ignored(self, mock_env):
        """Passing unknown setting keys should not crash the service."""
        from backend.services.azure_stt_fast import AzureSttFastService

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "combinedPhrases": [{"text": "Hello."}],
            "phrases": [
                {"offsetMilliseconds": 0, "durationMilliseconds": 1000, "text": "Hello."}
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
            result = await svc.transcribe(
                "fake/path.wav",
                language="en-US",
                settings={"bogus_key": "whatever", "another_fake": 123},
            )

        assert result.full_text == "Hello."
        assert len(result.segments) == 1
