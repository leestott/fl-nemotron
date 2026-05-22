from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from demo_client import DemoClient


def test_keyword_response() -> None:
    client = DemoClient()
    text = client.chat_completion([
        {"role": "system", "content": "You are a helper."},
        {"role": "user", "content": "What is Foundry Local?"},
    ])
    assert "Foundry Local" in text


def test_stream_completion_reconstructs_text() -> None:
    client = DemoClient()
    messages = [{"role": "user", "content": "Tell me about privacy."}]
    full = client.chat_completion(messages)
    streamed = "".join(client.stream_completion(messages))
    assert streamed == full


def test_demo_transcribe_rotates() -> None:
    client = DemoClient()
    first = client.transcribe("dummy.wav")
    second = client.transcribe("dummy.wav")
    assert first
    assert second
    assert first != second
