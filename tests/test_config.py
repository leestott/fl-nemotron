from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from config import load_config


def test_load_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("NEMOTRON_MODEL", raising=False)
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    cfg = load_config()

    assert cfg.app_name == "foundry-nemotron-voice"
    assert cfg.nemotron.model_alias
    assert cfg.whisper.model_alias
    assert cfg.nemotron.max_tokens > 0


def test_load_config_overrides(monkeypatch) -> None:
    monkeypatch.setenv("NEMOTRON_MODEL", "nemotron-nano")
    monkeypatch.setenv("WHISPER_MODEL", "whisper-small")
    monkeypatch.setenv("MAX_TOKENS", "321")
    monkeypatch.setenv("TEMPERATURE", "0.2")

    cfg = load_config()

    assert cfg.nemotron.model_alias == "nemotron-nano"
    assert cfg.whisper.model_alias == "whisper-small"
    assert cfg.nemotron.max_tokens == 321
    assert cfg.nemotron.temperature == 0.2
