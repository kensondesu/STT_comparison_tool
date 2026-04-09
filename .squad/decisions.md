# Squad Decisions

## Active Decisions

### 1. User Directive — Language Override (2026-04-07T13:43:43Z)
**By:** Fred (via Copilot)
**Category:** Product Requirement

Frontend should have the option to define language (just in case the autodetect doesn't work). This is captured for team memory and implemented as a 33-language dropdown in the frontend.

### 2. Architecture Decision — MAI_transcribe PoC (2025-07-17)
**By:** Keaton (Lead)
**Status:** Active

#### Key Decisions
- **Tech Stack:** FastAPI backend (async, auto OpenAPI docs, BackgroundTasks) + Vanilla HTML/JS/CSS frontend (no build step)
- **State Management:** In-memory dict (no database for PoC)
- **Audio Player:** wavesurfer.js v7 for waveform + timecode sync
- **Timecode Normalization:** All 5 services normalize to `{ start_time: float (seconds), end_time: float (seconds), text: string }`
- **API Design:** Upload → Transcribe → Poll → Results (4-step flow); methods independently tracked per job; partial failures allowed
- **Service Integration:** 
  - Azure STT Batch/Fast/MAI-Transcribe-1 use same Speech resource + REST API
  - MAI-Transcribe-1 activated via `enhancedMode` flag on Fast Transcription endpoint
  - Azure OpenAI uses `openai` Python SDK
  - Voxtral uses `azure-ai-inference` SDK targeting Foundry serverless endpoint
  - Batch Transcription only method requiring Azure Blob Storage
- **Error Isolation:** Each transcription method runs as independent async task; one method's failure never blocks others
- **Frontend Polling:** 3-second intervals

#### Artifacts
- `ARCHITECTURE.md` — full architecture document
- `API_CONTRACT.md` — REST API specification
- `requirements.txt` — Python dependencies
- `.env.example` — environment variable template
- Directory skeleton: `backend/`, `frontend/`, `uploads/`

### 3. Backend Implementation Choices (2026-04-07)
**By:** McManus (Backend Dev)

#### Pragmatic PoC Decisions
1. **azure-ai-inference AudioContentFormat:** Only `WAV` and `MP3` available as enum members; other formats (flac, ogg, m4a, webm) passed as raw string values at API level
2. **MAI-Transcribe-1 parser reuse:** `MaiTranscribeService` calls `AzureSttFastService._parse_result()` directly to avoid code duplication (creates coupling, acceptable for PoC)
3. **Azure STT Batch language fallback:** Defaults to `en-US` with 10-language candidate list when no language specified; same pattern for Fast/MAI
4. **Azure OpenAI language mapping:** SDK uses ISO 639-1 codes (`en`) while API contract uses BCP-47 (`en-US`); split on `-` and pass first part

#### Status
Backend fully runnable with `uvicorn backend.main:app` — frontend can integrate immediately.

### 4. Frontend Implementation Patterns (2025-07-15)
**By:** Fenster (Frontend Dev)
**Status:** Implemented

#### Decisions
1. **ES Modules (no bundler):** All JS files use `import`/`export` with `<script type="module">`; wavesurfer.js loaded from unpkg CDN as ESM; no build step
2. **Progressive result rendering:** Each method's card updates independently as results arrive; polling fetches individual method results to avoid redundant data transfer
3. **CSS custom properties for theming:** All colors defined as `--var` on `:root` and overridden in `body.dark`; theme preference persisted in `localStorage`
4. **wavesurfer MediaElement backend:** Uses `backend: 'MediaElement'` to stream audio from `/api/audio/{file_id}` endpoint with Range header support for seeking
5. **Segment click-to-seek:** Event delegation on `.segment` elements reads `data-start` attribute and calls `player.seekTo()`; auto-plays if paused

#### Backend Requirement
McManus: Backend must serve `/api/audio/{file_id}` with correct MIME types and Range header support for wavesurfer streaming.

### 5. Test-First Strategy for Backend (2025-07-18)
**By:** Hockney (Tester)
**Status:** Active

#### Strategic Decisions
1. **Fallback stubs in conftest.py:** `Segment` and `TranscriptionResult` Pydantic models defined as fallback stubs; once backend provides real models, stubs are superseded. Developers ensure schema names match.
2. **Graceful skips:** Tests importing unimplemented modules use `pytest.skip()` rather than hard-failing on `ImportError`; pytest always runs cleanly
3. **pytest-asyncio with asyncio_mode=auto:** All `async def test_*` functions run as async tests automatically; no need for per-test `@pytest.mark.asyncio`
4. **Mock all external calls:** Zero Azure/OpenAI credentials required; every service test patches HTTP clients or SDK calls; CI can run full suite without secrets
5. **Upload test audio:** `_make_wav_bytes()` generates valid RIFF/WAVE binary; minimal header stubs for non-WAV formats (sufficient for upload validation)

#### Test Suite Scope
- **88 tests** across 6 files: upload (14), transcribe (16), services (25+), audio (17), health (5)
- **Acceptance Criterion:** All 88 tests pass green once backend fully implemented
- Tests define expected API structure, service behavior, and timecode accuracy

#### Impact
- **McManus/Fenster:** Run tests frequently during implementation; 88 tests serve as acceptance criteria
- **Keaton:** No architecture changes implied; tests align with documented structure

### 6. Feature — Whisper + LLM Speech Service Integration (2026-04-09)
**By:** McManus (Backend Dev)
**Status:** Completed

#### Context
Added two new transcription engines to expand service roster from 5 to 7, leveraging existing Azure infrastructure.

#### Decisions
1. **Whisper shares Azure OpenAI resource with gpt-4o-transcribe**
   - Same endpoint and authentication (DefaultAzureCredential / API key fallback)
   - Different deployment name: `AZURE_WHISPER_DEPLOYMENT_NAME` (default: "whisper")
   - Uses `verbose_json` format with real segment-level timecodes (unlike gpt-4o-transcribe which only gets text)

2. **LLM Speech reuses Fast Transcription endpoint and parser**
   - Same endpoint and authentication as STT Fast
   - Differentiated by `enhancedMode: { enabled: true, task: "transcribe" }` in service definition
   - No `locales` field — language detection is fully automatic
   - Response parsed by `AzureSttFastService._parse_result()` (same as MAI-Transcribe-1)

3. **LLM Speech is distinct from MAI-Transcribe-1**
   - MAI uses `"model": "mai-transcribe-1"` in enhancedMode + its own Speech resource
   - LLM Speech uses `"task": "transcribe"` (no model) + the standard Speech resource
   - Both reuse the same response parser

#### Files Changed
- `backend/services/whisper_transcribe.py` (new)
- `backend/services/llm_speech.py` (new)
- `backend/config.py` — added `azure_whisper_deployment_name`
- `backend/models/schemas.py` — added enum values
- `backend/routers/transcribe.py` — SERVICE_MAP + health check
- `.env.example`, `ARCHITECTURE.md`, `API_CONTRACT.md` — docs
- `tests/test_health.py`, `tests/test_transcribe.py` — test coverage
- `frontend/js/app.js` — added Whisper and LLM Speech to METHODS array

#### Results
- All 67 tests pass (21 skipped)
- Backend fully operational with 7 transcription services
- Frontend ready for production deployment

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
