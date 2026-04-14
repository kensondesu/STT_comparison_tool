"""Whisper transcription via Azure Speech Batch Transcription API.

Subclasses ``AzureSttBatchService`` — the flow is identical (upload blob →
create batch job → poll → fetch results) with these differences:

- The batch job body includes ``"model": {"self": "<whisper_model_uri>"}``
- Uses ``displayFormWordLevelTimestampsEnabled`` instead of ``wordLevelTimestampsEnabled``
- Does not support ``punctuationMode``
- The ``lexical`` field is empty; text is taken from the ``display`` field

The Whisper base-model URI is auto-discovered via the Models API when
``AZURE_WHISPER_MODEL_ID`` is not set.

Auth: inherits from ``AzureSttBatchService`` (managed identity / key fallback).
"""

import asyncio
import logging
import uuid

import aiohttp

from backend.config import settings as app_settings
from backend.models.schemas import Segment
from backend.services.azure_stt_batch import AzureSttBatchService, TICKS_PER_SECOND
from backend.services.base import TranscriptionResult

logger = logging.getLogger(__name__)


class WhisperTranscribeService(AzureSttBatchService):
    """Whisper via Azure STT Batch Transcription (separate region from main STT)."""

    def __init__(self) -> None:
        # Do NOT call super().__init__() — we override all config
        # to use the Whisper-specific Speech resource
        self._region = app_settings.whisper_speech_region
        base = (
            app_settings.whisper_speech_endpoint.rstrip("/")
            if app_settings.whisper_speech_endpoint
            else f"https://{self._region}.api.cognitive.microsoft.com"
        )
        self._base_url = f"{base}/speechtotext/v3.2/transcriptions"
        self._container = app_settings.azure_storage_container_name
        self._use_key = bool(app_settings.whisper_speech_key)
        self._key = app_settings.whisper_speech_key
        self._conn_str = app_settings.azure_storage_connection_string
        self._account_name = app_settings.azure_storage_account_name
        self._whisper_model_uri: str | None = None

    # ------------------------------------------------------------------
    # Whisper model discovery
    # ------------------------------------------------------------------

    async def _resolve_whisper_model(self, session: aiohttp.ClientSession) -> str:
        """Discover or return cached Whisper base-model URI."""
        if self._whisper_model_uri:
            return self._whisper_model_uri

        base = (
            app_settings.whisper_speech_endpoint.rstrip("/")
            if app_settings.whisper_speech_endpoint
            else f"https://{self._region}.api.cognitive.microsoft.com"
        )

        if app_settings.azure_whisper_model_id:
            self._whisper_model_uri = (
                f"{base}/speechtotext/models/base/"
                f"{app_settings.azure_whisper_model_id}"
                f"?api-version=2024-11-15"
            )
            return self._whisper_model_uri

        # Auto-discover: paginate through all base models to find Whisper
        whisper_models: list[dict] = []
        skip = 0
        while True:
            url = f"{base}/speechtotext/models/base?api-version=2024-11-15&skip={skip}&top=100"
            async with session.get(url, headers=self._headers()) as resp:
                resp.raise_for_status()
                data = await resp.json()
            models = data.get("values", [])
            if not models:
                break
            for m in models:
                if "whisper" in m.get("displayName", "").lower():
                    whisper_models.append(m)
            # Stop early once we've found Whisper models and passed them
            if whisper_models and not any("whisper" in m.get("displayName", "").lower() for m in models):
                break
            skip += len(models)

        if not whisper_models:
            raise RuntimeError(
                "No Whisper base model found in this Speech resource region"
            )

        whisper_models.sort(
            key=lambda m: m.get("createdDateTime", ""), reverse=True
        )
        self._whisper_model_uri = whisper_models[0]["self"]
        logger.info("Discovered Whisper model: %s", self._whisper_model_uri)
        return self._whisper_model_uri

    # ------------------------------------------------------------------
    # Override batch-job creation for Whisper-specific payload
    # ------------------------------------------------------------------

    async def _create_batch_job(
        self,
        sas_url: str,
        language: str | None,
        session: aiohttp.ClientSession,
        settings: dict | None = None,
    ) -> str:
        """Create a batch transcription job with the Whisper model reference."""
        s = settings or {}
        model_uri = await self._resolve_whisper_model(session)

        body: dict = {
            "contentUrls": [sas_url],
            "displayName": f"whisper-{uuid.uuid4().hex[:8]}",
            "model": {"self": model_uri},
            "properties": {
                "displayFormWordLevelTimestampsEnabled": s.get(
                    "word_level_timestamps", False
                ),
                "profanityFilterMode": s.get("profanity_filter", "None"),
                "timeToLiveHours": 1,
            },
        }
        if language:
            body["locale"] = language
        else:
            body["locale"] = "en-US"

        async with session.post(
            self._base_url, json=body, headers=self._headers()
        ) as resp:
            if resp.status >= 400:
                body_text = await resp.text()
                logger.error(
                    "Whisper batch create %s: %s", resp.status, body_text
                )
            resp.raise_for_status()
            data = await resp.json()
            return data["self"]

    # ------------------------------------------------------------------
    # Override result parsing — Whisper uses display field (lexical empty)
    # ------------------------------------------------------------------

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None,
        settings: dict | None = None,
    ) -> TranscriptionResult:
        sas_url = await asyncio.to_thread(self._upload_to_blob, audio_path)

        async with aiohttp.ClientSession() as session:
            transcription_url = await self._create_batch_job(
                sas_url, language, session, settings=settings
            )
            job = await self._poll_until_done(transcription_url, session)

            if job["status"] != "Succeeded":
                error_msg = (
                    job.get("properties", {})
                    .get("error", {})
                    .get("message", "Whisper batch transcription failed")
                )
                raise RuntimeError(error_msg)

            results_data = await self._fetch_results(transcription_url, session)

        segments: list[Segment] = []
        all_text_parts: list[str] = []
        detected_lang: str | None = None

        for result in results_data:
            for combined in result.get("combinedRecognizedPhrases", []):
                all_text_parts.append(combined.get("display", ""))
                if not detected_lang:
                    detected_lang = combined.get("locale")

            for phrase in result.get("recognizedPhrases", []):
                best = phrase.get("nBest", [{}])[0]
                if "offsetInTicks" in phrase:
                    start = phrase["offsetInTicks"] / TICKS_PER_SECOND
                    end = start + phrase.get("durationInTicks", 0) / TICKS_PER_SECOND
                else:
                    start = phrase.get("offsetMilliseconds", 0) / 1000.0
                    end = start + phrase.get("durationMilliseconds", 0) / 1000.0
                # Whisper: lexical is empty, use display
                text = best.get("display", "")
                if text:
                    segments.append(
                        Segment(
                            start_time=round(start, 3),
                            end_time=round(end, 3),
                            text=text,
                        )
                    )
                if not detected_lang:
                    detected_lang = phrase.get("locale")

        return TranscriptionResult(
            segments=segments,
            full_text=(
                " ".join(all_text_parts)
                if all_text_parts
                else " ".join(s.text for s in segments)
            ),
            detected_language=detected_lang,
        )
