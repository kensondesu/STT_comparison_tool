# STT Comparison Tool — Deployment Guide

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) | ≥ 2.60 | Azure resource management |
| [Bicep CLI](https://learn.microsoft.com/azure/azure-resource-manager/bicep/install) | ≥ 0.28 | Infrastructure as code (bundled with Azure CLI) |
| [Docker](https://docs.docker.com/get-docker/) | ≥ 24.0 | Local builds (optional — ACR builds remotely) |
| [jq](https://jqlang.github.io/jq/) | ≥ 1.6 | JSON parsing in deploy script |
| Azure subscription | — | With permissions to create resources |

## Quickstart (Greenfield)

Deploy everything from scratch with a single command:

```bash
# Login to Azure
az login

# Run deployment (creates all resources)
./infra/deploy.sh
```

This will:
1. Create resource group `stt-comparison-rg` in `swedencentral`
2. Deploy all infrastructure via Bicep (ACR, Container Apps Environment, Container App)
3. Build the Docker image in ACR
4. Deploy the image to the Container App

## Brownfield Deployment

If you already have existing Azure resources, override the defaults:

```bash
RESOURCE_GROUP="my-existing-rg" \
LOCATION="westeurope" \
ENVIRONMENT_NAME="my-env" \
DEPLOYMENT_MODE="brownfield" \
EXISTING_SPEECH_RESOURCE_ID="..." \
EXISTING_MAI_SPEECH_RESOURCE_ID="..." \
EXISTING_OPENAI_RESOURCE_ID="..." \
EXISTING_SPEECH_ENDPOINT="https://my-region.tts.speech.microsoft.com/" \
EXISTING_MAI_SPEECH_ENDPOINT="https://my-region.tts.speech.microsoft.com/" \
EXISTING_OPENAI_ENDPOINT="https://my-openai.openai.azure.com/" \
./infra/deploy.sh
```

Or pass existing resource IDs and endpoints via Bicep parameters — edit `infra/main.bicepparam` to specify existing resources:

```bicep
param deploymentMode = 'brownfield'
param existingSpeechResourceId = '/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/my-speech'
param existingMaiSpeechResourceId = '/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/my-mai-speech'
param existingOpenAiResourceId = '/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/my-openai'
param existingStorageAccountId = '/subscriptions/.../providers/Microsoft.Storage/storageAccounts/mystg'
param existingSpeechEndpoint = 'https://my-region.tts.speech.microsoft.com/'
param existingMaiSpeechEndpoint = 'https://my-region.tts.speech.microsoft.com/'
param existingOpenAiEndpoint = 'https://my-openai.openai.azure.com/'
```

## Environment Variables

### Deploy Script Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOURCE_GROUP` | `stt-comparison-rg` | Azure resource group name |
| `LOCATION` | `swedencentral` | Azure region |
| `ENVIRONMENT_NAME` | `stt-comparison` | Container Apps environment name |
| `DEPLOYMENT_MODE` | `greenfield` | `greenfield` (create all) or `brownfield` (use existing) |

### Application Configuration (Container App env vars)

These are set in the Bicep template and injected into the running container:

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_SPEECH_REGION` | Yes | Azure Speech Services region |
| `AZURE_SPEECH_RESOURCE_ID` | Yes | Speech resource ID (for managed identity) |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Yes | gpt-4o-transcribe deployment name |
| `AZURE_WHISPER_DEPLOYMENT_NAME` | No | Whisper deployment name (default: `whisper`) |
| `AZURE_STORAGE_ACCOUNT_NAME` | Yes | Storage account for batch transcription |
| `AZURE_STORAGE_CONTAINER_NAME` | No | Blob container name (default: `audio-uploads`) |
| `VOXTRAL_ENDPOINT` | Yes | Voxtral Foundry endpoint URL |
| `MAI_SPEECH_REGION` | No | MAI-Transcribe-1 region (if different from Speech) |
| `MAI_SPEECH_RESOURCE_ID` | No | MAI Speech resource ID |

> **Note:** No API keys in the container — authentication uses managed identity via `DefaultAzureCredential`.

## Local Docker Build

To test the Docker image locally:

```bash
# Build
docker build -t stt-comparison:test .

# Run (with local .env file)
docker run --env-file .env -p 8000:8000 stt-comparison:test
```

Then open http://localhost:8000 in your browser.

## Troubleshooting

### ACR build fails with "unauthorized"

```bash
# Ensure you're logged in
az login
az acr login --name <acr-name>
```

### Container App not starting

Check logs:

```bash
az containerapp logs show \
  --name <app-name> \
  --resource-group <rg-name> \
  --type console \
  --follow
```

### "Module not found" errors in container

The Docker image copies `backend/` and `frontend/` directories. Ensure all Python files are committed and not in `.dockerignore`.

### Managed identity token errors

The Container App must have a system-assigned managed identity with the correct role assignments:
- **Cognitive Services User** on the Speech resource
- **Cognitive Services OpenAI User** on the Azure OpenAI resource
- **Storage Blob Data Contributor** on the Storage account

These roles are configured in the Bicep template.

### Port mismatch

The app listens on port **8000**. Ensure the Container App ingress is configured for port 8000 (set in the Bicep template).
