"""
Health endpoint tests — GET /api/health

Tests validate:
- Health check returns 200
- Response contains status and services dict
- Each of the 5 service methods is listed
- Service status is 'configured' or 'not_configured'
"""

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_200(client):
    """GET /api/health should always return 200."""
    resp = await client.get("/api/health")
    assert resp.status_code == 200


async def test_health_response_schema(client):
    """Response must have 'status' and 'services' keys."""
    resp = await client.get("/api/health")
    body = resp.json()

    assert "status" in body
    assert body["status"] == "ok"
    assert "services" in body
    assert isinstance(body["services"], dict)


async def test_health_lists_all_services(client):
    """All 7 transcription methods should be listed under 'services'."""
    resp = await client.get("/api/health")
    services = resp.json()["services"]

    expected_methods = {
        "azure_stt_batch",
        "azure_stt_fast",
        "mai_transcribe",
        "aoai_transcribe",
        "voxtral",
        "whisper",
        "llm_speech",
    }
    assert set(services.keys()) == expected_methods, (
        f"Missing services: {expected_methods - set(services.keys())}"
    )


async def test_health_service_status_values(client):
    """Each service status must be either 'configured' or 'not_configured'."""
    resp = await client.get("/api/health")
    services = resp.json()["services"]

    valid_statuses = {"configured", "not_configured"}
    for method, status in services.items():
        assert status in valid_statuses, (
            f"Service '{method}' has unexpected status '{status}'"
        )


async def test_health_unconfigured_without_env(client, monkeypatch):
    """With no Azure/OpenAI keys, services should report 'not_configured'."""
    # Clear settings attributes directly (env vars don't affect the singleton)
    monkeypatch.setattr("backend.config.settings.azure_speech_key", "")
    monkeypatch.setattr("backend.config.settings.azure_speech_region", "")
    monkeypatch.setattr("backend.config.settings.azure_speech_endpoint", "")
    monkeypatch.setattr("backend.config.settings.azure_storage_connection_string", "")
    monkeypatch.setattr("backend.config.settings.azure_storage_account_name", "")
    monkeypatch.setattr("backend.config.settings.mai_speech_key", "")
    monkeypatch.setattr("backend.config.settings.mai_speech_region", "")
    monkeypatch.setattr("backend.config.settings.mai_speech_endpoint", "")
    monkeypatch.setattr("backend.config.settings.azure_openai_api_key", "")
    monkeypatch.setattr("backend.config.settings.azure_openai_endpoint", "")
    monkeypatch.setattr("backend.config.settings.voxtral_endpoint_url", "")
    monkeypatch.setattr("backend.config.settings.voxtral_endpoint_key", "")

    resp = await client.get("/api/health")
    services = resp.json()["services"]

    for method, status in services.items():
        assert status == "not_configured", (
            f"Service '{method}' should be 'not_configured' without env vars, got '{status}'"
        )


# ---------------------------------------------------------------------------
# Whisper + LLM Speech health check coverage
# ---------------------------------------------------------------------------


async def test_health_whisper_appears(client):
    """The 'whisper' service must appear in health response."""
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert "whisper" in services


async def test_health_llm_speech_appears(client):
    """The 'llm_speech' service must appear in health response."""
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert "llm_speech" in services


async def test_health_whisper_configured_when_endpoint_set(client, monkeypatch):
    """Whisper should be 'configured' when azure_openai_endpoint is set."""
    monkeypatch.setattr("backend.config.settings.azure_openai_endpoint", "https://fake.openai.azure.com/")
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert services["whisper"] == "configured"


async def test_health_whisper_not_configured_when_empty(client, monkeypatch):
    """Whisper should be 'not_configured' when azure_openai_endpoint is empty."""
    monkeypatch.setattr("backend.config.settings.azure_openai_endpoint", "")
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert services["whisper"] == "not_configured"


async def test_health_llm_speech_configured_when_endpoint_set(client, monkeypatch):
    """LLM Speech should be 'configured' when azure_speech_endpoint is set."""
    monkeypatch.setattr("backend.config.settings.azure_speech_key", "")
    monkeypatch.setattr("backend.config.settings.azure_speech_endpoint", "https://fake.speech.azure.com")
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert services["llm_speech"] == "configured"


async def test_health_llm_speech_configured_when_key_set(client, monkeypatch):
    """LLM Speech should be 'configured' when azure_speech_key is set."""
    monkeypatch.setattr("backend.config.settings.azure_speech_key", "fake-key")
    monkeypatch.setattr("backend.config.settings.azure_speech_endpoint", "")
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert services["llm_speech"] == "configured"


async def test_health_llm_speech_not_configured_when_empty(client, monkeypatch):
    """LLM Speech should be 'not_configured' when both endpoint and key are empty."""
    monkeypatch.setattr("backend.config.settings.azure_speech_key", "")
    monkeypatch.setattr("backend.config.settings.azure_speech_endpoint", "")
    resp = await client.get("/api/health")
    services = resp.json()["services"]
    assert services["llm_speech"] == "not_configured"
