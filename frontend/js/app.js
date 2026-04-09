// Main application logic for MAI_transcribe

import * as api from './api.js';
import * as player from './player.js';

// ── Constants ──────────────────────────────────────────────

const METHODS = [
    { id: 'azure_stt_batch', label: 'Azure STT — Batch' },
    { id: 'azure_stt_fast', label: 'Azure STT — Fast' },
    { id: 'mai_transcribe', label: 'MAI-Transcribe-1' },
    { id: 'aoai_transcribe', label: 'Azure GPT-4o-transcribe' },
    { id: 'voxtral', label: 'Voxtral Mini' },
    { id: 'whisper', label: 'Azure Whisper' },
    { id: 'llm_speech', label: 'LLM Speech' },
];

const LANGUAGES = [
    { code: '', label: 'Auto-detect' },
    { code: 'en-US', label: 'English (US)' },
    { code: 'en-GB', label: 'English (UK)' },
    { code: 'fr-FR', label: 'French' },
    { code: 'de-DE', label: 'German' },
    { code: 'es-ES', label: 'Spanish' },
    { code: 'ja-JP', label: 'Japanese' },
    { code: 'zh-CN', label: 'Chinese (Simplified)' },
    { code: 'zh-TW', label: 'Chinese (Traditional)' },
    { code: 'pt-BR', label: 'Portuguese (Brazil)' },
    { code: 'pt-PT', label: 'Portuguese (Portugal)' },
    { code: 'it-IT', label: 'Italian' },
    { code: 'nl-NL', label: 'Dutch' },
    { code: 'ko-KR', label: 'Korean' },
    { code: 'ar-SA', label: 'Arabic' },
    { code: 'hi-IN', label: 'Hindi' },
    { code: 'ru-RU', label: 'Russian' },
    { code: 'pl-PL', label: 'Polish' },
    { code: 'sv-SE', label: 'Swedish' },
    { code: 'da-DK', label: 'Danish' },
    { code: 'nb-NO', label: 'Norwegian' },
    { code: 'fi-FI', label: 'Finnish' },
    { code: 'tr-TR', label: 'Turkish' },
    { code: 'th-TH', label: 'Thai' },
    { code: 'vi-VN', label: 'Vietnamese' },
    { code: 'uk-UA', label: 'Ukrainian' },
    { code: 'cs-CZ', label: 'Czech' },
    { code: 'el-GR', label: 'Greek' },
    { code: 'he-IL', label: 'Hebrew' },
    { code: 'id-ID', label: 'Indonesian' },
    { code: 'ms-MY', label: 'Malay' },
    { code: 'ro-RO', label: 'Romanian' },
    { code: 'hu-HU', label: 'Hungarian' },
];

const POLL_INTERVAL_MS = 3000;
const ACCEPTED_FORMATS = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.webm'];

