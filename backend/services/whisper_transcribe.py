"""Azure OpenAI Whisper transcription service.

Uses the same Azure OpenAI resource as gpt-4o-transcribe but targets a
Whisper deployment.  Unlike gpt-4o-transcribe, Whisper supports
``verbose_json`` with segment-level timecodes natively.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``AZURE_OPENAI_API_KEY`` is set.
"""

import logging

from openai import AsyncAzureOpenAI

from backend.config import settings, COGNITIVE_SERVICES_SCOPE
from backend.models.schemas import Segment
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)


class WhisperTranscribeService(TranscriptionService):
    """Azure OpenAI Whisper via openai SDK."""

    def __init__(self) -> None:
        if settings.azure_openai_api_key:
            self._client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version="2025-01-01-preview",
            )
        else:
            from azure.identity.aio import (
                DefaultAzureCredential as AsyncDefaultAzureCredential,
                get_bearer_token_provider,
            )
            token_provider = get_bearer_token_provider(
                AsyncDefaultAzureCredential(),
                COGNITIVE_SERVICES_SCOPE,
            )
            self._client = AsyncAzureOpenAI(
                azure_ad_token_provider=token_provider,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version="2025-01-01-preview",
            )
        self._deployment = settings.azure_whisper_deployment_name

    async def transcribe(
        self, audio_path: str, language: str | None = None, settings: dict | None = None
    ) -> TranscriptionResult:
        s = settings or {}
        with open(audio_path, "rb") as audio_file:
            kwargs: dict = {
                "model": self._deployment,
                "file": audio_file,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"],
            }
            if language:
                kwargs["language"] = language.split("-")[0]  # ISO-639-1

            # Custom settings
            if "prompt" in s:
                kwargs["prompt"] = s["prompt"]
            if "temperature" in s:
                kwargs["temperature"] = s["temperature"]

            response = await self._client.audio.transcriptions.create(**kwargs)

        segments: list[Segment] = []
        detected_lang: str | None = getattr(response, "language", None)
        full_text = getattr(response, "text", "") or ""

        for seg in getattr(response, "segments", []) or []:
            text = seg.get("text", "").strip() if isinstance(seg, dict) else getattr(seg, "text", "").strip()
            start = seg.get("start", 0.0) if isinstance(seg, dict) else getattr(seg, "start", 0.0)
            end = seg.get("end", 0.0) if isinstance(seg, dict) else getattr(seg, "end", 0.0)
            if text:
                segments.append(
                    Segment(start_time=round(start, 3), end_time=round(end, 3), text=text)
                )

        return TranscriptionResult(
            segments=segments,
            full_text=full_text.strip(),
            detected_language=detected_lang,
        )
