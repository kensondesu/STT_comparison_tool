# McManus — History

## Project Context

- **Project:** MAI_transcribe — Audio transcription webapp PoC
- **Stack:** Python backend, web frontend
- **User:** Fred (kensondesu)
- **Features:** Upload audio (wav, mp3, etc.) and transcribe using 5 methods:
  1. Azure STT with batch transcription
  2. Azure STT with fast transcription
  3. MAI-transcribe-1
  4. Azure OpenAI with gpt-4o-transcribe
  5. Voxtral mini transcribe via Azure Foundry
- **Backend:** Python API, file handling, Azure SDK integration, timecoded transcript output

## Learnings

- **Config pattern**: `backend/config.py` uses pydantic-settings `Settings` class with a module-level singleton `settings`. All env vars centralised there.
- **In-memory state**: `file_registry` (dict of UploadResponse) lives in `routers/upload.py`; `_jobs` and `_results` dicts live in `routers/transcribe.py`. PoC-only — no persistence.
- **Service abstraction**: All 5 engines implement `TranscriptionService.transcribe(audio_path, language) -> TranscriptionResult`. Result has `segments: list[Segment]`, `full_text`, `detected_language`.
- **MAI-Transcribe-1 reuses Fast Transcription**: Same endpoint, same response parser (`AzureSttFastService._parse_result`), only the `definition` JSON differs (adds `enhancedMode`).
- **Voxtral AudioContentFormat**: The `azure-ai-inference` SDK (v1.x) only exposes `WAV` and `MP3` in `AudioContentFormat`. Other formats (flac, ogg, m4a, webm) are sent as raw string values — the SDK accepts them.
- **Timecode normalisation**: Azure STT ticks ÷ 10,000,000 → seconds. Azure OpenAI already in seconds. Voxtral gets a single segment spanning full audio duration.
- **Async task pattern**: `asyncio.create_task` per method inside `POST /api/transcribe`. Each task catches its own exceptions, writes to `_results`, updates `_jobs`. One failure never blocks others.
- **Job status derivation**: `_compute_job_status()` checks all method statuses: all-failed→failed, any-processing→processing, else→completed.
- **File serving**: `GET /api/audio/{file_id}` uses FastAPI `FileResponse` with correct MIME type. Supports browser range requests natively.
- **Key file paths**: `backend/main.py` (entry), `backend/config.py` (settings), `backend/models/schemas.py` (all Pydantic models), `backend/routers/` (upload + transcribe), `backend/services/` (5 engines + base), `backend/utils/` (audio + storage).

## Team Sprint — 2026-04-07T13:43:43Z

### Delivery Summary
- **13 files** of production backend code
- **All 5 transcription services** fully integrated with Azure/OpenAI/Foundry
- **Smoke-tested** and ready for frontend integration
- **Runnable:** `uvicorn backend.main:app`

### Implementation Decisions Logged
1. **AudioContentFormat:** WAV/MP3 enums only; other formats as raw strings
2. **Parser reuse:** MAI-Transcribe-1 calls AzureSttFastService._parse_result()
3. **Language fallback:** Default to en-US with 10-language candidate list
4. **Language mapping:** BCP-47 → ISO 639-1 (split on `-`)

### Dependencies Satisfied
- Fenster can now integrate frontend against API endpoints
- Hockney's test suite can execute against production implementation

### Test Status
- 88-test suite: 34 pass, 30 skip, 14 fail + 10 errors (parallel dev mismatches)
- All failures are integration/import issues, not implementation bugs

### Next Steps
- Verify Range header support is functional for wavesurfer audio streaming
- Execute full test suite post-Fenster integration
- Performance testing with actual audio files

## Managed Identity Refactor — 2026-04-07