const METHOD_SETTINGS_SCHEMA = {
    azure_stt_batch: [
        { key: 'profanity_filter', label: 'Profanity Filter', type: 'select', options: ['None', 'Masked', 'Removed', 'Tags'], default: 'None' },
        { key: 'word_level_timestamps', label: 'Word-Level Timestamps', type: 'checkbox', default: false },
    ],
    azure_stt_fast: [
        { key: 'phrase_list', label: 'Phrase List (comma-separated)', type: 'text', default: '', placeholder: 'Contoso, Rehaan, Azure' },
        { key: 'profanity_filter', label: 'Profanity Filter', type: 'select', options: ['None', 'Masked', 'Removed', 'Tags'], default: 'None' },
        { key: 'diarization_enabled', label: 'Speaker Diarization', type: 'checkbox', default: false },
        { key: 'diarization_max_speakers', label: 'Max Speakers', type: 'number', default: 4, min: 1, max: 35 },
        { key: 'language_autodetect', label: 'Language Auto-detect', type: 'checkbox', default: true },
    ],
    mai_transcribe: [
        { key: 'profanity_filter', label: 'Profanity Filter', type: 'select', options: ['None', 'Masked', 'Removed', 'Tags'], default: 'None' },
    ],
    llm_speech: [
        { key: 'prompt', label: 'Custom Prompt', type: 'textarea', default: '', placeholder: 'Output must be in lexical format.' },
        { key: 'task', label: 'Task', type: 'select', options: ['transcribe', 'translate'], default: 'transcribe' },
        { key: 'target_language', label: 'Target Language (for translate)', type: 'text', default: '', placeholder: 'ko, fr, de...' },
        { key: 'profanity_filter', label: 'Profanity Filter', type: 'select', options: ['None', 'Masked', 'Removed', 'Tags'], default: 'None' },
        { key: 'diarization_enabled', label: 'Speaker Diarization', type: 'checkbox', default: false },
        { key: 'diarization_max_speakers', label: 'Max Speakers', type: 'number', default: 4, min: 1, max: 35 },
    ],
    whisper: [
        { key: 'prompt', label: 'Vocabulary Hints', type: 'text', default: '', placeholder: 'Technical terms, names...' },
        { key: 'temperature', label: 'Temperature', type: 'number', default: 0, min: 0, max: 1, step: 0.1 },
    ],
    aoai_transcribe: [
        { key: 'prompt', label: 'Vocabulary Hints', type: 'text', default: '', placeholder: 'Technical terms, names...' },
        { key: 'temperature', label: 'Temperature', type: 'number', default: 0, min: 0, max: 1, step: 0.1 },
    ],
    voxtral: [
        { key: 'system_prompt', label: 'System Prompt', type: 'textarea', default: '', placeholder: 'Custom transcription instructions...' },
        { key: 'temperature', label: 'Temperature', type: 'number', default: 0.7, min: 0, max: 2, step: 0.1 },
        { key: 'max_tokens', label: 'Max Tokens', type: 'number', default: 4096, min: 100, max: 16384 },
    ],
};

// ── State ──────────────────────────────────────────────────

let currentFileId = null;
let currentJobId = null;
let pollTimer = null;
let resultsData = {};
let methodSettings = {};

// ── DOM refs (set in init) ─────────────────────────────────

let $dropZone, $fileInput, $fileInfo, $languageSelect, $methodChecks,
    $transcribeBtn, $statusSection, $statusText, $progressBar,
    $playerSection, $waveform, $playBtn, $timeDisplay,
    $resultsSection, $resultsGrid, $themeToggle;

// ── Initialization ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);

function init() {
    cacheDOM();
    buildLanguageOptions();
    buildMethodCheckboxes();
    bindEvents();
    player.initPlayer($waveform);
    checkHealth();
}

function cacheDOM() {
    $dropZone = document.getElementById('drop-zone');
    $fileInput = document.getElementById('file-input');
    $fileInfo = document.getElementById('file-info');
    $languageSelect = document.getElementById('language-select');
    $methodChecks = document.getElementById('method-checks');
    $transcribeBtn = document.getElementById('transcribe-btn');
    $statusSection = document.getElementById('status-section');
    $statusText = document.getElementById('status-text');
    $progressBar = document.getElementById('progress-bar');
    $playerSection = document.getElementById('player-section');
    $waveform = document.getElementById('waveform');
    $playBtn = document.getElementById('play-btn');
    $timeDisplay = document.getElementById('time-display');
    $resultsSection = document.getElementById('results-section');
    $resultsGrid = document.getElementById('results-grid');
    $themeToggle = document.getElementById('theme-toggle');
}

// ── Language selector ──────────────────────────────────────

function buildLanguageOptions() {
    LANGUAGES.forEach(({ code, label }) => {
        const opt = document.createElement('option');
        opt.value = code;
        opt.textContent = label;
        $languageSelect.appendChild(opt);
    });
}

// ── Method checkboxes ──────────────────────────────────────

