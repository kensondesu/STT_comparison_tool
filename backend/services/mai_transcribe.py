"""MAI-Transcribe-1 service.

Uses its own Speech resource (separate region/endpoint from standard STT).
Same Fast Transcription endpoint format but with enhancedMode flag.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``MAI_SPEECH_KEY`` is set.
"""

import json
import logging
from pathlib import Path

import aiohttp

from backend.config import settings, get_cognitive_services_token
from backend.models.schemas import Segment
from backend.services.azure_stt_fast import AzureSttFastService, TICKS_PER_SECOND
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)


class MaiTranscribeService(TranscriptionService):
    """MAI-Transcribe-1 via Azure Fast Transcription with enhancedMode."""

    def __init__(self) -> None:
        # MAI uses its own resource, separate from standard STT
        self._use_key = bool(settings.mai_speech_key)
        self._key = settings.mai_speech_key
        self._region = settings.mai_speech_region
        base = settings.mai_speech_endpoint.rstrip("/") if settings.mai_speech_endpoint else f"https://{self._region}.api.cognitive.microsoft.com"
        self._url = f"{base}/speechtotext/transcriptions:transcribe?api-version=2025-10-15"

    def _build_definition(self, language: str | None, settings: dict | None = None) -> dict:
        s = settings or {}
        definition: dict = {
            "enhancedMode": {"enabled": True, "model": "mai-transcribe-1"},
        }

        # Profanity filter
        if "profanity_filter" in s:
            definition["profanityFilterMode"] = s["profanity_filter"]

        if language:
            definition["locales"] = [language]
        else:
            definition["locales"] = ["en-US"]
            definition["languageIdentification"] = {
                "candidateLocales": [
                    "en-US", "fr-FR", "de-DE", "es-ES", "ja-JP",
                    "zh-CN", "ko-KR", "pt-BR", "it-IT", "nl-NL",
                ]
            }
        return definition

    async def transcribe(
        self, audio_path: str, language: str | None = None, settings: dict | None = None
    ) -> TranscriptionResult:
        definition = self._build_definition(language, settings)
        file_path = Path(audio_path)

        data = aiohttp.FormData()
        data.add_field("definition", json.dumps(definition), content_type="application/json")
        data.add_field(
            "audio",
            open(file_path, "rb"),
            filename=file_path.name,
            content_type="application/octet-stream",
        )

        if self._use_key:
            headers = {"Ocp-Apim-Subscription-Key": self._key}
        else:
            token = get_cognitive_services_token()
            headers = {"Authorization": f"Bearer {token}"}

        async with aiohttp.ClientSession() as session:
            async with session.post(self._url, data=data, headers=headers) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error("MAI Transcribe %s: %s", resp.status, body)
                resp.raise_for_status()
                result = await resp.json()

        # Response format is the same as Fast Transcription
        return AzureSttFastService._parse_result(result)
