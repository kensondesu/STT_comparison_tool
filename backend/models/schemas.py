"""Pydantic models matching the API contract."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MethodName(str, Enum):
    azure_stt_batch = "azure_stt_batch"
    azure_stt_fast = "azure_stt_fast"
    mai_transcribe = "mai_transcribe"
    aoai_transcribe = "aoai_transcribe"
    voxtral = "voxtral"
    whisper = "whisper"
    llm_speech = "llm_speech"


class JobStatusValue(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ServiceConfigStatus(str, Enum):
    configured = "configured"
    not_configured = "not_configured"


# --- Request models ---


class TranscribeRequest(BaseModel):
    file_id: str
    methods: list[MethodName]
    language: str | None = None
    method_settings: dict[str, dict] | None = None


# --- Response models ---


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    duration_seconds: float | None = None
    format: str
    uploaded_at: datetime


class Segment(BaseModel):
    start_time: float
    end_time: float
    text: str


class MethodResult(BaseModel):
    status: JobStatusValue
    full_text: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    duration_seconds: float | None = None
    detected_language: str | None = None
    error: str | None = None


class JobStatus(BaseModel):
    job_id: str
    file_id: str
    status: JobStatusValue
    methods: dict[str, JobStatusValue]
    language: str | None = None
    created_at: datetime


class TranscriptionResults(BaseModel):
    job_id: str
    file_id: str
    language: str | None = None
    results: dict[str, MethodResult]


class HealthResponse(BaseModel):
    status: str = "ok"
    services: dict[str, ServiceConfigStatus]