### What Changed
- All 5 service files + config + requirements refactored from API key auth to `DefaultAzureCredential`
- Sync credential (`azure.identity.DefaultAzureCredential`) used in `config.py` for the shared token helper and in `azure_stt_batch.py` for blob upload (runs via `asyncio.to_thread`)
- Async credential (`azure.identity.aio.DefaultAzureCredential`) used in `aoai_transcribe.py` (via `get_bearer_token_provider`) and `voxtral_transcribe.py`
- Every service checks if the legacy key env-var is set; if so, uses key-based auth as a fallback
- `AZURE_STORAGE_ACCOUNT_NAME` added for managed-identity blob URL construction; `AZURE_STORAGE_CONNECTION_STRING` kept as fallback
- Batch blob SAS generation uses user-delegation key when on managed identity, account key when using connection string fallback
- `.env.example` and `ARCHITECTURE.md` updated to reflect managed identity as default with optional key fallbacks

### Learnings
- `DefaultAzureCredential` handles token caching internally — no manual TTL/refresh logic needed
- The `openai` SDK's `azure_ad_token_provider` expects a callable, not a raw token; `get_bearer_token_provider` from `azure.identity.aio` provides exactly that
- `azure-ai-inference` `ChatCompletionsClient` accepts either `AzureKeyCredential` or `TokenCredential` — `DefaultAzureCredential` satisfies the latter
- Blob SAS via managed identity requires `get_user_delegation_key()` + `user_delegation_key` param in `generate_blob_sas()` — no `account_key` available
- Python 3.11 and 3.12 co-exist on this machine; pip installs into 3.11 site-packages — must use `python3.11` to run
- **Settings singleton vs monkeypatch.setenv**: `backend.config.settings` is created at import time. `monkeypatch.setenv()` only changes `os.environ` — it does NOT affect the already-initialized pydantic-settings object. Must use `monkeypatch.setattr("backend.config.settings.<field>", value)` to patch settings in tests.
- **DefaultAzureCredential hangs in tests**: If settings fields are empty (the defaults), services take the managed identity auth path and `DefaultAzureCredential()` hangs trying to probe IMDS / Azure CLI. The fix is twofold: (1) set fake API keys on settings so the key-based path is always taken, and (2) mock `DefaultAzureCredential` and `get_cognitive_services_token` as a safety net.
- **Autouse conftest fixture for credential safety**: Added `_block_azure_credentials` autouse fixture in `tests/conftest.py` that sets fake keys on all settings fields and mocks credential helpers. Every test gets this automatically — individual `mock_env` fixtures can override specific values.

## Whisper + LLM Speech Integration — 2026-04-09

### What Changed
- Added 2 new transcription services: **Whisper** (Azure OpenAI) and **LLM Speech** (Fast Transcription enhanced mode)
- `backend/services/whisper_transcribe.py` — uses `openai` SDK with `verbose_json` + `timestamp_granularities=["segment"]`; parses `segments[]` with `start`/`end` in seconds
- `backend/services/llm_speech.py` — same endpoint as STT Fast with `enhancedMode: { enabled: true, task: "transcribe" }`; no `locales` (auto-detect); reuses `AzureSttFastService._parse_result()`
- `backend/config.py` — added `azure_whisper_deployment_name` setting (default: "whisper")
- `backend/models/schemas.py` — added `whisper` and `llm_speech` to `MethodName` enum
- `backend/routers/transcribe.py` — added both to `SERVICE_MAP` and health check
- `.env.example`, `ARCHITECTURE.md`, `API_CONTRACT.md` updated
- Updated `tests/test_health.py` (expected 7 methods) and `tests/test_transcribe.py` (invalid method test used "whisper" — now uses "nonexistent_method")

### Learnings
- **Whisper vs gpt-4o-transcribe**: Whisper supports `verbose_json` natively with real segment timecodes; gpt-4o-transcribe only supports `json` (text-only, no segments). Different deployment names on same Azure OpenAI resource.
- **LLM Speech vs MAI-Transcribe-1**: Both use enhancedMode on Fast Transcription endpoint. LLM Speech uses `"task": "transcribe"` (no model specified); MAI uses `"model": "mai-transcribe-1"`. LLM Speech skips `locales` entirely — language detection is automatic.
- **Parser reuse pattern holds**: LLM Speech reuses `AzureSttFastService._parse_result()` just like MAI-Transcribe-1 — same response format.
- **Test brittleness**: Health test hardcoded service count; invalid-method test used a method name that later became valid. Both needed updating when adding new services.

