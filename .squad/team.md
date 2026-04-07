# Squad Team

> MAI_transcribe — Audio transcription webapp PoC

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Keaton | Lead | .squad/agents/keaton/charter.md | 🏗️ Active |
| McManus | Backend Dev | .squad/agents/mcmanus/charter.md | 🔧 Active |
| Fenster | Frontend Dev | .squad/agents/fenster/charter.md | ⚛️ Active |
| Hockney | Tester | .squad/agents/hockney/charter.md | 🧪 Active |
| Scribe | (silent) | .squad/agents/scribe/charter.md | 📋 Active |
| Ralph | Work Monitor | .squad/agents/ralph/charter.md | 🔄 Active |

## Project Context

- **Project:** MAI_transcribe — Audio transcription webapp PoC
- **Stack:** Python backend, web frontend
- **User:** Fred (kensondesu)
- **Created:** 2026-04-07
- **Description:** Web app that takes audio file input (wav, mp3, etc.) and transcribes using 5 methods: Azure STT batch, Azure STT fast, MAI-transcribe-1, Azure OpenAI gpt-4o-transcribe, Voxtral mini transcribe (Azure Foundry). Frontend for upload, transcript visualization with timecodes mapped to audio player.
