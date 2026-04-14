"""Application settings loaded from environment variables.

Authentication: All Azure services use ``DefaultAzureCredential`` (managed
identity in Azure, Azure CLI / VS Code locally).  If a legacy API key env-var
is set it is used as a fallback so Fred can test locally with keys while
deploying with managed identity.
"""

from pathlib import Path

from azure.identity import DefaultAzureCredential
from pydantic_settings import BaseSettings

COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


class Settings(BaseSettings):
    # Azure Speech Services (Batch, Fast)
    azure_speech_key: str = ""          # optional fallback — leave blank to use managed identity
    azure_speech_region: str = "eastus"
    azure_speech_endpoint: str = ""     # custom subdomain endpoint (required for managed identity)
                                        # e.g. "https://my-resource.cognitiveservices.azure.com/"

    # MAI-Transcribe-1 (separate resource/region from STT)
    mai_speech_key: str = ""            # optional fallback
    mai_speech_region: str = "eastus"
    mai_speech_endpoint: str = ""       # e.g. "https://foundry-mai-transcribe.cognitiveservices.azure.com/"

    # Azure Blob Storage (Batch only)
    azure_storage_account_name: str = ""  # e.g. "mystorageaccount"
    azure_storage_connection_string: str = ""  # optional fallback
    azure_storage_container_name: str = "transcription-audio"

    # Azure OpenAI (gpt-4o-transcribe)
    azure_openai_api_key: str = ""      # optional fallback
    azure_openai_endpoint: str = ""
    azure_openai_deployment_name: str = "gpt-4o-transcribe"
    azure_whisper_model_id: str = ""  # optional — if empty, auto-discover Whisper base model

    # Voxtral Mini (Azure Foundry)
    voxtral_endpoint_url: str = ""
    voxtral_endpoint_key: str = ""      # optional fallback

    # App settings
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    max_file_size_bytes: int = 300 * 1024 * 1024  # 300 MB
    accepted_formats: list[str] = ["wav", "mp3", "flac", "ogg", "m4a", "webm"]
    method_timeout_seconds: int = 300  # 5 minutes per method
    batch_poll_interval_seconds: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()

# Lazy-initialised sync credential (avoids auth probe at import time, which
# would hang in test environments without Azure credentials).
_sync_credential: DefaultAzureCredential | None = None


def _get_sync_credential() -> DefaultAzureCredential:
    global _sync_credential
    if _sync_credential is None:
        _sync_credential = DefaultAzureCredential()
    return _sync_credential


def get_cognitive_services_token() -> str:
    """Obtain a bearer token for Cognitive Services (sync)."""
    token = _get_sync_credential().get_token(COGNITIVE_SERVICES_SCOPE)
    return token.token
