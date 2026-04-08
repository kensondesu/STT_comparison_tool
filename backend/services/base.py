"""Abstract base class for transcription services."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from backend.models.schemas import Segment


@dataclass
class TranscriptionResult:
    """Normalized output from any transcription service."""
    segments: list[Segment] = field(default_factory=list)
    full_text: str = ""
    detected_language: str | None = None


class TranscriptionService(ABC):
    """Every transcription backend implements this interface."""

    @abstractmethod
    async def transcribe(
        self, audio_path: str, language: str | None = None
    ) -> TranscriptionResult:
        """Run transcription and return normalized segments with timecodes."""
