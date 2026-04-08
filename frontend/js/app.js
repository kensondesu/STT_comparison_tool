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

// ── State ──────────────────────────────────────────────────

let currentFileId = null;
let currentJobId = null;
let pollTimer = null;
let resultsData = {};

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
        const wrapper = document.createElement('label');
        wrapper.className = 'method-check';
        wrapper.innerHTML = `<input type="checkbox" name="method" value="${id}" checked> ${label}`;
        $methodChecks.appendChild(wrapper);
    });
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
        const jobRes = await api.startTranscription(currentFileId, methods, language);
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
