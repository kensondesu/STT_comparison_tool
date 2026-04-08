"""Azure Speech-to-Text Fast Transcription service.

Synchronous multipart POST with audio file + JSON definition.
Timecodes arrive as offsetInTicks / durationInTicks (100 ns units) → normalised to seconds.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``AZURE_SPEECH_KEY`` is set.
"""

import logging
from pathlib import Path

import aiohttp

from backend.config import settings, get_cognitive_services_token
from backend.models.schemas import Segment
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)

TICKS_PER_SECOND = 10_000_000


class AzureSttFastService(TranscriptionService):
    """Azure Speech-to-Text — Fast Transcription (REST API)."""

    def __init__(self) -> None:
        self._use_key = bool(settings.azure_speech_key)
        self._key = settings.azure_speech_key
        self._region = settings.azure_speech_region
        # Custom subdomain required for bearer token auth
        base = settings.azure_speech_endpoint.rstrip("/") if settings.azure_speech_endpoint else f"https://{self._region}.api.cognitive.microsoft.com"
        self._url = f"{base}/speechtotext/transcriptions:transcribe?api-version=2025-10-15"

    def _build_definition(self, language: str | None) -> dict:
        definition: dict = {}
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
        self, audio_path: str, language: str | None = None
    ) -> TranscriptionResult:
        definition = self._build_definition(language)
        file_path = Path(audio_path)

        data = aiohttp.FormData()
        data.add_field("definition", __import__("json").dumps(definition), content_type="application/json")
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
                    logger.error("Fast STT %s: %s", resp.status, body)
                resp.raise_for_status()
                result = await resp.json()
                logger.info("Fast STT raw response keys: %s", list(result.keys()))
                if "phrases" in result:
                    logger.info("First phrase keys: %s", list(result["phrases"][0].keys()) if result["phrases"] else "empty")
                    if result["phrases"]:
                        logger.info("First phrase: %s", result["phrases"][0])

        return self._parse_result(result)

    @staticmethod
    def _parse_result(result: dict) -> TranscriptionResult:
        segments: list[Segment] = []
        all_text_parts: list[str] = []
        detected_lang: str | None = None

        for combined in result.get("combinedPhrases", []):
            all_text_parts.append(combined.get("text", ""))

        for phrase in result.get("phrases", []):
            # API returns milliseconds (not ticks)
            offset_ms = phrase.get("offsetMilliseconds", 0)
            duration_ms = phrase.get("durationMilliseconds", 0)
            start = offset_ms / 1000.0
            end = start + duration_ms / 1000.0
            text = phrase.get("text", "")
            if text:
                segments.append(
                    Segment(start_time=round(start, 3), end_time=round(end, 3), text=text)
                )
            if not detected_lang:
                detected_lang = phrase.get("locale")

        return TranscriptionResult(
            segments=segments,
            full_text=" ".join(all_text_parts) if all_text_parts else " ".join(s.text for s in segments),
            detected_language=detected_lang,
        )
