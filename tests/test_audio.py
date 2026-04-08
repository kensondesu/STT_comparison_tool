"""
Audio utility tests — format detection, MIME types, metadata extraction.

Tests validate:
- Format detection from file extension
- MIME type mapping for all supported formats
- Audio metadata extraction via mutagen (mocked)
- Handling of unknown/unsupported extensions
"""

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestFormatDetection:
    """backend.utils.audio should detect format from file extension."""

    EXTENSION_MAP = {
        "wav": "wav",
        "mp3": "mp3",
        "flac": "flac",
        "ogg": "ogg",
        "m4a": "m4a",
        "webm": "webm",
    }

    def _get_format_func(self):
        try:
            from backend.utils.audio import get_audio_format
            return get_audio_format
        except ImportError:
            pytest.skip("backend.utils.audio not yet implemented")

    @pytest.mark.parametrize("ext,expected", list(EXTENSION_MAP.items()))
    def test_detect_from_extension(self, ext, expected):
        func = self._get_format_func()
        result = func(f"recording.{ext}")
        assert result == expected

    def test_case_insensitive(self):
        func = self._get_format_func()
        assert func("recording.WAV") == "wav"
        assert func("song.MP3") == "mp3"

    def test_unsupported_extension(self):
        func = self._get_format_func()
        with pytest.raises((ValueError, KeyError)):
            func("document.pdf")

    def test_no_extension(self):
        func = self._get_format_func()
        with pytest.raises((ValueError, KeyError)):
            func("noextfile")


# ---------------------------------------------------------------------------
# MIME type mapping
# ---------------------------------------------------------------------------


class TestMimeTypeMapping:
    """backend.utils.audio should map formats to correct MIME types."""

    MIME_MAP = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "flac": "audio/flac",
        "ogg": "audio/ogg",
        "m4a": "audio/mp4",
        "webm": "audio/webm",
    }

    def _get_mime_func(self):
        try:
            from backend.utils.audio import get_mime_type
            return get_mime_type
        except ImportError:
            pytest.skip("backend.utils.audio not yet implemented")

    @pytest.mark.parametrize("fmt,expected_mime", list(MIME_MAP.items()))
    def test_mime_for_format(self, fmt, expected_mime):
        func = self._get_mime_func()
        result = func(fmt)
        assert result == expected_mime

    def test_unsupported_format_mime(self):
        func = self._get_mime_func()
        with pytest.raises((ValueError, KeyError)):
            func("exe")


# ---------------------------------------------------------------------------
# Supported format validation
# ---------------------------------------------------------------------------


class TestSupportedFormats:
    """Verify the set of accepted formats matches the API contract."""

    EXPECTED_FORMATS = {"wav", "mp3", "flac", "ogg", "m4a", "webm"}

    def test_accepted_formats_constant(self):
        try:
            from backend.utils.audio import SUPPORTED_FORMATS
        except ImportError:
            try:
                from backend.utils.audio import ACCEPTED_FORMATS as SUPPORTED_FORMATS
            except ImportError:
                pytest.skip("Supported formats constant not yet defined")

        # Convert to set for comparison (might be list, tuple, or set)
        formats = set(SUPPORTED_FORMATS)
        assert formats == self.EXPECTED_FORMATS, (
            f"Supported formats mismatch.\n"
            f"  Expected: {self.EXPECTED_FORMATS}\n"
            f"  Got:      {formats}"
        )


# ---------------------------------------------------------------------------
# Audio metadata extraction (mutagen)
# ---------------------------------------------------------------------------


class TestAudioMetadata:
    """backend.utils.audio should extract duration and sample rate from audio files."""

    def _get_metadata_func(self):
        try:
            from backend.utils.audio import get_audio_metadata
            return get_audio_metadata
        except ImportError:
            pytest.skip("backend.utils.audio.get_audio_metadata not yet implemented")

    def test_wav_metadata(self):
        """Mocked mutagen should return duration for a WAV file."""
        func = self._get_metadata_func()

        mock_audio = MagicMock()
        mock_audio.info.length = 124.5
        mock_audio.info.sample_rate = 44100
        mock_audio.info.channels = 2

        with patch("mutagen.File", return_value=mock_audio):
            metadata = func("recording.wav")

        assert metadata["duration_seconds"] == pytest.approx(124.5)

    def test_mp3_metadata(self):
        func = self._get_metadata_func()

        mock_audio = MagicMock()
        mock_audio.info.length = 200.0
        mock_audio.info.sample_rate = 44100
        mock_audio.info.channels = 2

        with patch("mutagen.File", return_value=mock_audio):
            metadata = func("song.mp3")

        assert metadata["duration_seconds"] == pytest.approx(200.0)

    def test_unreadable_file_returns_none_duration(self):
        """If mutagen can't parse the file, duration should be None."""
        func = self._get_metadata_func()

        with patch("mutagen.File", return_value=None):
            metadata = func("corrupt.wav")

        assert metadata.get("duration_seconds") is None

    def test_file_not_found(self):
        """A non-existent file should raise or return None gracefully."""
        func = self._get_metadata_func()

        with patch("mutagen.File", side_effect=FileNotFoundError):
            with pytest.raises((FileNotFoundError, Exception)):
                func("nonexistent.wav")