function buildMethodCheckboxes() {
    METHODS.forEach(({ id, label }) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'method-check-row';
        const lbl = document.createElement('label');
        lbl.className = 'method-check';
        lbl.innerHTML = `<input type="checkbox" name="method" value="${id}" checked> ${label}`;
        wrapper.appendChild(lbl);

        if (METHOD_SETTINGS_SCHEMA[id]) {
            const cog = document.createElement('button');
            cog.type = 'button';
            cog.className = 'settings-cog';
            cog.dataset.method = id;
            cog.title = `Settings for ${label}`;
            cog.textContent = '⚙️';
            cog.addEventListener('click', (e) => {
                e.stopPropagation();
                openSettingsModal(id);
            });
            wrapper.appendChild(cog);
        }
        $methodChecks.appendChild(wrapper);
    });
}

// ── Settings modal ─────────────────────────────────────────

function openSettingsModal(methodId) {
    const schema = METHOD_SETTINGS_SCHEMA[methodId];
    if (!schema) return;

    const info = METHODS.find((m) => m.id === methodId);
    const $modal = document.getElementById('settings-modal');
    const $title = document.getElementById('modal-title');
    const $body = document.getElementById('modal-body');
    const $saveBtn = document.getElementById('modal-save-btn');

    $title.textContent = `${info?.label ?? methodId} Settings`;

    const saved = methodSettings[methodId] || {};
    let fieldsHtml = '';
    for (const field of schema) {
        const val = saved[field.key] ?? field.default;
        fieldsHtml += `<div class="modal-field">`;
        fieldsHtml += `<label for="setting-${field.key}">${escapeHtml(field.label)}</label>`;

        if (field.type === 'select') {
            fieldsHtml += `<select id="setting-${field.key}" data-key="${field.key}">`;
            for (const opt of field.options) {
                const selected = val === opt ? ' selected' : '';
                fieldsHtml += `<option value="${opt}"${selected}>${escapeHtml(opt)}</option>`;
            }
            fieldsHtml += `</select>`;
        } else if (field.type === 'checkbox') {
            const checked = val ? ' checked' : '';
            fieldsHtml += `<label class="modal-checkbox"><input type="checkbox" id="setting-${field.key}" data-key="${field.key}"${checked}> Enabled</label>`;
        } else if (field.type === 'textarea') {
            const displayVal = Array.isArray(val) ? val.join('\n') : (val || '');
            fieldsHtml += `<textarea id="setting-${field.key}" data-key="${field.key}" rows="3"${field.placeholder ? ` placeholder="${escapeHtml(field.placeholder)}"` : ''}>${escapeHtml(displayVal)}</textarea>`;
        } else if (field.type === 'number') {
            let attrs = `type="number" id="setting-${field.key}" data-key="${field.key}" value="${val}"`;
            if (field.min != null) attrs += ` min="${field.min}"`;
            if (field.max != null) attrs += ` max="${field.max}"`;
            if (field.step != null) attrs += ` step="${field.step}"`;
            fieldsHtml += `<input ${attrs}>`;
        } else {
            // text
            const displayVal = Array.isArray(val) ? val.join(', ') : (val || '');
            fieldsHtml += `<input type="text" id="setting-${field.key}" data-key="${field.key}" value="${escapeHtml(displayVal)}"${field.placeholder ? ` placeholder="${escapeHtml(field.placeholder)}"` : ''}>`;
        }
        fieldsHtml += `</div>`;
    }
    $body.innerHTML = fieldsHtml;

    $saveBtn.onclick = () => saveMethodSettings(methodId);
    $modal.style.display = 'flex';
    $modal.dataset.method = methodId;

    // Close on backdrop click
    $modal._backdropHandler = (e) => {
        if (e.target === $modal) closeSettingsModal();
    };
    $modal.addEventListener('click', $modal._backdropHandler);

    // Close on Escape
    $modal._escHandler = (e) => {
        if (e.key === 'Escape') closeSettingsModal();
    };
    document.addEventListener('keydown', $modal._escHandler);
}

function closeSettingsModal() {
    const $modal = document.getElementById('settings-modal');
    $modal.style.display = 'none';
    if ($modal._backdropHandler) {
        $modal.removeEventListener('click', $modal._backdropHandler);
        $modal._backdropHandler = null;
    }
    if ($modal._escHandler) {
        document.removeEventListener('keydown', $modal._escHandler);
        $modal._escHandler = null;
    }
}

