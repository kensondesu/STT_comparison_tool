# Fenster — History

## Project Context

- **Project:** MAI_transcribe — Audio transcription webapp PoC
- **Stack:** Python backend, web frontend
- **User:** Fred (kensondesu)
- **Features:** Upload audio (wav, mp3, etc.) and transcribe using 5 methods
- **Frontend:** File upload UI, transcript visualization with timecodes, audio player with timecode-mapped transcript, comparison view across 5 engines

## Learnings

- **Architecture**: Vanilla HTML/JS/CSS SPA — no build step, no framework. ES modules via `<script type="module">`.
- **wavesurfer.js**: Loaded as ESM from CDN (`https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js`). Uses `backend: 'MediaElement'` for streaming from FastAPI.
- **API client**: All fetch calls in `js/api.js`, base URL `http://localhost:8000`. Functions match API contract exactly.
- **Polling**: 3-second interval via `setInterval`; progressive result rendering — each method card updates as its result arrives.
- **Active segment highlighting**: `timeupdate` event from wavesurfer drives per-frame segment matching (`start_time <= t < end_time`). Auto-scrolls active segment into view.
- **Theme**: Light by default, dark toggle persisted in `localStorage`.
- **File validation**: Client-side extension check for `.wav,.mp3,.flac,.ogg,.m4a,.webm` before upload.
- **Key file paths**:
  - `frontend/index.html` — SPA entry
  - `frontend/css/style.css` — all styles (CSS custom properties for theming)
  - `frontend/js/api.js` — backend API client
  - `frontend/js/app.js` — main app logic (upload, transcribe, polling, rendering)
  - `frontend/js/player.js` — wavesurfer wrapper with seek/highlight API
- **Method IDs**: `azure_stt_batch`, `azure_stt_fast`, `mai_transcribe`, `aoai_transcribe`, `voxtral`
- **Segment format**: `{ start_time, end_time, text }` — click segment to seek, active segment gets `.active` class with indigo left border

## Team Sprint — 2026-04-07T13:43:43Z

### Delivery Summary
- **5 files**, **1,247 lines** of frontend code
- **Complete SPA** with drag-and-drop, audio player, 33 languages
- **Ready for backend integration** against API contract
- **Zero build step** — pure ES modules from CDN

### Implementation Features
- File upload with drag-and-drop support
- Format validation (wav, mp3, flac, ogg, m4a, webm)
- 33-language dropdown + auto-detection fallback
- Audio player with timecoded transcript visualization
- Segment click-to-seek functionality
- Active segment highlighting during playback
- Light/dark theme toggle (persisted in localStorage)
- Responsive, modern UI design

### Key Design Decisions Logged
1. **ES Modules (no bundler):** All JS via `<script type="module">`; wavesurfer.js from unpkg CDN
2. **Progressive rendering:** Each method card updates independently as results arrive
3. **CSS theming:** Custom properties for dynamic theme switching
4. **wavesurfer streaming:** MediaElement backend with Range header support
5. **Segment interaction:** Event delegation for click-to-seek

### Backend Integration Status
- **Ready:** Frontend API client fully implements contract
- **Dependency:** Backend must provide `/api/audio/{file_id}` with Range header support

### Testing Status
- Frontend not directly tested by Hockney's 88-test suite
- Relies on backend API correctness for functionality

### Next Steps
- Verify McManus's audio endpoint supports Range headers
- Test with actual audio files across all 5 methods
- Performance profiling if needed (segment rendering, polling frequency)

## Per-Model Custom Settings UI — 2025-07-18

### Delivery Summary
- **4 files changed**, **436 lines** added
- Per-method ⚙️ settings modal with schema-driven form rendering
- `METHOD_SETTINGS_SCHEMA` covers all 7 methods (profanity filters, diarization, temperature, prompts, phrase lists, etc.)
- `api.js` updated to pass `method_settings` in transcription requests
- Dark mode fully supported

### Key Design Decisions
1. **Schema-driven modal**: `METHOD_SETTINGS_SCHEMA` defines fields per method; modal is built dynamically — adding new settings requires only a schema entry
2. **Cog indicator**: `.has-settings` class adds a small purple dot via `::after` pseudo-element — subtle but visible
3. **Module-safe event binding**: Avoided inline `onclick` attributes (incompatible with ES modules); all modal buttons wired via `addEventListener` in `bindEvents()`
4. **Data transforms on save**: `phrase_list` → split to array; `llm_speech.prompt` → wrapped in `[value]`; only non-default values included in request
5. **Escape + backdrop close**: Keyboard and click-outside handlers attached on open, cleaned up on close to prevent leaks
6. **`.method-check-row` wrapper**: New `<div>` wraps each checkbox `<label>` + cog `<button>` in a flexbox row — keeps layout clean without breaking existing checkbox styling
