# MAI_transcribe — Architecture

> PoC: Audio transcription comparison webapp — upload audio, transcribe with 7 engines, compare results with timecoded playback.

## Directory Structure

```
MAI_transcribe/
├── ARCHITECTURE.md          # This file
├── API_CONTRACT.md          # REST API specification
├── requirements.txt         # Python backend dependencies
├── .env.example             # Environment variable template
│
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings (env vars, constants)
│   ├── routers/
│   │   ├── upload.py        # POST /api/upload
│   │   └── transcribe.py    # POST /api/transcribe, GET /api/transcribe/{job_id}, etc.
│   ├── services/
│   │   ├── base.py          # Abstract base class for transcription services
│   │   ├── azure_stt_batch.py    # Azure STT — Batch Transcription
│   │   ├── azure_stt_fast.py     # Azure STT — Fast Transcription
│   │   ├── mai_transcribe.py     # MAI-Transcribe-1
│   │   ├── aoai_transcribe.py    # Azure OpenAI gpt-4o-transcribe
│   │   ├── voxtral_transcribe.py # Voxtral Mini via Azure Foundry
│   │   ├── whisper_transcribe.py  # Azure OpenAI Whisper
│   │   └── llm_speech.py         # LLM Speech (Fast Transcription enhanced mode)
│   ├── models/
│   │   └── schemas.py       # Pydantic request/response models
│   └── utils/
│       ├── audio.py         # Audio file validation & metadata
│       └── storage.py       # Local file storage helpers
│
├── frontend/
│   ├── index.html           # Single-page app
│   ├── css/
│   │   └── style.css        # Styles
│   └── js/
│       ├── app.js           # Main application logic
│       ├── api.js           # Backend API client
│       └── player.js        # Audio player with timecode sync
│
└── uploads/                 # Temporary audio file storage (gitignored)
```

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Backend framework** | FastAPI | Async-native, built-in file upload support, auto-generated OpenAPI docs, background tasks |
| **Python version** | 3.11+ | Required by latest Azure SDKs |
| **Frontend** | Vanilla HTML / JS / CSS | PoC-scoped — no build step, no framework overhead |
| **Audio player** | [wavesurfer.js](https://wavesurfer.xyz/) (v7) | Waveform visualization, region/segment highlighting, timecode seeking — loaded via CDN |
| **File storage** | Local filesystem (`uploads/`) | PoC-scoped — no blob storage needed for the app itself |
| **Job state** | In-memory dict | PoC-scoped — no database. State lost on restart, which is acceptable |
| **Task execution** | `asyncio.create_task` | Run transcriptions concurrently per job; FastAPI's async loop handles it |

## Transcription Service Integration

All 7 services implement a common `TranscriptionService` base class:

```python
class TranscriptionService(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, language: str | None) -> TranscriptionResult:
        """Returns normalized segments with timecodes."""
```

### 1. Azure STT — Batch Transcription

| Detail | Value |
|--------|-------|
| **SDK/API** | REST API v2025-10-15 (`speechtotext/v3.2/transcriptions`) |
| **Auth** | `DefaultAzureCredential` bearer token (falls back to `Ocp-Apim-Subscription-Key` if `AZURE_SPEECH_KEY` set) |
| **Flow** | Upload audio to Azure Blob (or use SAS URL) → create batch transcription job → poll status → fetch results |
| **Timecodes** | Response includes `offsetInTicks` and `durationInTicks` (100ns units) — normalize to seconds |
| **Latency** | Slowest of the 5; async by nature (minutes). Poll every 5s. |
| **Key env vars** | `AZURE_SPEECH_REGION`, `AZURE_STORAGE_ACCOUNT_NAME`, `AZURE_STORAGE_CONTAINER_NAME` |
| **Notes** | Requires a Blob Storage container for audio input. Uses user-delegation SAS (managed identity) or account-key SAS (connection string fallback). |

### 2. Azure STT — Fast Transcription

| Detail | Value |
|--------|-------|
| **SDK/API** | REST API v2025-10-15 (`speechtotext/transcriptions:transcribe`) |
| **Auth** | `DefaultAzureCredential` bearer token (falls back to `Ocp-Apim-Subscription-Key` if `AZURE_SPEECH_KEY` set) |
| **Flow** | Synchronous — POST multipart/form-data with audio file + JSON definition → get result immediately |
| **Timecodes** | Response includes `offsetInTicks` and `durationInTicks` per phrase — normalize to seconds |
| **Latency** | Fast — faster-than-real-time. Up to 2h / 300MB audio. |
| **Key env vars** | `AZURE_SPEECH_REGION` |
| **Supported regions** | East US, West Europe, Southeast Asia, Central India (check latest docs) |

### 3. MAI-Transcribe-1

| Detail | Value |
|--------|-------|
| **SDK/API** | Same Fast Transcription REST endpoint with `enhancedMode` |
| **Auth** | `DefaultAzureCredential` bearer token (falls back to `Ocp-Apim-Subscription-Key` if `AZURE_SPEECH_KEY` set) |
| **Flow** | Same as Fast Transcription but with `definition: { "enhancedMode": { "enabled": true, "model": "mai-transcribe-1" } }` |
| **Timecodes** | Same response format as Fast Transcription — offset/duration in ticks |
| **Latency** | Fast — up to ~69x real-time |
| **Key env vars** | `AZURE_SPEECH_REGION` |
| **Notes** | Uses the same Speech resource as Fast Transcription. The model flag selects MAI-Transcribe-1 vs standard. |

### 4. Azure OpenAI — gpt-4o-transcribe

| Detail | Value |
|--------|-------|
| **SDK/API** | `openai` Python SDK (Azure-configured) |
| **Auth** | `DefaultAzureCredential` via `azure_ad_token_provider` (falls back to API key if `AZURE_OPENAI_API_KEY` set) |
| **Flow** | `client.audio.transcriptions.create(model="gpt-4o-transcribe", file=audio, response_format="verbose_json")` |
| **Timecodes** | With `response_format="verbose_json"`, response includes `segments[]` with `start` and `end` in seconds |
| **Latency** | Moderate — synchronous call |
| **Key env vars** | `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME` |
| **Notes** | Set `timestamp_granularities=["segment"]` for segment-level timecodes. Max file size ~25MB (compress if needed). |

### 5. Voxtral Mini — via Azure Foundry

| Detail | Value |
|--------|-------|
| **SDK/API** | `azure-ai-inference` SDK or REST (chat completions with audio) |
| **Auth** | `DefaultAzureCredential` (falls back to endpoint key if `VOXTRAL_ENDPOINT_KEY` set) |
| **Flow** | Deploy Voxtral Mini as serverless endpoint in Azure Foundry → send audio as base64 in chat completion request → parse transcription from response |
| **Timecodes** | Model may not natively provide timecodes — prompt for timestamps or post-process. Fallback: assign full-duration single segment. |
| **Latency** | Variable — depends on deployment SKU |
| **Key env vars** | `VOXTRAL_ENDPOINT_URL` |
| **Notes** | Voxtral is a chat model that accepts audio input, not a dedicated STT API. Transcription is extracted from the text response. Timecode granularity may be limited. |

### 6. Azure OpenAI — Whisper

| Detail | Value |
|--------|-------|
| **SDK/API** | `openai` Python SDK (Azure-configured) |
| **Auth** | `DefaultAzureCredential` via `azure_ad_token_provider` (falls back to API key if `AZURE_OPENAI_API_KEY` set) |
| **Flow** | `client.audio.transcriptions.create(model="whisper", file=audio, response_format="verbose_json", timestamp_granularities=["segment"])` |
| **Timecodes** | `verbose_json` returns `segments[]` with `start` and `end` in seconds — pass through |
| **Latency** | Fast — synchronous call |
| **Key env vars** | `AZURE_OPENAI_ENDPOINT`, `AZURE_WHISPER_DEPLOYMENT_NAME` |
| **Notes** | Uses same Azure OpenAI resource as gpt-4o-transcribe. Unlike gpt-4o-transcribe, Whisper natively supports `verbose_json` with segment-level timecodes. Language param uses ISO-639-1 (`en`, `fr`). |

### 7. LLM Speech — Azure Fast Transcription Enhanced Mode

| Detail | Value |
|--------|-------|
| **SDK/API** | REST API v2025-10-15 (`speechtotext/transcriptions:transcribe`) |
| **Auth** | `DefaultAzureCredential` bearer token (falls back to `Ocp-Apim-Subscription-Key` if `AZURE_SPEECH_KEY` set) |
| **Flow** | Same endpoint as Fast Transcription but with `definition: { "enhancedMode": { "enabled": true, "task": "transcribe" } }` |
| **Timecodes** | Same response format as Fast Transcription — offset/duration in milliseconds |
| **Latency** | Fast — synchronous |
| **Key env vars** | `AZURE_SPEECH_ENDPOINT` |
| **Notes** | Uses same Speech resource as Fast Transcription. No `locales` needed — language detection is automatic. Different from MAI-Transcribe-1 which uses `"model": "mai-transcribe-1"`. Reuses `AzureSttFastService._parse_result()`. |

## Timecode Format (Normalized)

All services normalize their output to this common segment format:

```json
{
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 2.54,
      "text": "Hello, welcome to the demo."
    },
    {
      "start_time": 2.54,
      "end_time": 5.12,
      "text": "This is a transcription test."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | `float` | Segment start in **seconds** from audio beginning |
| `end_time` | `float` | Segment end in **seconds** from audio beginning |
| `text` | `string` | Transcribed text for this segment |

**Normalization rules per service:**
- Azure STT (Batch/Fast/MAI): Convert `offsetInTicks` and `durationInTicks` from 100ns units → seconds (`/ 10_000_000`)
- Azure OpenAI (gpt-4o-transcribe): Already in seconds — pass through
- Whisper: `verbose_json` returns `segments[]` with `start`/`end` in seconds — pass through
- Voxtral: Parse from model response or assign single segment spanning full audio duration
- LLM Speech: Same response format as Fast Transcription — reuses `AzureSttFastService._parse_result()`

## Job Lifecycle

```
UPLOAD → PENDING → PROCESSING → COMPLETED / FAILED
```

1. **Upload**: Audio file saved to `uploads/{file_id}.{ext}`, metadata stored in memory
2. **Transcribe**: Job created with selected methods. Each method runs as a concurrent async task.
3. **Poll**: Client polls `GET /api/transcribe/{job_id}` for status of each method
4. **Results**: When all (or any) methods complete, results available via `GET /api/transcribe/{job_id}/results`

Each method within a job has independent status:
```json
{
  "azure_stt_batch": "processing",
  "azure_stt_fast": "completed",
  "mai_transcribe": "completed",
  "aoai_transcribe": "failed",
  "voxtral": "processing",
  "whisper": "completed",
  "llm_speech": "processing"
}
```

## Error Handling Strategy

| Scenario | Handling |
|----------|----------|
| **Invalid audio format** | Return 400 with clear error at upload time (validate extension + basic header check) |
| **File too large** | Return 413 — cap at 300MB (largest service limit) |
| **Service auth failure** | Return method-level error in results (`"error": "Authentication failed for Azure STT"`) — don't fail the whole job |
| **Service timeout** | 5-minute timeout per method. Mark as `"failed"` with timeout message. |
| **Service unavailable** | Mark method as `"failed"` with error detail. Other methods continue. |
| **Partial failure** | Job status = `"completed"` if ≥1 method succeeded. `"failed"` only if ALL methods failed. |
| **Unknown errors** | Log full traceback server-side. Return sanitized error to client. |

**Principle**: Each transcription method is independent. One method failing never blocks or cancels others.

## Environment Variables

All Azure services authenticate via **`DefaultAzureCredential`** from the
`azure-identity` SDK.  In Azure this resolves to managed identity; locally it
uses your `az login` / VS Code credential.  No API keys or connection strings
are required.

If you *do* set a legacy key variable (e.g. `AZURE_SPEECH_KEY`) it is used as
a fallback — convenient for quick local testing without `az login`.

```bash
# Azure Speech Services (used by Batch, Fast, and MAI-Transcribe-1)
# AZURE_SPEECH_KEY=              # optional fallback
AZURE_SPEECH_REGION=eastus

# Azure Blob Storage (used by Batch Transcription only)
AZURE_STORAGE_ACCOUNT_NAME=      # required — storage account name for blob URL
# AZURE_STORAGE_CONNECTION_STRING= # optional fallback
AZURE_STORAGE_CONTAINER_NAME=transcription-audio

# Azure OpenAI (used by gpt-4o-transcribe and Whisper)
# AZURE_OPENAI_API_KEY=          # optional fallback
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o-transcribe
AZURE_WHISPER_DEPLOYMENT_NAME=whisper

# Voxtral Mini (Azure Foundry deployment)
VOXTRAL_ENDPOINT_URL=
# VOXTRAL_ENDPOINT_KEY=          # optional fallback
```

## Future Considerations (Out of PoC Scope)

- Persistent storage (database for jobs, blob storage for audio)
- User authentication
- WebSocket for real-time progress updates (replacing polling)
- Audio format conversion pipeline (ffmpeg)
- Deployment to Azure App Service or Container Apps
- Cost tracking per transcription method
