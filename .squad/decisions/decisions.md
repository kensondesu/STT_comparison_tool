# Decisions

## Decision: Migrate Azure Auth to DefaultAzureCredential

**Date:** 2026-04-07  
**Author:** McManus (Backend Dev)  
**Directive from:** Fred (kensondesu)  
**Category:** Security / Infrastructure  

### Summary

All Azure service integrations migrated from hardcoded API keys and connection strings to `DefaultAzureCredential` from the `azure-identity` SDK. This enables managed identity in Azure deployments and developer-friendly local auth via `az login` or VS Code.

### What Changed

| File | Before | After |
|------|--------|-------|
| `requirements.txt` | — | Added `azure-identity>=1.19.0` |
| `backend/config.py` | Key fields only | Added `azure_storage_account_name`, shared sync credential, `get_cognitive_services_token()` helper |
| `azure_stt_batch.py` | `Ocp-Apim-Subscription-Key` + `from_connection_string()` + account-key SAS | Bearer token + `BlobServiceClient(credential=DefaultAzureCredential())` + user-delegation SAS |
| `azure_stt_fast.py` | `Ocp-Apim-Subscription-Key` | Bearer token via `get_cognitive_services_token()` |
| `mai_transcribe.py` | `Ocp-Apim-Subscription-Key` | Bearer token via `get_cognitive_services_token()` |
| `aoai_transcribe.py` | `api_key=` | `azure_ad_token_provider` via `get_bearer_token_provider(AsyncDefaultAzureCredential(), ...)` |
| `voxtral_transcribe.py` | `AzureKeyCredential(key)` | `AsyncDefaultAzureCredential()` |
| `.env.example` | Key vars required | Keys commented out; documented as optional fallback |
| `ARCHITECTURE.md` | Key-based env vars | Updated to reflect managed identity defaults |

### Fallback Strategy

Every service checks if its legacy key env-var is set (non-empty). If set, the service uses key-based auth. This lets Fred test locally with keys while deploying to Azure with managed identity — zero code changes needed between environments.

### Verification

- All 6 module imports pass
- Server starts on port 8099, health endpoint returns 200
- No keys required at startup

### Impact

- **Hockney:** Test mocks for `Ocp-Apim-Subscription-Key` headers may need updating to mock bearer tokens or the credential fallback path
- **Fenster:** No frontend impact — API contract unchanged
- **Keaton:** Azure RBAC roles must be assigned to the managed identity (Cognitive Services User, Storage Blob Data Contributor, etc.)

---

## Decision: Test-Backend Integration Alignment

**Date:** 2026-04-07  
**Author:** Hockney (Tester)  
**Status:** Applied

### Context
Tests were written TDD-first in parallel with backend implementation, causing 24 integration mismatches.

### Decision
Aligned all test mocks, fixtures, and assertions with McManus's actual backend code:
- Class names use PascalCase with lowercase acronyms (`AzureSttBatchService`, not `AzureSTTBatchService`)
- `settings.upload_dir` is always `Path`, never `str`
- Upload tests must provide format-specific magic bytes (backend validates headers)
- `TranscriptionResult` is a dataclass in `backend.services.base` (no `duration_seconds` field)

### Impact
- Test suite now passes green (67 pass, 21 graceful skips)
- Establishes naming convention precedent for future service classes

---

## User Directive: Managed Identity Required

**Date:** 2026-04-07T17:11:42Z  
**By:** Fred (via Copilot)  
**Status:** Captured for team memory

### Directive
Must use managed identities for Azure services — no connection strings.

### Why
User request — ensuring secure, scalable authentication strategy for Azure deployments.
