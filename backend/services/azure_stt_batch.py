"""Azure Speech-to-Text Batch Transcription service.

Flow: upload audio to Blob Storage → create batch job via REST v3.2 → poll → fetch results.
Timecodes arrive as offsetInTicks / durationInTicks (100 ns units) and are normalised to seconds.

Auth: ``DefaultAzureCredential`` (managed identity / Azure CLI).
Falls back to API key if ``AZURE_SPEECH_KEY`` is set.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

from backend.config import settings, get_cognitive_services_token
from backend.models.schemas import Segment
from backend.services.base import TranscriptionResult, TranscriptionService

logger = logging.getLogger(__name__)

TICKS_PER_SECOND = 10_000_000


class AzureSttBatchService(TranscriptionService):
    """Azure Speech-to-Text — Batch Transcription (REST API v3.2)."""

    def __init__(self) -> None:
        self._region = settings.azure_speech_region
        base = settings.azure_speech_endpoint.rstrip("/") if settings.azure_speech_endpoint else f"https://{self._region}.api.cognitive.microsoft.com"
        self._base_url = f"{base}/speechtotext/v3.2/transcriptions"
        self._container = settings.azure_storage_container_name
        self._use_key = bool(settings.azure_speech_key)
        self._key = settings.azure_speech_key
        self._conn_str = settings.azure_storage_connection_string
        self._account_name = settings.azure_storage_account_name

    # --- Blob helpers ---

    def _get_blob_service_client(self) -> BlobServiceClient:
        """Build a BlobServiceClient using managed identity or connection string fallback."""
        if self._conn_str:
            return BlobServiceClient.from_connection_string(self._conn_str)
        account_url = f"https://{self._account_name}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())

    def _get_blob_client(self, blob_name: str):
        service = self._get_blob_service_client()
        container = service.get_container_client(self._container)
        try:
            container.get_container_properties()
        except Exception:
            container.create_container()
        return service, container.get_blob_client(blob_name)

    def _upload_to_blob(self, audio_path: str) -> str:
        """Upload file to blob and return a SAS URL valid for 1 hour."""
        blob_name = f"{uuid.uuid4().hex}_{Path(audio_path).name}"
        service, blob_client = self._get_blob_client(blob_name)
        with open(audio_path, "rb") as f:
            blob_client.upload_blob(f, overwrite=True)

        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        if self._conn_str:
            # Fallback: account-key SAS
            sas = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self._container,
                blob_name=blob_name,
                account_key=service.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )
        else:
            # Managed identity: user-delegation-key SAS
            delegation_key = service.get_user_delegation_key(
                key_start_time=datetime.now(timezone.utc),
                key_expiry_time=expiry,
            )
            sas = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self._container,
                blob_name=blob_name,
                user_delegation_key=delegation_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )
        return f"{blob_client.url}?{sas}"

    # --- REST helpers ---

    def _headers(self) -> dict:
        if self._use_key:
            return {
                "Ocp-Apim-Subscription-Key": self._key,
                "Content-Type": "application/json",
            }
        token = get_cognitive_services_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _create_batch_job(
        self, sas_url: str, language: str | None, session: aiohttp.ClientSession
    ) -> str:
        """Create a batch transcription job. Returns the transcription URL for polling."""
        body: dict = {
            "contentUrls": [sas_url],
            "displayName": f"mai-transcribe-{uuid.uuid4().hex[:8]}",
            "properties": {
                "wordLevelTimestampsEnabled": False,
                "punctuationMode": "DictatedAndAutomatic",
                "profanityFilterMode": "None",
            },
        }
        if language:
            body["locale"] = language
        else:
            body["locale"] = "en-US"
            body["properties"]["languageIdentification"] = {
                "candidateLocales": [
                    "en-US", "fr-FR", "de-DE", "es-ES", "ja-JP",
                    "zh-CN", "ko-KR", "pt-BR", "it-IT", "nl-NL",
                ]
            }

        async with session.post(
            self._base_url, json=body, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["self"]

    async def _poll_until_done(
        self, transcription_url: str, session: aiohttp.ClientSession
    ) -> dict:
        """Poll the batch job until it reaches a terminal state."""
        while True:
            async with session.get(
                transcription_url, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                status = data["status"]
                if status in ("Succeeded", "Failed"):
                    return data
            await asyncio.sleep(settings.batch_poll_interval_seconds)

    async def _fetch_results(
        self, transcription_url: str, session: aiohttp.ClientSession
    ) -> list[dict]:
        """Fetch the results files from a succeeded batch job."""
        files_url = f"{transcription_url}/files"
        async with session.get(files_url, headers=self._headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()

        results = []
        for f in data.get("values", []):
            if f.get("kind") == "Transcription":
                content_url = f["links"]["contentUrl"]
                # contentUrl is a SAS URL with embedded auth — do NOT send our headers
                async with session.get(content_url) as r:
                    r.raise_for_status()
                    results.append(await r.json())
        return results

    # --- Main entry point ---

    async def transcribe(
        self, audio_path: str, language: str | None = None
    ) -> TranscriptionResult:
        sas_url = await asyncio.to_thread(self._upload_to_blob, audio_path)

        async with aiohttp.ClientSession() as session:
            transcription_url = await self._create_batch_job(sas_url, language, session)
            job = await self._poll_until_done(transcription_url, session)

            if job["status"] != "Succeeded":
                error_msg = job.get("properties", {}).get("error", {}).get(
                    "message", "Batch transcription failed"
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
                # v3.2 batch API may use ticks or milliseconds depending on version
                if "offsetInTicks" in phrase:
                    start = phrase["offsetInTicks"] / TICKS_PER_SECOND
                    end = start + phrase.get("durationInTicks", 0) / TICKS_PER_SECOND
                else:
                    start = phrase.get("offsetMilliseconds", 0) / 1000.0
                    end = start + phrase.get("durationMilliseconds", 0) / 1000.0
                text = best.get("display", "")
                if text:
                    segments.append(Segment(start_time=round(start, 3), end_time=round(end, 3), text=text))
                if not detected_lang:
                    detected_lang = phrase.get("locale")

        return TranscriptionResult(
            segments=segments,
            full_text=" ".join(all_text_parts) if all_text_parts else " ".join(s.text for s in segments),
            detected_language=detected_lang,
        )
