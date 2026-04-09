"""Azure OpenAI gpt-4o-transcribe service.

Uses the openai SDK configured for Azure. Returns verbose_json with segment-level timecodes.
Timecodes are already in seconds — no conversion needed.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``AZURE_OPENAI_API_KEY`` is set.
"""

import logging

from openai import AsyncAzureOpenAI

from backend.config import settings, COGNITIVE_SERVICES_SCOPE
from backend.models.schemas import Segment
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)


class AoaiTranscribeService(TranscriptionService):
    """Azure OpenAI gpt-4o-transcribe via openai SDK."""

    def __init__(self) -> None:
        if settings.azure_openai_api_key:
            self._client = AsyncAzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version="2025-01-01-preview",
            )
        else:
            from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential, get_bearer_token_provider
            token_provider = get_bearer_token_provider(
                AsyncDefaultAzureCredential(),
                COGNITIVE_SERVICES_SCOPE,
            )
            self._client = AsyncAzureOpenAI(
                azure_ad_token_provider=token_provider,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version="2025-01-01-preview",
            )
        self._deployment = settings.azure_openai_deployment_name

    async def transcribe(
        self, audio_path: str, language: str | None = None, settings: dict | None = None
    ) -> TranscriptionResult:
        s = settings or {}
        with open(audio_path, "rb") as audio_file:
            kwargs: dict = {
                "model": self._deployment,
                "file": audio_file,
                "response_format": "json",
            }
            if language:
                kwargs["language"] = language.split("-")[0]  # openai uses ISO-639-1

            # Custom settings
            if "prompt" in s:
                kwargs["prompt"] = s["prompt"]
            if "temperature" in s:
                kwargs["temperature"] = s["temperature"]

            response = await self._client.audio.transcriptions.create(**kwargs)

        segments: list[Segment] = []
        detected_lang: str | None = getattr(response, "language", None)
        full_text = getattr(response, "text", "") or ""

        # json format returns text only — no segment-level timecodes.
        # Create a single segment spanning full audio duration.
        if full_text:
            from backend.utils.audio import get_duration
            duration = get_duration(audio_path) or 0.0
            logger.info("AOAI duration for %s: %s", audio_path, duration)
            segments.append(
                Segment(start_time=0.0, end_time=round(duration, 3), text=full_text.strip())
            )

        return TranscriptionResult(
            segments=segments,
            full_text=full_text.strip(),
            detected_language=detected_lang,
        )