function saveMethodSettings(methodId) {
    const schema = METHOD_SETTINGS_SCHEMA[methodId];
    if (!schema) return;

    const settings = {};
    let hasNonDefault = false;

    for (const field of schema) {
        const el = document.getElementById(`setting-${field.key}`);
        if (!el) continue;

        let val;
        if (field.type === 'checkbox') {
            val = el.checked;
        } else if (field.type === 'number') {
            val = parseFloat(el.value);
        } else {
            val = el.value;
        }

        // Transform phrase_list: comma-separated string → array
        if (field.key === 'phrase_list' && typeof val === 'string') {
            val = val.split(',').map((s) => s.trim()).filter(Boolean);
            if (val.length === 0 && (Array.isArray(field.default) ? field.default.length === 0 : field.default === '')) continue;
        }

        // Transform prompt for llm_speech: wrap single string in array
        if (field.key === 'prompt' && methodId === 'llm_speech' && typeof val === 'string') {
            val = val.trim() ? [val.trim()] : [];
            if (val.length === 0) continue;
        }

        // Skip values that match the default
        const isDefault = (Array.isArray(val) && Array.isArray(field.default))
            ? JSON.stringify(val) === JSON.stringify(field.default)
            : val === field.default || (val === '' && field.default === '');

        if (!isDefault) {
            settings[field.key] = val;
            hasNonDefault = true;
        }
    }

    if (hasNonDefault) {
        methodSettings[methodId] = settings;
    } else {
        delete methodSettings[methodId];
    }

    updateCogIndicators();
    closeSettingsModal();
}

function updateCogIndicators() {
    document.querySelectorAll('.settings-cog').forEach((cog) => {
        const mid = cog.dataset.method;
        cog.classList.toggle('has-settings', !!methodSettings[mid]);
    });
}

function getActiveMethodSettings() {
    const selectedMethods = getSelectedMethods();
    const active = {};
    for (const m of selectedMethods) {
        if (methodSettings[m] && Object.keys(methodSettings[m]).length > 0) {
            active[m] = methodSettings[m];
        }
    }
    return Object.keys(active).length > 0 ? active : null;
}

// ── Event binding ──────────────────────────────────────────

function bindEvents() {
    // File drop zone
    $dropZone.addEventListener('click', () => $fileInput.click());
    $dropZone.addEventListener('dragover', (e) => { e.preventDefault(); $dropZone.classList.add('drag-over'); });
    $dropZone.addEventListener('dragleave', () => $dropZone.classList.remove('drag-over'));
    $dropZone.addEventListener('drop', handleDrop);
    $fileInput.addEventListener('change', handleFileSelect);

    // Transcribe
    $transcribeBtn.addEventListener('click', handleTranscribe);

    // Player
    $playBtn.addEventListener('click', () => {
        player.togglePlayPause();
    });
    player.onPlayPause((playing) => {
        $playBtn.textContent = playing ? '⏸ Pause' : '▶ Play';
    });
    player.onTimeUpdate((t) => {
        $timeDisplay.textContent = `${fmtTime(t)} / ${fmtTime(player.getDuration())}`;
        highlightActiveSegments(t);
    });
    player.onFinish(() => {
        $playBtn.textContent = '▶ Play';
    });

    // Theme
    $themeToggle.addEventListener('click', toggleTheme);

    // Modal close buttons
    document.getElementById('modal-close-x').addEventListener('click', closeSettingsModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', closeSettingsModal);
}

// ── File handling ──────────────────────────────────────────

function handleDrop(e) {
    e.preventDefault();
    $dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) selectFile(file);
}

function handleFileSelect() {
    const file = $fileInput.files[0];
    if (file) selectFile(file);
}

function selectFile(file) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!ACCEPTED_FORMATS.includes(ext)) {
        showError(`Unsupported format "${ext}". Accepted: ${ACCEPTED_FORMATS.join(', ')}`);
        return;
    }
    $fileInfo.innerHTML = `
        <span class="file-name">${escapeHtml(file.name)}</span>
        <span class="file-size">${formatBytes(file.size)}</span>
    `;
    $fileInfo.style.display = 'flex';
    $dropZone.classList.add('has-file');
    $transcribeBtn.disabled = false;
    $fileInput._selectedFile = file;
}