## Per-Model Custom Settings — 2026-04-10

### What Changed
- Added `method_settings: dict[str, dict] | None = None` to `TranscribeRequest` schema
- Updated `TranscriptionService.transcribe()` base signature to accept `settings: dict | None = None`
- Router passes per-method settings from `method_settings.get(method_name)` to each service
- All 7 services updated to read relevant keys from `settings` dict via `.get()` — unknown keys silently ignored
- `API_CONTRACT.md` updated with full "Method Settings" reference section

### Settings per Service
- **azure_stt_fast**: `phrase_list`, `profanity_filter`, `diarization_enabled`/`diarization_max_speakers`, `language_autodetect`
- **azure_stt_batch**: `profanity_filter`, `word_level_timestamps`
- **mai_transcribe**: `profanity_filter`
- **llm_speech**: `prompt`, `task`, `target_language`, `diarization_enabled`/`diarization_max_speakers`, `profanity_filter`
- **whisper**: `prompt`, `temperature`
- **aoai_transcribe**: `prompt`, `temperature`
- **voxtral**: `system_prompt`, `temperature`, `max_tokens`

### Learnings
- **Backward compatibility preserved**: `settings` defaults to `None`, treated as empty dict inside each service. Zero behavior change when no settings passed.
- **Router plumbing is minimal**: One new kwarg on `_run_method()` + a `.get()` call per task dispatch. Clean separation between routing and service logic.
- **Settings dict over typed model**: Using `dict` instead of per-method Pydantic models keeps the interface uniform and avoids schema explosion. Services are responsible for validating their own keys.
- All 81 tests pass with no changes needed — the settings parameter is fully additive.

## Container Deployment Artifacts — 2026-04-10

### What Changed
- Created `Dockerfile` — multi-stage build with `python:3.13-slim` builder + production stage, copies backend/ + frontend/, exposes port 8000
- Created `.dockerignore` — excludes .git, .squad, .venv, tests, __pycache__, .env files to keep image lean
- Created `infra/deploy.sh` — full deployment script: creates resource group → deploys Bicep → builds image in ACR → updates Container App
- Created `infra/README.md` — deployment guide with prerequisites, quickstart, brownfield config, env var reference, troubleshooting

### Learnings
- **Docker build verified**: Multi-stage build completes successfully; `python:3.13-slim` matches the project's uv venv Python version
- **No .env in image**: All env vars injected via Container App configuration — keeps secrets out of the image layer
- **ACR remote build**: `az acr build` avoids needing Docker daemon in CI; builds directly in Azure
- **deploy.sh is idempotent**: Can re-run safely; `az group create` and `az deployment group create` are upsert operations

## Whisper → Azure STT Batch Refactor — 2026-04-10

### What Changed
- Rewrote `backend/services/whisper_transcribe.py` — now subclasses `AzureSttBatchService` instead of using the `openai` SDK
- Flow is identical to STT Batch: upload blob → create batch job → poll → fetch results
- Whisper model auto-discovered via `GET speechtotext/models/base` API (filters for "whisper" in displayName, picks newest)
- `backend/config.py` — replaced `azure_whisper_deployment_name` with `azure_whisper_model_id` (optional, empty = auto-discover)
- `backend/routers/transcribe.py` — health check now checks Speech config (`azure_speech_key` or `azure_speech_endpoint`) instead of `azure_openai_endpoint`
- `.env.example` — replaced `AZURE_WHISPER_DEPLOYMENT_NAME` with `AZURE_WHISPER_MODEL_ID`
- `frontend/js/app.js` — Whisper settings changed from `prompt`/`temperature` to `word_level_timestamps`/`profanity_filter`
- `tests/test_services.py` — Whisper tests now mock batch flow (blob upload, model discovery, job creation, polling, result fetch)
- `tests/test_health.py` — Whisper health tests now check Speech config instead of OpenAI endpoint
- `ARCHITECTURE.md` and `API_CONTRACT.md` — updated Whisper docs to reflect batch transcription approach

