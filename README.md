# Foundry Local + NVIDIA Nemotron: Voice-Activated AI Assistant

[![CI](https://github.com/leestott/fl-nemotron/actions/workflows/ci.yml/badge.svg)](https://github.com/leestott/fl-nemotron/actions/workflows/ci.yml)
[![Security Scans](https://github.com/leestott/fl-nemotron/actions/workflows/security.yml/badge.svg)](https://github.com/leestott/fl-nemotron/actions/workflows/security.yml)

A fully on-device voice assistant built with **Microsoft Foundry Local** and **NVIDIA Nemotron**. Speech is transcribed locally by Whisper, reasoned over by Nemotron, and spoken back via pyttsx3 — no cloud endpoints, no API keys, no data leaving your device.

---

## Architecture

```
Microphone
    │
    ▼  (sounddevice)
  WAV file  ──►  Whisper (Foundry Local)  ──►  Transcript text
                                                      │
                                                      ▼
                                          Nemotron (Foundry Local)
                                          + Conversation history
                                                      │
                                                      ▼
                                          Response text  ──►  pyttsx3 TTS  ──►  Speakers
```

All three stages — capture, transcription, and generation — run in-process via the Foundry Local SDK. The optional HTTP service layer exposes an OpenAI-compatible endpoint for integration with other tools.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Required by Foundry Local SDK |
| Foundry Local CLI | Latest | `winget install Microsoft.FoundryLocal` (Windows) |
| Node.js | Optional | Speeds up model catalog queries |
| Microphone | Any | For voice input modes |

---

## Quick Start

### Windows

```powershell
git clone https://github.com/leestott/fl-nemotron
cd fl-nemotron
.\setup.ps1
```

### macOS / Linux

```bash
git clone https://github.com/leestott/fl-nemotron
cd fl-nemotron
bash setup.sh
```

### Manual Setup

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# Windows (recommended — enables NPU/GPU via WinML):
pip install foundry-local-sdk-winml
# macOS/Linux:
pip install foundry-local-sdk

pip install -r requirements.txt
cp .env.example .env
```

---

## Model Download

The setup script downloads models automatically. To download manually:

```bash
# List all available models
foundry model ls

# Download the models used by this app
foundry model run whisper-base
foundry model run nemotron-nano
```

Or from Python:

```python
python src/utils.py --list-models
```

---

## Running the Assistant

### Web UI (Recommended)

The web interface provides a full chat experience with streaming responses, microphone recording, and real-time model status. It works in **demo mode** even without Foundry Local installed.

```powershell
# Windows
.venv\Scripts\uvicorn.exe app:app --app-dir src --host 0.0.0.0 --port 8000
```

```bash
# macOS / Linux
.venv/bin/uvicorn app:app --app-dir src --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser.

| Endpoint | Description |
|---|---|
| `GET /` | Chat UI |
| `GET /api/status` | Model status (demo or foundry mode) |
| `POST /api/chat` | Chat — `stream:true` returns SSE, `stream:false` returns JSON |
| `POST /api/transcribe` | Upload audio file → transcription text |
| `GET /docs` | Interactive OpenAPI docs (Swagger UI) |

> **Demo mode** is activated automatically when Foundry Local is not installed or not running. All responses are simulated so you can explore the UI without any model setup.

---

### CLI — Voice-Activity Detection (VAD) Mode
Speak to start recording. The assistant stops when it detects silence.

```bash
python src/voice_assistant.py
```

### CLI — Press-to-Talk Mode
Press ENTER to start recording, press ENTER again to stop.

```bash
python src/voice_assistant.py --press-to-talk
```

### CLI — Text-Only Mode
Type your questions — no microphone required. Useful for testing.

```bash
python src/voice_assistant.py --text-only
```

### CLI — Debug Mode
Enable verbose logging to diagnose audio or model issues.

```bash
python src/voice_assistant.py --debug
```

---

## Scenarios

Three pre-built scenarios demonstrate different applications of the voice assistant.

### 1. Voice Q&A (`scenarios/scenario_qa.py`)
A focused factual Q&A assistant. Nemotron answers in 1–2 sentences optimised for voice delivery.

```bash
python scenarios/scenario_qa.py
python scenarios/scenario_qa.py --text-only
```

**Example exchanges:**
- *"What is the difference between supervised and unsupervised learning?"*
- *"How does attention work in transformer models?"*
- *"What is the capital of New Zealand?"*

---

### 2. Voice Document Summariser (`scenarios/scenario_summarize.py`)
Dictate a document aloud or pass a text file. Nemotron produces a spoken 2–4 sentence summary — demonstrating its long-context processing capability.

```bash
# Dictation mode (speak, then say "summarise")
python scenarios/scenario_summarize.py

# File mode
python scenarios/scenario_summarize.py --file path/to/document.txt

# Text-only (paste text, type "summarise")
python scenarios/scenario_summarize.py --text-only
```

**Example use cases:**
- Summarise meeting notes before a call
- Get a spoken overview of a research paper abstract
- Summarise a changelog before reviewing a PR

---

### 3. Voice Coding Assistant (`scenarios/scenario_code.py`)
Describe a coding task or question verbally. Nemotron gives a spoken explanation plus a code snippet displayed with syntax highlighting in the terminal.

```bash
python scenarios/scenario_code.py
python scenarios/scenario_code.py --language TypeScript
python scenarios/scenario_code.py --text-only
```

**Example requests:**
- *"Write a Python function that reads a CSV file and returns it as a list of dictionaries"*
- *"Explain what a decorator does in Python"*
- *"Show me how to handle errors in an async function"*

---

## Configuration

Copy `.env.example` to `.env` and edit as needed. All settings have sensible defaults.

| Variable | Default | Description |
|---|---|---|
| `NEMOTRON_MODEL` | `nemotron-nano` | Foundry Local model alias for Nemotron |
| `WHISPER_MODEL` | `whisper-base` | Foundry Local model alias for Whisper |
| `MAX_TOKENS` | `256` | Maximum tokens in Nemotron's response |
| `TEMPERATURE` | `0.7` | Sampling temperature (0.0 = deterministic) |
| `STREAM_RESPONSE` | `true` | Stream tokens to terminal as they arrive |
| `TTS_ENGINE` | `pyttsx3` | `pyttsx3` (offline) or `edge-tts` (online, neural) |
| `TTS_RATE` | `175` | Speech rate in words per minute |
| `SILENCE_THRESHOLD` | `0.01` | RMS energy below which audio is treated as silence |
| `SILENCE_DURATION` | `1.5` | Seconds of silence before auto-stop |
| `HISTORY_LIMIT` | `10` | Max conversation turns kept in context |
| `DEBUG` | `false` | Enable verbose logging |

### Listing Available Models

```bash
python src/utils.py --list-models
```

### Listing Microphone Devices

```bash
python src/utils.py --list-mics
```

Set `DEVICE_INDEX` in `.env` to use a specific microphone.

---

## Project Structure

```
fl-nemotron/
├── src/
│   ├── voice_assistant.py      # Main orchestration loop
│   ├── foundry_client.py       # Foundry Local SDK wrapper (Nemotron + Whisper)
│   ├── speech_handler.py       # Microphone capture, VAD, TTS
│   ├── config.py               # All configuration (dataclasses + dotenv)
│   └── utils.py                # Model listing, audio validation helpers
├── scenarios/
│   ├── scenario_qa.py          # Voice Q&A assistant
│   ├── scenario_summarize.py   # Voice document summariser
│   └── scenario_code.py        # Voice coding assistant
├── audio_samples/              # Temporary WAV files (auto-cleaned)
├── blog/                       # Local blog artifacts (gitignored)
├── requirements.txt
├── .env.example
├── .gitignore
├── setup.ps1                   # Windows one-command setup
└── setup.sh                    # macOS / Linux one-command setup
```

---

## Why Nemotron + Foundry Local?

| Consideration | Nemotron + Foundry Local | Managed cloud LLM |
|---|---|---|
| Data residency | ✅ Data never leaves device | ❌ Data sent to cloud endpoint |
| Network required | ❌ Works fully offline | ✅ Always required |
| Per-token cost | ✅ Zero | ❌ Pay-per-use |
| Model control | ✅ Open weights, customisable | ❌ Proprietary, managed |
| Voice / multimodal | ⚠️ Separate Whisper model | ✅ Native in some APIs |
| Setup complexity | Medium | Low |

Nemotron is particularly well-suited to this scenario because it is open-weight, designed for enterprise deployment across cloud/hybrid/edge, and optimised for long-running agentic workflows — exactly the profile you need for a locally-hosted voice assistant.

---

## Troubleshooting

**`No module named 'foundry_local_sdk'`**
Install the SDK: `pip install foundry-local-sdk` (or `foundry-local-sdk-winml` on Windows).

**`Model 'nemotron-nano' not found in catalog`**
Run `foundry model ls` to see available models. Update `NEMOTRON_MODEL` in `.env` to match an available alias.

**No microphone audio / silent recordings**
Run `python src/utils.py --list-mics` to list devices. Set `DEVICE_INDEX` in `.env` to the correct device number.

**`pyttsx3` no audio on Linux**
Install espeak: `sudo apt-get install espeak espeak-data`.

**Slow first response**
Models load on first use. Subsequent responses within the same session are much faster as the model stays loaded in memory.

---

## Testing

Run the lightweight test suite locally:

```bash
python -m pytest -q
```

Continuous checks run in GitHub Actions:
- CI workflow: unit tests on Python 3.11 and 3.12
- Security workflow: Gitleaks secret scan and pip-audit dependency scan
- Dependabot: weekly dependency update PRs for pip and GitHub Actions

---

## Learn More

- [Microsoft Foundry Local documentation](https://learn.microsoft.com/en-us/azure/foundry-local/)
- [Foundry Local GitHub repository](https://github.com/microsoft/Foundry-Local)
- [Foundry Local Python samples](https://github.com/microsoft/Foundry-Local/tree/main/samples/python)
- [NVIDIA Nemotron developer hub](https://developer.nvidia.com/nemotron)
- [Foundry Local on PyPI](https://pypi.org/project/foundry-local-sdk/)

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
Please also review [CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md).

Issue and PR templates are included under `.github/` to help submit high-quality reports and changes.

---

## Security

If you discover a security issue, please follow the private reporting guidance in [SECURITY.md](SECURITY.md).

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
