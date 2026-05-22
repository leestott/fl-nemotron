# Foundry Local Nemotron Voice Assistant — Windows setup script
# Run from the project root: .\setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  Foundry Local Nemotron Voice Assistant Setup   " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python version check ───────────────────────────────────────────────────
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found. Install Python 3.11+ from https://python.org"
    exit 1
}
Write-Host "[OK] $pythonVersion" -ForegroundColor Green

$versionParts = ($pythonVersion -replace "Python ","").Split(".")
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 11)) {
    Write-Error "Python 3.11+ required. Found: $pythonVersion"
    exit 1
}

# ── 2. Create virtual environment ─────────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv) ..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[OK] .venv created" -ForegroundColor Green
} else {
    Write-Host "[OK] .venv already exists" -ForegroundColor Green
}

# ── 3. Activate venv ──────────────────────────────────────────────────────────
Write-Host "Activating virtual environment ..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"

# ── 4. Upgrade pip ────────────────────────────────────────────────────────────
Write-Host "Upgrading pip ..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet

# ── 5. Install dependencies ───────────────────────────────────────────────────
Write-Host "Installing dependencies (foundry-local-sdk >= 1.1.0 required) ..." -ForegroundColor Yellow
pip install --upgrade "foundry-local-sdk>=1.1.0,<2" --quiet
Write-Host "  [OK] foundry-local-sdk (>=1.1.0) installed" -ForegroundColor Green

pip install -r requirements.txt --quiet
Write-Host "[OK] Dependencies installed" -ForegroundColor Green

# ── 6. Pre-download models via the Foundry Local SDK ──────────────────────────
Write-Host ""
Write-Host "Pre-downloading AI models via the SDK (cached locally; one-time) ..." -ForegroundColor Yellow

$downloadModels = Read-Host "Download models now? (Y/n)"
if ($downloadModels -ne "n" -and $downloadModels -ne "N") {
    $chatAlias = if ($env:LLM_MODEL) { $env:LLM_MODEL } else { "qwen2.5-0.5b" }
    $sttAlias = if ($env:STT_MODEL) { $env:STT_MODEL } else { "nemotron-speech-streaming-en-0.6b" }

    Write-Host "  Prefetching $sttAlias and $chatAlias via SDK ..." -ForegroundColor Cyan
    python scripts\prefetch.py $sttAlias $chatAlias
}

# ── 8. Create .env from template ──────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env created from .env.example" -ForegroundColor Green
} else {
    Write-Host "[OK] .env already exists" -ForegroundColor Green
}

# ── 9. Create audio_samples directory ─────────────────────────────────────────
New-Item -ItemType Directory -Path "audio_samples" -Force | Out-Null
Write-Host "[OK] audio_samples/ directory ready" -ForegroundColor Green

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To start the voice assistant:" -ForegroundColor White
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "  python src\voice_assistant.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "Other modes:" -ForegroundColor White
Write-Host "  python src\voice_assistant.py --press-to-talk" -ForegroundColor DarkCyan
Write-Host "  python src\voice_assistant.py --text-only" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "Scenarios:" -ForegroundColor White
Write-Host "  python scenarios\scenario_qa.py" -ForegroundColor DarkCyan
Write-Host "  python scenarios\scenario_summarize.py" -ForegroundColor DarkCyan
Write-Host "  python scenarios\scenario_code.py" -ForegroundColor DarkCyan
Write-Host ""
