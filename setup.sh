#!/usr/bin/env bash
# Foundry Local Nemotron Voice Assistant — Linux / macOS setup script
# Run from the project root: bash setup.sh

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}  Foundry Local Nemotron Voice Assistant Setup   ${NC}"
echo -e "${CYAN}=================================================${NC}"
echo ""

# ── 1. Python version check ───────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR: python3 not found. Install Python 3.11+ and retry.${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
    echo -e "${RED}ERROR: Python 3.11+ required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] Python $PYTHON_VERSION${NC}"

# ── 2. System audio libraries (Linux only) ───────────────────────────────────
if [[ "$(uname -s)" == "Linux" ]]; then
    echo -e "${YELLOW}Installing system audio libraries (requires sudo) ...${NC}"
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y portaudio19-dev python3-pyaudio espeak espeak-data libespeak1 &>/dev/null
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y portaudio-devel espeak &>/dev/null
    elif command -v pacman &>/dev/null; then
        sudo pacman -S --noconfirm portaudio espeak-ng &>/dev/null
    fi
    echo -e "${GREEN}[OK] Audio libraries ready${NC}"
fi

# ── 3. Create virtual environment ─────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment (.venv) ...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}[OK] .venv created${NC}"
else
    echo -e "${GREEN}[OK] .venv already exists${NC}"
fi

# ── 4. Activate and upgrade pip ───────────────────────────────────────────────
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip --quiet

# ── 5. Install Python dependencies ────────────────────────────────────────────
echo -e "${YELLOW}Installing Python dependencies (foundry-local-sdk >= 1.1.0 required) ...${NC}"
pip install --upgrade 'foundry-local-sdk>=1.1.0,<2' --quiet
pip install -r requirements.txt --quiet
echo -e "${GREEN}[OK] Python dependencies installed${NC}"

# ── 6. Pre-download models via the Foundry Local SDK ──────────────────────────
echo ""
echo -e "${YELLOW}Pre-downloading AI models via the SDK (cached locally; one-time) ...${NC}"
echo ""
read -r -p "Download models now? (Y/n): " DOWNLOAD_MODELS
if [[ "$DOWNLOAD_MODELS" != "n" && "$DOWNLOAD_MODELS" != "N" ]]; then
    CHAT_ALIAS="${LLM_MODEL:-qwen2.5-0.5b}"
    STT_ALIAS="${STT_MODEL:-nemotron-speech-streaming-en-0.6b}"

    echo -e "${CYAN}  Prefetching ${STT_ALIAS} and ${CHAT_ALIAS} via SDK ...${NC}"
    python scripts/prefetch.py "${STT_ALIAS}" "${CHAT_ALIAS}"
fi

# ── 8. Create .env from template ──────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}[OK] .env created from .env.example${NC}"
else
    echo -e "${GREEN}[OK] .env already exists${NC}"
fi

# ── 9. Create audio_samples directory ─────────────────────────────────────────
mkdir -p audio_samples
echo -e "${GREEN}[OK] audio_samples/ directory ready${NC}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo "To start the voice assistant:"
echo -e "  ${CYAN}source .venv/bin/activate${NC}"
echo -e "  ${CYAN}python src/voice_assistant.py${NC}"
echo ""
echo "Other modes:"
echo -e "  ${CYAN}python src/voice_assistant.py --press-to-talk${NC}"
echo -e "  ${CYAN}python src/voice_assistant.py --text-only${NC}"
echo ""
echo "Scenarios:"
echo -e "  ${CYAN}python scenarios/scenario_qa.py${NC}"
echo -e "  ${CYAN}python scenarios/scenario_summarize.py${NC}"
echo -e "  ${CYAN}python scenarios/scenario_code.py${NC}"
echo ""
