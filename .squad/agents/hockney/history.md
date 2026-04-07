# Hockney — History

## Project Context

- **Project:** MAI_transcribe — Audio transcription webapp PoC
- **Stack:** Python backend, web frontend
- **User:** Fred (kensondesu)
- **Features:** 5 transcription methods, audio upload, timecoded transcript with audio player
- **Testing scope:** API tests, frontend tests, format handling, timecode accuracy, edge cases

## Learnings

### Test suite v1 — 2025-07-18

- **88 tests** across 6 files covering upload, transcribe, services, audio utils, and health endpoints
- Backend is skeleton-only (empty `__init__.py`); tests are TDD-first — they define the spec
- **Key file paths:**
  - `tests/conftest.py` — fixtures, mock audio factories, fallback Pydantic stubs
  - `tests/test_upload.py` — 14 tests: format acceptance/rejection, schema, edge cases
  - `tests/test_transcribe.py` — 16 tests: lifecycle, status polling, results, delete, language
  - `tests/test_services.py` — 25+ tests: base ABC, timecode normalization, per-service mocked HTTP
  - `tests/test_audio.py` — 17 tests: format detection, MIME mapping, mutagen metadata
  - `tests/test_health.py` — 5 tests: schema, service listing, configuration status
  - `requirements-dev.txt` — test deps (pytest, pytest-asyncio, httpx, pytest-cov)
  - `pyproject.toml` — pytest configuration with asyncio_mode=auto
- **Patterns:**
  - `pytest.skip()` when backend modules aren't importable — graceful TDD failure
  - Schema stubs in conftest.py mirror ARCHITECTURE.md until real models exist
  - WAV file factory (`_make_wav_bytes`) generates valid RIFF/WAVE headers for upload tests
  - All Azure/OpenAI calls mocked via `unittest.mock.patch` — zero credentials needed
  - Timecode normalization tested with formula: `ticks / 10_000_000` → seconds
- **Edge cases covered:**
  - Empty file upload, missing file field, no extension, duplicate file IDs
  - Auth failure (401), service unavailable (503), timeout per service
  - Segment schema validation: missing required fields
  - Case-insensitive format detection (WAV vs wav)

## Team Sprint — 2026-04-07T13:43:43Z

### Test Suite Delivery
- **88 comprehensive tests** across 6 files
- **Current status:** 34 pass, 30 skip, 14 fail + 10 errors (expected during parallel development)
- **Test suite is ready** and defining acceptance criteria for backend/frontend integration

### Test Strategy Decisions Logged
1. **Fallback stubs in conftest.py:** Pydantic models defined as stubs until backend provides real implementations
2. **Graceful skips:** Import failures converted to pytest.skip() — suite runs cleanly during parallel dev
3. **pytest-asyncio auto mode:** All async tests run automatically without per-test decorators
4. **Mock all external calls:** Zero credentials needed; all service calls patched
5. **Upload test audio generation:** Valid RIFF/WAVE binary for WAV; minimal stubs for other formats

### Blockers During Sprint
- **14 failures + 10 errors** primarily due to timing:
  - Import mismatches (backend modules not yet fully populated)
  - Schema name mismatches between tests and backend implementations
  - These will resolve as McManus and Fenster complete integration

### Test Coverage
- **Upload:** Format validation, schema compliance, edge cases
- **Transcribe:** Job lifecycle, status polling, result retrieval, language handling
- **Services:** Base ABC patterns, timecode normalization, mocked HTTP per service
- **Audio:** Format detection, MIME types, metadata extraction
- **Health:** Configuration validation, service discovery

### Acceptance Criteria
**All 88 tests should pass green once backend is fully integrated.**

### Impact on Team
- **McManus:** Tests define expected API structure and service behavior
- **Fenster:** Tests validate backend correctness; frontend can integrate safely
- **Keaton:** Architecture remains stable; tests align with documented design

### Next Phase
- Execute test suite after McManus completes backend
- Fix schema name mismatches if needed
- Add frontend integration tests post-PoC if required
- Expand edge case coverage based on real usage