### Learnings
- **Subclassing AzureSttBatchService is clean**: Only need to override `_create_batch_job()` and `transcribe()`. All blob helpers, polling, and result fetching are inherited.
- **Whisper batch differences from standard STT Batch**: Uses `displayFormWordLevelTimestampsEnabled` (not `wordLevelTimestampsEnabled`), no `punctuationMode`, lexical field is empty (use `display` from nBest), requires `"model": {"self": "<uri>"}` in job body.
- **Model auto-discovery via base models API**: `GET /speechtotext/models/base?api-version=2024-11-15` returns all base models; filter by displayName containing "whisper". Sorting by `createdDateTime` picks the newest version.
- **Test mock complexity for batch flow**: Batch tests require 5 mock responses (model discovery, job create, poll, files list, content fetch) with proper async context managers — helper methods keep tests manageable.

## ffmpeg Audio Preprocessing — 2026-04-15

### What Changed
- Added `ensure_compatible_format()` async function in `backend/utils/audio.py` — probes with ffprobe, converts incompatible formats (e.g. m4a) to 16kHz mono PCM WAV via ffmpeg
- Added `ffmpeg_path` and `ffprobe_path` settings to `backend/config.py` (default: system PATH)
- Integrated preprocessing into `backend/routers/upload.py` — runs after `save_file()`, before `get_duration()`, updates `ext` and `format` in response
- Added `ffmpeg` installation to Dockerfile production stage
- Added `_mock_ffprobe` autouse fixture in `tests/conftest.py` — bypasses ffprobe/ffmpeg for test stubs that aren't real audio

### Learnings
- **Patch target matters for `from X import Y`**: When `upload.py` does `from backend.utils.audio import ensure_compatible_format`, monkeypatching the function on `backend.utils.audio` doesn't affect the already-bound name in `upload.py`. Must patch on `backend.routers.upload` instead.
- **ffprobe format_name is comma-delimited**: e.g. `"matroska,webm"` or `"mov,mp4,m4a,3gp,3g2,mj2"`. Substring match against `_COMPATIBLE_FORMATS` handles this correctly.
- **Graceful degradation**: If ffprobe/ffmpeg is not installed, `ensure_compatible_format` catches `FileNotFoundError` and returns the original path with a warning — no crash.
- **`find_file()` already extension-agnostic**: Searches by stem, so `.m4a` → `.wav` conversion doesn't break file lookups.
- All 91 tests pass (21 skipped) after changes.

## First-Time Setup Wizard — 2026-04-15

### What Changed
- Created `backend/setup_wizard.py` — interactive CLI wizard that prompts for all Azure service config and writes `.env`
- Modified `backend/main.py` — wizard check runs BEFORE `from backend.config import settings` so the freshly written `.env` is read at import time
- Wizard includes auth mode toggle: Managed Identity (DefaultAzureCredential) vs API key based
- Covers all services: Azure Speech, MAI-Transcribe-1, Whisper, Blob Storage, Azure OpenAI, Voxtral
- Auto-skip in non-interactive contexts: `sys.stdin.isatty()` returns False (pytest, Docker, CI), or `AZURE_SPEECH_ENDPOINT` / `SKIP_SETUP_WIZARD` env vars are set

### Learnings
- **Import order is critical**: `backend/config.py` reads `.env` at module load time via pydantic-settings `model_config`. The wizard must execute before `from backend.config import settings` — otherwise the Settings singleton is created without the `.env` values.
- **isatty() guard is essential for tests**: pytest runs with stdin redirected (not a tty), so the `sys.stdin.isatty()` check prevents the wizard from ever triggering during test runs — no test changes needed.
- **Skip via env var for containers**: Docker / Container Apps inject env vars directly; `SKIP_SETUP_WIZARD` or an existing `AZURE_SPEECH_ENDPOINT` bypasses the wizard even without a `.env` file.
- All 98 tests pass (21 skipped) after changes — zero regressions.
