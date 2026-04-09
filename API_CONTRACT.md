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
    "voxtral",
    "whisper",
    "llm_speech"
  ],
  "language": "en-US"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_id` | `string` (UUID) | Yes | ID returned from upload |
| `methods` | `string[]` | Yes | Which transcription engines to use. At least one required. |
| `language` | `string \| null` | No | BCP-47 language code (e.g., `"en-US"`, `"fr-FR"`, `"ja-JP"`). If omitted or `null`, services will attempt auto-detection. |
| `method_settings` | `object \| null` | No | Per-method custom settings. Keys are method identifiers, values are setting objects. See [Method Settings](#method-settings). |

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
  "detail": "Invalid method: 'foo'. Valid methods: azure_stt_batch, azure_stt_fast, mai_transcribe, aoai_transcribe, voxtral, whisper, llm_speech"
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
    "voxtral": "not_configured",
    "whisper": "configured",
    "llm_speech": "configured"
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
| `whisper` | Azure OpenAI Whisper |
| `llm_speech` | LLM Speech (Azure Fast Transcription enhanced mode) |

---

## Method Settings

The optional `method_settings` field in `POST /api/transcribe` allows passing per-method configuration. Keys are method identifiers; values are objects with method-specific parameters. Unknown keys are silently ignored. When `method_settings` is omitted or `null`, all methods use their defaults.

**Example request:**
```json
{
  "file_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "methods": ["azure_stt_fast", "whisper"],
  "language": "en-US",
  "method_settings": {
    "azure_stt_fast": {
      "phrase_list": ["Contoso", "Azure"],
      "diarization_enabled": true,
      "diarization_max_speakers": 4,
      "profanity_filter": "Masked",
      "language_autodetect": true
    },
    "whisper": {
      "prompt": "Technical meeting about Azure cloud services",
      "temperature": 0.2
    }
  }
}
```

### Settings per Method

#### `azure_stt_fast`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `phrase_list` | `string[]` | — | Custom phrases/vocabulary to boost recognition accuracy |
| `profanity_filter` | `string` | `None` | Profanity filter mode: `"None"`, `"Masked"`, `"Removed"`, `"Tags"` |
| `diarization_enabled` | `bool` | `false` | Enable speaker diarization |
| `diarization_max_speakers` | `int` | `4` | Maximum number of speakers (used when diarization is enabled) |
| `language_autodetect` | `bool` | `true` | When `false` and `language` is set, disables language auto-detection |

#### `azure_stt_batch`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `profanity_filter` | `string` | `"None"` | Profanity filter mode: `"None"`, `"Masked"`, `"Removed"`, `"Tags"` |
| `word_level_timestamps` | `bool` | `false` | Enable word-level timestamp output |

#### `mai_transcribe`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `profanity_filter` | `string` | — | Profanity filter mode: `"None"`, `"Masked"`, `"Removed"`, `"Tags"` |

#### `llm_speech`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `prompt` | `list[str]` | — | Prompt hints for the enhanced mode |
| `task` | `string` | `"transcribe"` | Task type: `"transcribe"` or `"translate"` |
| `target_language` | `string` | — | Target language code (only for `"translate"` task) |
| `diarization_enabled` | `bool` | `false` | Enable speaker diarization |
| `diarization_max_speakers` | `int` | `4` | Maximum number of speakers |
| `profanity_filter` | `string` | — | Profanity filter mode: `"None"`, `"Masked"`, `"Removed"`, `"Tags"` |

#### `whisper`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `prompt` | `string` | — | Vocabulary hints for the model (guide style/spelling) |
| `temperature` | `float` | — | Sampling temperature (0.0–1.0). Lower = more deterministic |

#### `aoai_transcribe`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `prompt` | `string` | — | Vocabulary hints for the model |
| `temperature` | `float` | — | Sampling temperature (0.0–1.0) |

#### `voxtral`

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `system_prompt` | `string` | *(built-in)* | Replace the default system prompt entirely |
| `temperature` | `float` | — | Sampling temperature for generation |
| `max_tokens` | `int` | — | Maximum tokens in the response |

---

## CORS

The backend must allow CORS from `http://localhost:*` for local PoC development. FastAPI `CORSMiddleware` configured with:
- `allow_origins=["*"]`
- `allow_methods=["*"]`
- `allow_headers=["*"]`

## Polling Strategy

Frontend should poll `GET /api/transcribe/{job_id}` every **3 seconds** while `status` is `"processing"`. Stop polling when status is `"completed"` or `"failed"`, then fetch results.
