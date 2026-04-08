// Audio player with wavesurfer.js and timecode sync

import WaveSurfer from 'https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js';

let wavesurfer = null;
let currentTimeUpdateCb = null;

/**
 * Initialize the wavesurfer player inside the given container.
 * @param {string|HTMLElement} container  CSS selector or DOM element
 * @returns {WaveSurfer}
 */
export function initPlayer(container) {
    if (wavesurfer) {
        wavesurfer.destroy();
    }

    wavesurfer = WaveSurfer.create({
        container,
        waveColor: '#a0aec0',
        progressColor: '#4f46e5',
        cursorColor: '#4f46e5',
        cursorWidth: 2,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 96,
        normalize: true,
        backend: 'MediaElement',
    });

    return wavesurfer;
}

/**
 * Load an audio URL into the player.
 * @param {string} url
 * @returns {Promise<void>}
 */
export function loadAudio(url) {
    if (!wavesurfer) throw new Error('Player not initialized');
    wavesurfer.load(url);
    return new Promise((resolve) => {
        wavesurfer.once('ready', resolve);
    });
}

/** Play / pause toggle */
export function togglePlayPause() {
    if (!wavesurfer) return;
    wavesurfer.playPause();
}

/** @returns {boolean} */
export function isPlaying() {
    return wavesurfer ? wavesurfer.isPlaying() : false;
}

/**
 * Seek to a specific time in seconds.
 * @param {number} seconds
 */
export function seekTo(seconds) {
    if (!wavesurfer) return;
    const duration = wavesurfer.getDuration();
    if (duration > 0) {
        wavesurfer.seekTo(seconds / duration);
    }
}

/** @returns {number} current time in seconds */
export function getCurrentTime() {
    return wavesurfer ? wavesurfer.getCurrentTime() : 0;
}

/** @returns {number} duration in seconds */
export function getDuration() {
    return wavesurfer ? wavesurfer.getDuration() : 0;
}

/**
 * Register a callback called on every animation frame with the current time.
 * Used to highlight active transcript segments.
 * @param {(currentTime: number) => void} cb
 */
export function onTimeUpdate(cb) {
    if (currentTimeUpdateCb && wavesurfer) {
        wavesurfer.un('timeupdate', currentTimeUpdateCb);
    }
    currentTimeUpdateCb = cb;
    if (wavesurfer) {
        wavesurfer.on('timeupdate', cb);
    }
}

/**
 * Register a callback for play state changes.
 * @param {(playing: boolean) => void} cb
 */
export function onPlayPause(cb) {
    if (!wavesurfer) return;
    wavesurfer.on('play', () => cb(true));
    wavesurfer.on('pause', () => cb(false));
}

/**
 * Register a callback when audio finishes playing.
 * @param {() => void} cb
 */
export function onFinish(cb) {
    if (!wavesurfer) return;
    wavesurfer.on('finish', cb);
}

/**
 * Destroy the player instance.
 */
export function destroyPlayer() {
    if (wavesurfer) {
        wavesurfer.destroy();
        wavesurfer = null;
    }
}
