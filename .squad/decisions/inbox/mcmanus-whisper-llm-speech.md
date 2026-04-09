# Decision: Whisper + LLM Speech Service Integration

**Date:** 2026-04-09
**By:** McManus (Backend Dev)
**Category:** Implementation

## Context

Added two new transcription engines to bring total services from 5 to 7.

## Decisions

### 1. Whisper shares Azure OpenAI resource with gpt-4o-transcribe
- Same endpoint, same auth (DefaultAzureCredential / API key fallback)
- Different deployment name: `AZURE_WHISPER_DEPLOYMENT_NAME` (default: "whisper")
- Uses `verbose_json` format with real segment-level timecodes (unlike gpt-4o-transcribe which only gets text)

### 2. LLM Speech reuses Fast Transcription endpoint and parser
- Same endpoint + auth as STT Fast
- Differentiated by `enhancedMode: { enabled: true, task: "transcribe" }` in definition
- No `locales` field — language detection is fully automatic
- Response parsed by `AzureSttFastService._parse_result()` (same as MAI-Transcribe-1)

### 3. LLM Speech is distinct from MAI-Transcribe-1
- MAI uses `"model": "mai-transcribe-1"` in enhancedMode + its own Speech resource
- LLM Speech uses `"task": "transcribe"` (no model) + the standard Speech resource
- Both reuse the same response parser

## Files Changed
- `backend/services/whisper_transcribe.py` (new)
- `backend/services/llm_speech.py` (new)
- `backend/config.py` — added `azure_whisper_deployment_name`
- `backend/models/schemas.py` — added enum values
- `backend/routers/transcribe.py` — SERVICE_MAP + health check
- `.env.example`, `ARCHITECTURE.md`, `API_CONTRACT.md` — docs
- `tests/test_health.py`, `tests/test_transcribe.py` — test fixes

## Status
All 67 tests pass (21 skipped). Ready for frontend integration.
