# MAI_transcribe — API Contract

> REST API specification for the transcription comparison backend.
> Base URL: `http://localhost:8000`

---

## Endpoints Overview

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload an audio file |
| `POST` | `/api/transcribe` | Start transcription job |
| `GET` | `/api/transcribe/{job_id}` | Get job status |
| `GET` | `/api/transcribe/{job_id}/results` | Get transcription results |
| `DELETE` | `/api/transcribe/{job_id}` | Cancel/delete a job |
| `GET` | `/api/health` | Health check |

---

## 1. Upload Audio File

### `POST /api/upload`

Upload an audio file for later transcription.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` — the audio file

**Constraints:**
- Max file size: 300 MB
- Accepted formats: `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`, `.webm`

**Response: `200 OK`**
```json
{
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "filename": "meeting_recording.wav",
  "size_bytes": 15234567,
  "duration_seconds": 124.5,
  "format": "wav",
  "uploaded_at": "2025-01-15T10:30:00Z"
}
```

**Error: `400 Bad Request`**
```json
{
  "detail": "Unsupported audio format. Accepted: wav, mp3, flac, ogg, m4a, webm"
}
```

**Error: `413 Request Entity Too Large`**
```json
{
  "detail": "File size exceeds 300MB limit"
}
```

---

## 2. Start Transcription

### `POST /api/transcribe`

Start transcription of an uploaded file using one or more methods.

**Request:**
```json
{
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "methods": [
    "azure_stt_batch",
    "azure_stt_fast",
    "mai_transcribe",
    "aoai_transcribe",
    "voxtral"
  ],
  "language": "en-US"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_id` | `string` (UUID) | Yes | ID returned from upload |
| `methods` | `string[]` | Yes | Which transcription engines to use. At least one required. |
| `language` | `string \| null` | No | BCP-47 language code (e.g., `"en-US"`, `"fr-FR"`, `"ja-JP"`). If omitted or `null`, services will attempt auto-detection. |

**Valid method identifiers:**
- `azure_stt_batch` — Azure STT Batch Transcription
- `azure_stt_fast` — Azure STT Fast Transcription
- `mai_transcribe` — MAI-Transcribe-1
- `aoai_transcribe` — Azure OpenAI gpt-4o-transcribe
- `voxtral` — Voxtral Mini via Azure Foundry

**Response: `202 Accepted`**
```json
{
  "job_id": "f8e7d6c5-b4a3-2109-8765-432109876543",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "methods": {
    "azure_stt_fast": "processing",
    "mai_transcribe": "processing",
    "aoai_transcribe": "processing"
  },
  "language": "en-US",
  "created_at": "2025-01-15T10:31:00Z"
}
```

**Error: `404 Not Found`**
```json
{
  "detail": "File not found: a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Error: `400 Bad Request`**
```json
{
  "detail": "Invalid method: 'whisper'. Valid methods: azure_stt_batch, azure_stt_fast, mai_transcribe, aoai_transcribe, voxtral"
}
```

---

## 3. Get Job Status

### `GET /api/transcribe/{job_id}`

Poll the status of a transcription job.

**Response: `200 OK`** (in progress)
```json
{
  "job_id": "f8e7d6c5-b4a3-2109-8765-432109876543",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "methods": {
    "azure_stt_fast": "completed",
    "mai_transcribe": "completed",
    "aoai_transcribe": "processing"
  },
  "language": "en-US",
  "created_at": "2025-01-15T10:31:00Z"
}
```

**Response: `200 OK`** (all done)
```json
{
  "job_id": "f8e7d6c5-b4a3-2109-8765-432109876543",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "methods": {
    "azure_stt_fast": "completed",
    "mai_transcribe": "completed",
    "aoai_transcribe": "failed"
  },
  "language": "en-US",
  "created_at": "2025-01-15T10:31:00Z"
}
```

**Job-level `status` values:**
- `pending` — job created, not yet started
- `processing` — at least one method still running
- `completed` — all methods finished (some may have failed)
- `failed` — all methods failed

**Method-level status values:**
- `pending` — queued, not started
- `processing` — actively transcribing
- `completed` — transcription succeeded
- `failed` — transcription failed

**Error: `404 Not Found`**
```json
{
  "detail": "Job not found: f8e7d6c5-b4a3-2109-8765-432109876543"
}
```

---

## 4. Get Transcription Results

### `GET /api/transcribe/{job_id}/results`

Retrieve transcription results for all completed methods.

**Query parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `method` | `string` | No | Filter to a single method's results |

**Response: `200 OK`** (all results)
```json
{
  "job_id": "f8e7d6c5-b4a3-2109-8765-432109876543",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "language": "en-US",
  "results": {
    "azure_stt_fast": {
      "status": "completed",
      "full_text": "Hello, welcome to the demo. This is a transcription test.",
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
      ],
      "duration_seconds": 1.23,
      "detected_language": "en-US"
    },
    "mai_transcribe": {
      "status": "completed",
      "full_text": "Hello. Welcome to the demo. This is a transcription test.",
      "segments": [
        {
          "start_time": 0.0,
          "end_time": 2.50,
          "text": "Hello. Welcome to the demo."
        },
        {
          "start_time": 2.50,
          "end_time": 5.10,
          "text": "This is a transcription test."
        }
      ],
      "duration_seconds": 0.98,
      "detected_language": "en-US"
    },
    "aoai_transcribe": {
      "status": "failed",
      "error": "Service timeout after 300 seconds",
      "segments": [],
      "full_text": null,
      "duration_seconds": null,
      "detected_language": null
    }
  }
}
```

**Response: `200 OK`** (filtered to one method)

`GET /api/transcribe/{job_id}/results?method=azure_stt_fast`

```json
{
  "job_id": "f8e7d6c5-b4a3-2109-8765-432109876543",
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "language": "en-US",
  "results": {
    "azure_stt_fast": {
      "status": "completed",
      "full_text": "Hello, welcome to the demo. This is a transcription test.",
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
      ],
      "duration_seconds": 1.23,
      "detected_language": "en-US"
    }
  }
}
```

---

## 5. Delete Job

### `DELETE /api/transcribe/{job_id}`

Cancel a running job or delete a completed one. Also removes the uploaded audio file if no other jobs reference it.

**Response: `200 OK`**
```json
{
  "detail": "Job f8e7d6c5-b4a3-2109-8765-432109876543 deleted"
}
```

---

## 6. Health Check

### `GET /api/health`

Simple health check for the backend.

**Response: `200 OK`**
```json
{
  "status": "ok",
  "services": {
    "azure_stt_batch": "configured",
    "azure_stt_fast": "configured",
    "mai_transcribe": "configured",
    "aoai_transcribe": "configured",
    "voxtral": "not_configured"
  }
}
```

Service status values:
- `configured` — required env vars are set
- `not_configured` — missing env vars (method will fail if selected)

---

## 7. Serve Audio File

### `GET /api/audio/{file_id}`

Stream the uploaded audio file to the frontend for playback.

**Response: `200 OK`**
- Content-Type: appropriate audio MIME type (`audio/wav`, `audio/mpeg`, etc.)
- Body: audio file stream
- Supports `Range` header for seeking

**Error: `404 Not Found`**
```json
{
  "detail": "File not found"
}
```

---

## Common Types

### Segment

```json
{
  "start_time": 0.0,
  "end_time": 2.54,
  "text": "Hello, welcome to the demo."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | `float` | Start time in seconds |
| `end_time` | `float` | End time in seconds |
| `text` | `string` | Transcribed text for this segment |

### MethodResult

```json
{
  "status": "completed",
  "full_text": "Full concatenated transcript",
  "segments": [ ... ],
  "duration_seconds": 1.23,
  "detected_language": "en-US",
  "error": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | `string` | `completed` or `failed` |
| `full_text` | `string \| null` | Full transcript text (null if failed) |
| `segments` | `Segment[]` | Array of timecoded segments (empty if failed) |
| `duration_seconds` | `float \| null` | Processing time in seconds (null if failed) |
| `detected_language` | `string \| null` | Language detected by the service |
| `error` | `string \| null` | Error message if failed |

### Valid Method Identifiers

| Identifier | Service |
|------------|---------|
| `azure_stt_batch` | Azure Speech-to-Text Batch Transcription |
| `azure_stt_fast` | Azure Speech-to-Text Fast Transcription |
| `mai_transcribe` | MAI-Transcribe-1 |
| `aoai_transcribe` | Azure OpenAI gpt-4o-transcribe |
| `voxtral` | Voxtral Mini via Azure Foundry |

---

## CORS

The backend must allow CORS from `http://localhost:*` for local PoC development. FastAPI `CORSMiddleware` configured with:
- `allow_origins=["*"]`
- `allow_methods=["*"]`
- `allow_headers=["*"]`

## Polling Strategy

Frontend should poll `GET /api/transcribe/{job_id}` every **3 seconds** while `status` is `"processing"`. Stop polling when status is `"completed"` or `"failed"`, then fetch results.
