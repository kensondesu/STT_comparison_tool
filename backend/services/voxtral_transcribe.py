"""Voxtral Mini transcription via Azure Foundry.

Sends audio as base64 in a chat completion request using the azure-ai-inference SDK.
Timecodes: prompts the model for timestamps; falls back to a single full-duration segment.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to endpoint key if ``VOXTRAL_ENDPOINT_KEY`` is set.
"""

import base64
import logging
import re
from pathlib import Path

from azure.ai.inference.aio import ChatCompletionsClient
from azure.ai.inference.models import (
    SystemMessage,
    UserMessage,
    TextContentItem,
    AudioContentItem,
    InputAudio,
    AudioContentFormat,
)
from azure.core.credentials import AzureKeyCredential

from backend.config import settings
from backend.models.schemas import Segment
from backend.services.base import TranscriptionResult, TranscriptionService
from backend.utils.audio import get_duration

logger = logging.getLogger(__name__)

AUDIO_FORMAT_MAP: dict[str, str] = {
    "wav": AudioContentFormat.WAV,
    "mp3": AudioContentFormat.MP3,
    "flac": "flac",
    "ogg": "ogg",
    "m4a": "m4a",
    "webm": "webm",
}


class VoxtralTranscribeService(TranscriptionService):
    """Voxtral Mini via Azure Foundry (chat completion with audio input)."""

    def __init__(self) -> None:
        self._endpoint = settings.voxtral_endpoint_url
        self._use_key = bool(settings.voxtral_endpoint_key)
        self._key = settings.voxtral_endpoint_key

    async def transcribe(
        self, audio_path: str, language: str | None = None
    ) -> TranscriptionResult:
        file_path = Path(audio_path)
        ext = file_path.suffix.lstrip(".").lower()
        audio_bytes = file_path.read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode()

        audio_format = AUDIO_FORMAT_MAP.get(ext, AudioContentFormat.WAV)

        lang_hint = f" The audio language is {language}." if language else ""
        system_prompt = (
            "You are a precise audio transcription assistant. "
            "Transcribe the following audio exactly as spoken. "
            "Output ONLY the transcribed text, nothing else."
            f"{lang_hint}"
        )

        if self._use_key:
            credential = AzureKeyCredential(self._key)
        else:
            from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential
            credential = AsyncDefaultAzureCredential()

        client = ChatCompletionsClient(
            endpoint=self._endpoint,
            credential=credential,
        )

        try:
            response = await client.complete(
                messages=[
                    SystemMessage(content=system_prompt),
                    UserMessage(
                        content=[
                            AudioContentItem(
                                input_audio=InputAudio(
                                    data=audio_b64,
                                    format=audio_format,
                                ),
                            ),
                            TextContentItem(text="Transcribe this audio."),
                        ],
                    ),
                ],
                model="voxtral-mini",
            )
        finally:
            await client.close()

        text = response.choices[0].message.content.strip() if response.choices else ""
        detected_lang = language

        # Build a single segment spanning the full audio duration
        duration = get_duration(audio_path)
        end_time = duration if duration else 0.0

        segments = [Segment(start_time=0.0, end_time=round(end_time, 3), text=text)] if text else []

        return TranscriptionResult(
            segments=segments,
            full_text=text,
            detected_language=detected_lang,
        )