// ── Transcription flow ─────────────────────────────────────

async function handleTranscribe() {
    const file = $fileInput._selectedFile;
    if (!file) return;

    const methods = getSelectedMethods();
    if (methods.length === 0) {
        showError('Select at least one transcription method.');
        return;
    }
    const language = $languageSelect.value || null;

    $transcribeBtn.disabled = true;
    $resultsSection.style.display = 'none';
    $resultsGrid.innerHTML = '';
    resultsData = {};
    showStatus('Uploading audio file…', 0);

    try {
        // 1. Upload
        const uploadRes = await api.uploadFile(file);
        currentFileId = uploadRes.file_id;
        showStatus(`Uploaded "${uploadRes.filename}" (${formatBytes(uploadRes.size_bytes)}, ${uploadRes.duration_seconds?.toFixed(1) ?? '?'}s). Starting transcription…`, 10);

        // 2. Load player
        $playerSection.style.display = 'block';
        player.loadAudio(api.getAudioUrl(currentFileId));

        // 3. Start transcription
        const activeSettings = getActiveMethodSettings();
        const jobRes = await api.startTranscription(currentFileId, methods, language, activeSettings);
        currentJobId = jobRes.job_id;
        showStatus('Transcription in progress…', 20);

        // Build placeholder cards
        buildResultCards(methods);
        $resultsSection.style.display = 'block';

        // 4. Poll
        startPolling(methods);
    } catch (err) {
        showError(err.message);
        $transcribeBtn.disabled = false;
    }
}

function getSelectedMethods() {
    return Array.from(document.querySelectorAll('input[name="method"]:checked')).map((cb) => cb.value);
}

// ── Polling ────────────────────────────────────────────────

function startPolling(methods) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => pollJob(methods), POLL_INTERVAL_MS);
    pollJob(methods); // immediate first check
}

async function pollJob(methods) {
    try {
        const status = await api.getJobStatus(currentJobId);

        // Update per-method cards
        const methodStatuses = status.methods;
        const completedMethods = [];
        let doneCount = 0;
        let totalMethods = methods.length;

        for (const m of methods) {
            const ms = methodStatuses[m];
            if (ms === 'completed' || ms === 'failed') doneCount++;
            if (ms === 'completed' && !resultsData[m]) {
                completedMethods.push(m);
            }
            updateCardStatus(m, ms);
        }

        const pct = 20 + Math.round((doneCount / totalMethods) * 80);
        showStatus(`Transcription in progress… (${doneCount}/${totalMethods} methods done)`, pct);

        // Fetch newly completed results progressively
        for (const m of completedMethods) {
            try {
                const data = await api.getResults(currentJobId, m);
                const methodResult = data.results[m];
                resultsData[m] = methodResult;
                renderMethodResult(m, methodResult);
            } catch { /* will retry next poll */ }
        }

        // Handle failed methods
        for (const m of methods) {
            if (methodStatuses[m] === 'failed' && !resultsData[m]) {
                try {
                    const data = await api.getResults(currentJobId, m);
                    const methodResult = data.results[m];
                    resultsData[m] = methodResult;
                    renderMethodResult(m, methodResult);
                } catch { /* ignore */ }
            }
        }

        // Done?
        if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(pollTimer);
            pollTimer = null;
            const msg = status.status === 'completed'
                ? `Transcription complete — ${doneCount}/${totalMethods} methods finished.`
                : 'All methods failed.';
            showStatus(msg, 100);
            $transcribeBtn.disabled = false;
        }
    } catch (err) {
        console.error('Poll error:', err);
    }
}

// ── Result cards ───────────────────────────────────────────

function buildResultCards(methods) {
    $resultsGrid.innerHTML = '';
    methods.forEach((m) => {
        const info = METHODS.find((x) => x.id === m);
        const card = document.createElement('div');
        card.className = 'result-card';
        card.id = `card-${m}`;
        card.innerHTML = `
            <div class="card-header">
                <h3>${info?.label ?? m}</h3>
                <span class="card-badge processing">Processing…</span>
            </div>
            <div class="card-body">
                <div class="card-loader"><div class="spinner"></div></div>
            </div>
        `;
        $resultsGrid.appendChild(card);
    });
}

