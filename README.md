# STT Comparison Tool

A web app that compares 7 Azure transcription engines side-by-side with timecoded playback and click-to-seek navigation.

## Features

- **7 Transcription Methods**: Azure STT Batch, STT Fast, MAI-Transcribe-1, GPT-4o-transcribe, Whisper, LLM Speech, Voxtral Mini
- **Multi-Format Audio Upload**: .wav, .mp3, .flac, .ogg, .m4a, .webm
- **Timecoded Transcript Visualization**: Built with [wavesurfer.js](https://wavesurfer.xyz/) for interactive waveform display
- **Click-to-Seek Navigation**: Click any segment to jump audio to that exact timestamp
- **Per-Model Settings**: Configure phrase lists, diarization, profanity filtering, prompt, temperature, and more
- **Language Support**: 33 languages plus auto-detect
- **Dark/Light Theme**: Seamless UI customization
- **Zero API Keys**: Authentication via managed identity (`DefaultAzureCredential`) — secure by default

## Tech Stack

- **Backend**: Python 3.11+ / FastAPI
- **Frontend**: Vanilla HTML / JavaScript / CSS
- **Audio Player**: wavesurfer.js v7 (via CDN)
- **Authentication**: Azure SDKs with managed identity support
- **File Storage**: Local filesystem (uploads/)
- **Task Execution**: asyncio for concurrent transcription

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (fast Python package manager)
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) + `az login`

### Setup

```bash
# Clone and enter directory
git clone https://github.com/kensondesu/MAI_transcribe.git
cd MAI_transcribe

# Copy environment template and fill in your Azure endpoints
cp .env.example .env
# Edit .env with your Azure Speech, OpenAI, and Storage endpoints

# Install dependencies
uv sync

# Run development server
uv run python -m uvicorn backend.main:app --reload
```

Open http://localhost:8000 in your browser.

## Deploy to Azure (Container Apps)

### Greenfield Deployment (from scratch)

```bash
cd infra
./deploy.sh
```

This creates all resources in `swedencentral` region by default.

### Brownfield Deployment (existing resources)

```bash
RESOURCE_GROUP="my-existing-rg" \
LOCATION="westeurope" \
DEPLOYMENT_MODE="brownfield" \
EXISTING_SPEECH_RESOURCE_ID="..." \
./infra/deploy.sh
```

See `infra/README.md` for full deployment guide, environment variables, and troubleshooting.

## Testing

```bash
uv run pytest
```

Runs 91 tests covering API routes, transcription services, and audio validation.

## Architecture

For detailed system design, service integration, timecode normalization, and job lifecycle:
- **ARCHITECTURE.md** — System design and transcription service specs
- **API_CONTRACT.md** — REST API specification

## Environment Variables

All Azure services authenticate via `DefaultAzureCredential` (managed identity in Azure, Azure CLI locally). Set `AZURE_SPEECH_REGION`, `AZURE_OPENAI_ENDPOINT`, etc. in `.env`.

See `.env.example` for all available options. Legacy API keys are supported as fallback for local testing.

## Project Structure

```
MAI_transcribe/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── routers/             # API endpoints
│   ├── services/            # Transcription services (7 engines)
│   ├── models/              # Pydantic schemas
│   └── utils/               # Audio validation, storage helpers
├── frontend/
│   ├── index.html           # Single-page app
│   ├── css/style.css        # Styles
│   └── js/                  # app.js, api.js, player.js
├── tests/                   # 91 tests
├── infra/                   # Bicep templates & deploy script
├── Dockerfile               # Container image
├── pyproject.toml           # Python project config
└── .env.example             # Environment template
```

## Contributing

Run linter and type checker before submitting:

```bash
uv run ruff check backend/ frontend/ tests/
uv run mypy backend/
```

## License

Specify your license here.
