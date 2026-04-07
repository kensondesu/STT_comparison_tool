# Decision: Test-Backend Integration Alignment

**Date:** 2026-04-07
**Author:** Hockney (Tester)
**Status:** Applied

## Context
Tests were written TDD-first in parallel with backend implementation, causing 24 integration mismatches.

## Decision
Aligned all test mocks, fixtures, and assertions with McManus's actual backend code:
- Class names use PascalCase with lowercase acronyms (`AzureSttBatchService`, not `AzureSTTBatchService`)
- `settings.upload_dir` is always `Path`, never `str`
- Upload tests must provide format-specific magic bytes (backend validates headers)
- `TranscriptionResult` is a dataclass in `backend.services.base` (no `duration_seconds` field)

## Impact
- Test suite now passes green (67 pass, 21 graceful skips)
- Establishes naming convention precedent for future service classes