function updateCardStatus(method, status) {
    const badge = document.querySelector(`#card-${method} .card-badge`);
    if (!badge) return;
    badge.className = `card-badge ${status}`;
    const labels = { pending: 'Pending', processing: 'Processing…', completed: 'Completed', failed: 'Failed' };
    badge.textContent = labels[status] || status;
}

function renderMethodResult(method, result) {
    const card = document.getElementById(`card-${method}`);
    if (!card) return;
    const body = card.querySelector('.card-body');

    if (result.status === 'failed') {
        body.innerHTML = `<div class="card-error"><span class="error-icon">⚠</span> ${escapeHtml(result.error || 'Unknown error')}</div>`;
        return;
    }

    const durationHtml = result.duration_seconds != null
        ? `<span class="card-duration">Processed in ${result.duration_seconds.toFixed(2)}s</span>`
        : '';
    const langHtml = result.detected_language
        ? `<span class="card-lang">Language: ${escapeHtml(result.detected_language)}</span>`
        : '';

    let segmentsHtml = '';
    if (result.segments && result.segments.length > 0) {
        segmentsHtml = result.segments.map((seg, i) => `
            <div class="segment" data-method="${method}" data-index="${i}"
                 data-start="${seg.start_time}" data-end="${seg.end_time}">
                <span class="seg-time">${fmtTime(seg.start_time)}</span>
                <span class="seg-text">${escapeHtml(seg.text)}</span>
            </div>
        `).join('');
    } else {
        segmentsHtml = '<p class="no-segments">No segments returned.</p>';
    }

    body.innerHTML = `
        <div class="card-meta">${durationHtml}${langHtml}</div>
        <div class="segments" id="segments-${method}">${segmentsHtml}</div>
    `;

    // Click-to-seek
    body.querySelectorAll('.segment').forEach((el) => {
        el.addEventListener('click', () => {
            const start = parseFloat(el.dataset.start);
            player.seekTo(start);
            if (!player.isPlaying()) player.togglePlayPause();
        });
    });
}

// ── Active segment highlighting ────────────────────────────

function highlightActiveSegments(currentTime) {
    document.querySelectorAll('.segment').forEach((el) => {
        const start = parseFloat(el.dataset.start);
        const end = parseFloat(el.dataset.end);
        const active = currentTime >= start && currentTime < end;
        el.classList.toggle('active', active);

        // Auto-scroll active segment into view
        if (active && !el.dataset.scrolled) {
            el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            el.dataset.scrolled = '1';
        }
        if (!active) delete el.dataset.scrolled;
    });
}

// ── Status / progress ──────────────────────────────────────

function showStatus(message, pct) {
    $statusSection.style.display = 'block';
    $statusText.textContent = message;
    $progressBar.style.width = `${pct}%`;
    $statusSection.classList.remove('error');
}

function showError(message) {
    $statusSection.style.display = 'block';
    $statusText.textContent = message;
    $progressBar.style.width = '100%';
    $statusSection.classList.add('error');
}

// ── Health check ───────────────────────────────────────────

async function checkHealth() {
    try {
        const h = await api.getHealth();
        console.log('Backend health:', h);
    } catch {
        console.warn('Backend not reachable — make sure the server is running');
    }
}

// ── Theme toggle ───────────────────────────────────────────

function toggleTheme() {
    document.body.classList.toggle('dark');
    const isDark = document.body.classList.contains('dark');
    $themeToggle.textContent = isDark ? '☀️' : '🌙';
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// Restore theme on load
(function restoreTheme() {
    if (localStorage.getItem('theme') === 'dark') {
        document.body.classList.add('dark');
        const btn = document.getElementById('theme-toggle');
        if (btn) btn.textContent = '☀️';
    }
})();

// ── Utilities ──────────────────────────────────────────────

function fmtTime(seconds) {
    if (seconds == null || isNaN(seconds)) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
