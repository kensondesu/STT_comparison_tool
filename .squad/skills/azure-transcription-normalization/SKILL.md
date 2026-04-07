# Skill: Azure Transcription Timecode Normalization

## Problem
Azure Speech Services (Batch, Fast, MAI-Transcribe-1), Azure OpenAI, and Voxtral all return timecodes in different formats. A comparison webapp needs a single normalized format.

## Pattern

### Normalized Segment Format
```json
{
  "start_time": 0.0,
  "end_time": 2.54,
  "text": "Transcribed text for this segment."
}
```
All times in **seconds** as `float`.

### Conversion Rules

| Service | Source Format | Conversion |
|---------|-------------|------------|
| Azure STT (Batch/Fast/MAI) | `offsetInTicks`, `durationInTicks` (100ns units) | `start = offset / 10_000_000`, `end = (offset + duration) / 10_000_000` |
| Azure OpenAI (gpt-4o-transcribe) | `start`, `end` in seconds | Pass through directly |
| Voxtral Mini | Text response (may lack timestamps) | Parse if available, else single segment spanning full audio duration |

### Code Snippet
```python
def normalize_azure_stt_segments(phrases: list[dict]) -> list[dict]:
    """Convert Azure STT phrase results to normalized segments."""
    return [
        {
            "start_time": p["offsetInTicks"] / 10_000_000,
            "end_time": (p["offsetInTicks"] + p["durationInTicks"]) / 10_000_000,
            "text": p["display"],
        }
        for p in phrases
    ]
```

## When to Use
- Any project comparing multiple Azure transcription services
- Any timecoded transcript visualization with Azure STT
