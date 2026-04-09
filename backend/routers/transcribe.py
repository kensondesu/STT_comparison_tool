"""Transcribe router — job lifecycle + health check."""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.config import settings
from backend.models.schemas import (
    HealthResponse,
    JobStatus,
    JobStatusValue,
    MethodName,
    MethodResult,
    Segment,
    ServiceConfigStatus,
    TranscribeRequest,
    TranscriptionResults,
)
from backend.routers.upload import file_registry
from backend.services.azure_stt_batch import AzureSttBatchService
from backend.services.azure_stt_fast import AzureSttFastService
from backend.services.mai_transcribe import MaiTranscribeService
from backend.services.aoai_transcribe import AoaiTranscribeService
from backend.services.voxtral_transcribe import VoxtralTranscribeService
from backend.services.whisper_transcribe import WhisperTranscribeService
from backend.services.llm_speech import LlmSpeechService
from backend.services.base import TranscriptionService
from backend.utils.storage import find_file, delete_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["transcribe"])

# In-memory job store
_jobs: dict[str, JobStatus] = {}
_results: dict[str, dict[str, MethodResult]] = {}

SERVICE_MAP: dict[str, type[TranscriptionService]] = {
    "azure_stt_batch": AzureSttBatchService,
    "azure_stt_fast": AzureSttFastService,
    "mai_transcribe": MaiTranscribeService,
    "aoai_transcribe": AoaiTranscribeService,
    "voxtral": VoxtralTranscribeService,
    "whisper": WhisperTranscribeService,
    "llm_speech": LlmSpeechService,
}

VALID_METHODS = list(SERVICE_MAP.keys())


def _compute_job_status(methods: dict[str, JobStatusValue]) -> JobStatusValue:
    """Derive aggregate job status from individual method statuses."""
    statuses = set(methods.values())
    if all(s in (JobStatusValue.completed, JobStatusValue.failed) for s in statuses):
        if all(s == JobStatusValue.failed for s in statuses):
            return JobStatusValue.failed
        return JobStatusValue.completed
    if any(s in (JobStatusValue.processing, JobStatusValue.pending) for s in statuses):
        return JobStatusValue.processing
    return JobStatusValue.completed


async def _run_method(
    job_id: str, method: str, audio_path: str, language: str | None
) -> None:
    """Execute a single transcription method and store the result."""
    service = SERVICE_MAP[method]()
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            service.transcribe(audio_path, language),
            timeout=settings.method_timeout_seconds,
        )
        elapsed = round(time.monotonic() - start, 2)
        _results[job_id][method] = MethodResult(
            status=JobStatusValue.completed,
            full_text=result.full_text,
            segments=result.segments,
            duration_seconds=elapsed,
            detected_language=result.detected_language,
        )
        _jobs[job_id].methods[method] = JobStatusValue.completed
    except asyncio.TimeoutError:
        _results[job_id][method] = MethodResult(
            status=JobStatusValue.failed,
            error=f"Service timeout after {settings.method_timeout_seconds} seconds",
        )
        _jobs[job_id].methods[method] = JobStatusValue.failed
    except Exception as exc:
        logger.exception("Method %s failed for job %s", method, job_id)
        _results[job_id][method] = MethodResult(
            status=JobStatusValue.failed,
            error=str(exc)[:500],
        )
        _jobs[job_id].methods[method] = JobStatusValue.failed
    finally:
        _jobs[job_id].status = _compute_job_status(_jobs[job_id].methods)


@router.post("/transcribe", response_model=JobStatus, status_code=202)
async def start_transcription(request: TranscribeRequest):
    """Start transcription of an uploaded file using selected methods."""
    file_id = request.file_id

    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    audio_path = find_file(file_id)
    if audio_path is None:
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    for m in request.methods:
        if m.value not in SERVICE_MAP:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid method: '{m.value}'. Valid methods: {', '.join(VALID_METHODS)}",
            )

    job_id = str(uuid.uuid4())
    method_statuses = {m.value: JobStatusValue.processing for m in request.methods}

    job = JobStatus(
        job_id=job_id,
        file_id=file_id,
        status=JobStatusValue.processing,
        methods=method_statuses,
        language=request.language,
        created_at=datetime.now(timezone.utc),
    )
    _jobs[job_id] = job
    _results[job_id] = {}

    for m in request.methods:
        asyncio.create_task(
            _run_method(job_id, m.value, str(audio_path), request.language)
        )

    return job


@router.get("/transcribe/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Poll the status of a transcription job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    job.status = _compute_job_status(job.methods)
    return job


@router.get("/transcribe/{job_id}/results", response_model=TranscriptionResults)
async def get_results(job_id: str, method: str | None = Query(default=None)):
    """Retrieve transcription results for completed methods."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    job_results = _results.get(job_id, {})

    if method:
        if method not in job.methods:
            raise HTTPException(
                status_code=400,
                detail=f"Method '{method}' was not requested for this job",
            )
        filtered = {method: job_results[method]} if method in job_results else {}
    else:
        filtered = dict(job_results)

    return TranscriptionResults(
        job_id=job_id,
        file_id=job.file_id,
        language=job.language,
        results=filtered,
    )


@router.delete("/transcribe/{job_id}")
async def delete_job(job_id: str):
    """Cancel a running job or delete a completed one."""
    job = _jobs.pop(job_id, None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    _results.pop(job_id, None)

    # Clean up audio if no other jobs reference this file
    file_id = job.file_id
    still_referenced = any(j.file_id == file_id for j in _jobs.values())
    if not still_referenced:
        delete_file(file_id)

    return {"detail": f"Job {job_id} deleted"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check — reports which services are configured."""

    def _configured(condition: bool) -> ServiceConfigStatus:
        return ServiceConfigStatus.configured if condition else ServiceConfigStatus.not_configured

    services = {
        "azure_stt_batch": _configured(
            bool(settings.azure_speech_key or settings.azure_speech_region)
            and bool(settings.azure_storage_connection_string or settings.azure_storage_account_name)
        ),
        "azure_stt_fast": _configured(bool(settings.azure_speech_key or settings.azure_speech_region)),
        "mai_transcribe": _configured(bool(settings.mai_speech_key or settings.mai_speech_endpoint)),
        "aoai_transcribe": _configured(
            bool(settings.azure_openai_endpoint)
        ),
        "voxtral": _configured(
            bool(settings.voxtral_endpoint_url)
        ),
        "whisper": _configured(
            bool(settings.azure_openai_endpoint)
        ),
        "llm_speech": _configured(
            bool(settings.azure_speech_endpoint or settings.azure_speech_key)
        ),
    }
    return HealthResponse(status="ok", services=services)
