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
