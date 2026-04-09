"""LLM Speech transcription service (Azure Fast Transcription enhanced mode).

Uses the SAME Azure Speech resource and endpoint as STT Fast, but sends
``enhancedMode: { enabled: true, task: "transcribe" }`` in the definition.
Language detection is automatic — no ``locales`` field is sent.

This is distinct from MAI-Transcribe-1 which uses
``"model": "mai-transcribe-1"`` in enhancedMode.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``AZURE_SPEECH_KEY`` is set.
"""

import json
import logging
from pathlib import Path

import aiohttp

from backend.config import settings, get_cognitive_services_token
from backend.services.azure_stt_fast import AzureSttFastService
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)


class LlmSpeechService(TranscriptionService):
    """LLM Speech via Azure Fast Transcription with enhancedMode."""

    def __init__(self) -> None:
        self._use_key = bool(settings.azure_speech_key)
        self._key = settings.azure_speech_key
        self._region = settings.azure_speech_region
        base = (
            settings.azure_speech_endpoint.rstrip("/")
            if settings.azure_speech_endpoint
            else f"https://{self._region}.api.cognitive.microsoft.com"
        )
        self._url = f"{base}/speechtotext/transcriptions:transcribe?api-version=2025-10-15"

    @staticmethod
    def _build_definition() -> dict:
        return {
            "enhancedMode": {
                "enabled": True,
                "task": "transcribe",
            },
        }

    async def transcribe(
        self, audio_path: str, language: str | None = None
    ) -> TranscriptionResult:
        definition = self._build_definition()
        file_path = Path(audio_path)

        data = aiohttp.FormData()
        data.add_field(
            "definition", json.dumps(definition), content_type="application/json"
        )
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
                    logger.error("LLM Speech %s: %s", resp.status, body)
                resp.raise_for_status()
                result = await resp.json()

        return AzureSttFastService._parse_result(result)
