# Keaton — History

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
- **Frontend:** File upload, transcript visualization, audio player with timecoded transcript mapping

## Learnings

### Architecture Decisions (2025-07-17)
- **Backend**: FastAPI — async-native, file upload support, auto OpenAPI docs
- **Frontend**: Vanilla HTML/JS/CSS with wavesurfer.js for audio player — no build step, PoC-appropriate
- **Job state**: In-memory dict — no database for PoC
- **Concurrency**: `asyncio.create_task` to run transcription methods in parallel per job
- **Timecodes**: Normalized to `{start_time: float, end_time: float, text: string}` segments (seconds)
  - Azure STT ticks: divide by 10,000,000
  - Azure OpenAI: already in seconds
  - Voxtral: may need single-segment fallback
- **MAI-Transcribe-1**: Uses same Fast Transcription REST endpoint with `enhancedMode` flag — shares SDK/auth with Azure STT
- **Voxtral via Foundry**: Chat-completion model with audio input, not a dedicated STT API — timecodes may be limited
- **Azure STT Batch**: Only method requiring Blob Storage (SAS URL for audio input) — adds Azure Storage dependency
- **Error isolation**: Each method runs independently; one failure never blocks others
- **Polling**: Frontend polls every 3s; job-level status derived from method statuses

### Key File Paths
- `ARCHITECTURE.md` — full architecture doc
- `API_CONTRACT.md` — REST API specification with JSON schemas
- `requirements.txt` — Python backend dependencies
- `.env.example` — environment variable template
- `backend/` — Python backend (FastAPI)
- `frontend/` — Vanilla HTML/JS/CSS frontend
- `uploads/` — temp audio storage (gitignored)

## Team Sprint — 2026-04-07T13:43:43Z

### Sprint Summary
Orchestrated complete PoC delivery: architecture, 13-file backend, 5-file frontend, 88-test suite.

### Team Coordination
- **McManus (Backend):** Delivered all 5 transcription services, ready for integration
- **Fenster (Frontend):** Delivered complete SPA with 33-language support and wavesurfer.js
- **Hockney (Tester):** Delivered TDD test suite with 88 tests defining acceptance criteria

### Key Milestones
- Architecture + API contract finalized and approved
- Backend fully implemented and smoke-tested
- Frontend complete with drag-and-drop and audio player
- Test suite ready to validate integration

### Blockers Resolved
- None — parallel development proceeding smoothly

### Next Phase
- Execute test suite post-integration
- Verify timecode accuracy and audio streaming
- Performance optimization if needed

## Infrastructure Sprint — 2026-04-10

### Sprint Summary
Created complete Bicep IaC for Azure Container Apps deployment with managed identity auth.

### Deliverables
- **10 Bicep files** in `infra/` directory (main + 8 modules + params)
- **Greenfield/brownfield dual mode** — deploy fresh or wire into existing resources
- **Managed identity only** — zero secrets/keys in container env vars
- **6 RBAC role assignments** — Cognitive Services User, OpenAI User, Storage Blob Data Contributor, Storage Blob Delegator, AcrPull
- **Validated** — `az bicep build` succeeds (BCP318 warnings are safe false positives from conditional module outputs)

### Key Design Decisions
- System-assigned managed identity on Container App for all Azure service auth
- ACR pull via managed identity (no admin credentials)
- PoC-appropriate sizing: Basic ACR, 1 CPU/2Gi, Standard_LRS storage
- Deterministic role assignment names via `guid()` for idempotency
- Conditional resource creation with ternary output resolution for brownfield mode

### Learnings
- BCP318 warnings on conditional module outputs are false positives when the ternary condition mirrors the deployment condition
- Bicep infers dependsOn from output references — explicit dependsOn is only needed for side-effect dependencies
- OpenAI model deployments must be sequential (dependsOn between them) to avoid ARM conflicts on the parent resource
