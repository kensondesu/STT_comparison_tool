// Backend API client for MAI_transcribe

const BASE_URL = window.location.origin;

/**
 * Upload an audio file.
 * @param {File} file
 * @returns {Promise<{file_id: string, filename: string, size_bytes: number, duration_seconds: number, format: string, uploaded_at: string}>}
 */
export async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch(`${BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Upload failed (${res.status})`);
    }

    return res.json();
}

/**
 * Start a transcription job.
 * @param {string} fileId
 * @param {string[]} methods
 * @param {string|null} language  BCP-47 code or null for auto-detect
 * @returns {Promise<{job_id: string, file_id: string, status: string, methods: Object, language: string|null, created_at: string}>}
 */
export async function startTranscription(fileId, methods, language) {
    const body = {
        file_id: fileId,
        methods,
        language: language || null,
    };

    const res = await fetch(`${BASE_URL}/api/transcribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Transcription request failed (${res.status})`);
    }

    return res.json();
}

/**
 * Poll job status.
 * @param {string} jobId
 * @returns {Promise<{job_id: string, file_id: string, status: string, methods: Object, language: string|null, created_at: string}>}
 */
export async function getJobStatus(jobId) {
    const res = await fetch(`${BASE_URL}/api/transcribe/${jobId}`);

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Status check failed (${res.status})`);
    }

    return res.json();
}

/**
 * Get transcription results.
 * @param {string} jobId
 * @param {string} [method]  Optional — filter to a single method
 * @returns {Promise<{job_id: string, file_id: string, language: string|null, results: Object}>}
 */
export async function getResults(jobId, method) {
    let url = `${BASE_URL}/api/transcribe/${jobId}/results`;
    if (method) url += `?method=${encodeURIComponent(method)}`;

    const res = await fetch(url);

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Results fetch failed (${res.status})`);
    }

    return res.json();
}

/**
 * Get the audio streaming URL for the player.
 * @param {string} fileId
 * @returns {string}
 */
export function getAudioUrl(fileId) {
    return `${BASE_URL}/api/audio/${fileId}`;
}

/**
 * Health check.
 * @returns {Promise<{status: string, services: Object}>}
 */
export async function getHealth() {
    const res = await fetch(`${BASE_URL}/api/health`);

    if (!res.ok) {
        throw new Error(`Health check failed (${res.status})`);
    }

    return res.json();
}
