"""
Tests for the ffmpeg/ffprobe audio preprocessing pipeline.

Validates ensure_compatible_format():
- Compatible formats (wav, mp3, flac) pass through unchanged
- Incompatible containers (mp4/m4a) trigger conversion to WAV
- Corrupt files raise ValueError
- Missing ffprobe/ffmpeg degrades gracefully
- Conversion failures raise ValueError
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.utils.audio import ensure_compatible_format

PATCH_TARGET = "backend.utils.audio.asyncio.create_subprocess_exec"


def _make_probe_process(format_name: str, returncode: int = 0) -> AsyncMock:
    """Build a mock subprocess that behaves like ffprobe."""
    proc = AsyncMock()
    stdout = json.dumps({"format": {"format_name": format_name}}).encode()
    proc.communicate.return_value = (stdout, b"")
    proc.returncode = returncode
    return proc


def _make_convert_process(returncode: int = 0) -> AsyncMock:
    """Build a mock subprocess that behaves like ffmpeg conversion."""
    proc = AsyncMock()
    proc.communicate.return_value = (b"", b"")
    proc.returncode = returncode
    return proc


# -------------------------------------------------------------------
# Pass-through tests — compatible formats need no conversion
# -------------------------------------------------------------------


class TestCompatibleFormats:

    @pytest.mark.asyncio
    async def test_compatible_wav_passes_through(self, tmp_path):
        wav_file = tmp_path / "audio.wav"
        wav_file.write_bytes(b"RIFF" + b"\x00" * 100)

        probe = _make_probe_process("wav")

        with patch(PATCH_TARGET, return_value=probe):
            result = await ensure_compatible_format(wav_file)

        assert result == wav_file

    @pytest.mark.asyncio
    async def test_compatible_mp3_passes_through(self, tmp_path):
        mp3_file = tmp_path / "audio.mp3"
        mp3_file.write_bytes(b"ID3" + b"\x00" * 100)

        probe = _make_probe_process("mp3")

        with patch(PATCH_TARGET, return_value=probe):
            result = await ensure_compatible_format(mp3_file)

        assert result == mp3_file

    @pytest.mark.asyncio
    async def test_compatible_flac_passes_through(self, tmp_path):
        flac_file = tmp_path / "audio.flac"
        flac_file.write_bytes(b"fLaC" + b"\x00" * 100)

        probe = _make_probe_process("flac")

        with patch(PATCH_TARGET, return_value=probe):
            result = await ensure_compatible_format(flac_file)

        assert result == flac_file


# -------------------------------------------------------------------
# Conversion tests — incompatible containers trigger ffmpeg
# -------------------------------------------------------------------


class TestConversion:

    @pytest.mark.asyncio
    async def test_mp4_container_gets_converted(self, tmp_path):
        m4a_file = tmp_path / "audio.m4a"
        m4a_file.write_bytes(b"\x00\x00\x00\x20ftyp" + b"\x00" * 100)

        probe = _make_probe_process("mov,mp4,m4a,3gp")
        convert = _make_convert_process(returncode=0)

        call_count = 0

        async def _subprocess_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return probe
            # ffmpeg writes the output file — create it so stat() works
            output_path = tmp_path / "audio.wav"
            output_path.write_bytes(b"RIFF" + b"\x00" * 100)
            return convert

        with patch(PATCH_TARGET, side_effect=_subprocess_router):
            result = await ensure_compatible_format(m4a_file)

        assert result.suffix == ".wav"
        assert call_count == 2  # ffprobe + ffmpeg

    @pytest.mark.asyncio
    async def test_conversion_failure_raises(self, tmp_path):
        bad_file = tmp_path / "audio.aac"
        bad_file.write_bytes(b"\x00" * 100)

        probe = _make_probe_process("aac")
        convert = _make_convert_process(returncode=1)

        call_count = 0

        async def _subprocess_router(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return probe if call_count == 1 else convert

        with patch(PATCH_TARGET, side_effect=_subprocess_router):
            with pytest.raises(ValueError, match="Failed to convert"):
                await ensure_compatible_format(bad_file)


# -------------------------------------------------------------------
# Error-handling tests
# -------------------------------------------------------------------


class TestErrorHandling:

    @pytest.mark.asyncio
    async def test_corrupt_file_raises_error(self, tmp_path):
        corrupt = tmp_path / "broken.wav"
        corrupt.write_bytes(b"\x00" * 50)

        probe = _make_probe_process("", returncode=1)

        with patch(PATCH_TARGET, return_value=probe):
            with pytest.raises(ValueError, match="corrupt"):
                await ensure_compatible_format(corrupt)

    @pytest.mark.asyncio
    async def test_ffmpeg_not_found_graceful(self, tmp_path):
        missing = tmp_path / "audio.wav"
        missing.write_bytes(b"RIFF" + b"\x00" * 100)

        with patch(PATCH_TARGET, side_effect=FileNotFoundError):
            result = await ensure_compatible_format(missing)

        assert result == missing  # graceful degradation
