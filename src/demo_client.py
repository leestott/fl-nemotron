"""
demo_client.py — Mock AI client for UI testing and demonstrations.

Provides realistic keyword-matched responses without requiring Foundry Local
to be running. Used automatically when the SDK is unavailable or the service
is not started.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator

# Keyword → response mapping (covers common demo questions)
_RESPONSES: dict[str, str] = {
    "nemotron": (
        "Nemotron is an open-weight large language model family from NVIDIA, designed for "
        "enterprise deployment across cloud, hybrid, and edge environments. "
        "It provides open weights and training recipes, making it suitable for regulated industries "
        "where proprietary hosted models cannot be used."
    ),
    "foundry local": (
        "Microsoft Foundry Local is an on-device AI runtime that manages the full lifecycle of "
        "AI models: download, caching, hardware acceleration selection (NPU/GPU/CPU via ONNX "
        "Runtime), and inference. It exposes an OpenAI-compatible API so existing code works "
        "without modification — just point it at localhost."
    ),
    "foundry": (
        "Microsoft Foundry Local runs AI models entirely on your device. "
        "It auto-selects NPU, GPU, or CPU execution via ONNX Runtime and caches models locally "
        "so subsequent launches are instant. The OpenAI-compatible API means you can switch "
        "between local and cloud inference with a single line change."
    ),
    "whisper": (
        "Whisper is OpenAI's automatic speech recognition model. "
        "In this application, Whisper runs locally via Foundry Local — "
        "your audio never leaves your device during transcription."
    ),
    "onnx": (
        "ONNX Runtime is a cross-platform, hardware-agnostic inference engine. "
        "It automatically selects the best execution provider available on your device: "
        "NPU (Copilot+ PCs), CUDA GPU, DirectML GPU, or CPU. "
        "Foundry Local uses ONNX Runtime under the hood for all model inference."
    ),
    "privacy": (
        "All processing in this application happens on your local device. "
        "Voice audio, transcripts, conversation history, and model outputs never leave your machine. "
        "There are no outbound API calls after the initial one-time model download."
    ),
    "install": (
        "On Windows: winget install Microsoft.FoundryLocal. "
        "On macOS: brew install microsoft/foundrylocal/foundrylocal. "
        "After installing, run: foundry model run nemotron-nano to download the model, "
        "then start this app with: uvicorn app:app --app-dir src --port 8000"
    ),
    "build": (
        "Microsoft Build 2026 is June 2–3 at Fort Mason Center, San Francisco, and online. "
        "The Microsoft Build CLI integrates with GitHub Copilot CLI to surface relevant Build "
        "sessions directly in your terminal — install it with /plugin install microsoft/Build-CLI."
    ),
    "hello": (
        "Hello! I'm Nemotron, running via Microsoft Foundry Local — entirely on your device. "
        "Ask me about Foundry Local, NVIDIA Nemotron, on-device AI, or anything else."
    ),
    "voice": (
        "This voice assistant captures microphone audio via sounddevice, transcribes it with "
        "Whisper locally, sends the transcript to Nemotron for reasoning, and speaks the response "
        "using pyttsx3 — all on-device, with zero cloud dependency after model download."
    ),
    "demo": (
        "Demo mode is active because Foundry Local is not running on this machine. "
        "Responses are simulated with keyword matching. For real AI inference, install "
        "Foundry Local and run: foundry model run nemotron-nano, then restart this app."
    ),
}

_DEFAULT_RESPONSE = (
    "I'm running in demo mode — Foundry Local is not currently active on this device. "
    "In production, this response would come from NVIDIA Nemotron running entirely locally "
    "via Microsoft Foundry Local, with no data leaving your machine. "
    "Try asking about: Nemotron, Foundry Local, Whisper, ONNX, privacy, or installation."
)

_DEMO_TRANSCRIPTIONS = [
    "What is Nemotron?",
    "How does Foundry Local handle hardware acceleration?",
    "Tell me about the privacy benefits of running AI locally.",
    "What is ONNX Runtime?",
    "How do I install Foundry Local?",
    "What is Microsoft Build 2026?",
]


class DemoClient:
    """
    Mock AI client that simulates Nemotron + Whisper responses.

    Used when Foundry Local SDK is not installed or the service is not running.
    Supports the same interface as FoundryClient for drop-in replacement.
    """

    def __init__(self) -> None:
        self._transcription_index = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Chat

    def chat_completion(self, messages: list[dict]) -> str:
        return self._find_response(messages)

    def stream_completion(self, messages: list[dict]) -> Iterator[str]:
        text = self._find_response(messages)
        words = text.split()
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            time.sleep(0.035)   # simulate token generation delay

    def _find_response(self, messages: list[dict]) -> str:
        last = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        lower = last.lower()
        for keyword, response in _RESPONSES.items():
            if keyword in lower:
                return response
        return _DEFAULT_RESPONSE

    # ─────────────────────────────────────────────────────────────────────────
    # Transcription

    def transcribe(self, audio_path: str | Path) -> str:
        """Return a rotating sample transcription (demo only)."""
        result = _DEMO_TRANSCRIPTIONS[self._transcription_index % len(_DEMO_TRANSCRIPTIONS)]
        self._transcription_index += 1
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Lifecycle (no-ops in demo mode)

    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def __enter__(self) -> "DemoClient":
        return self

    def __exit__(self, *_) -> None:
        pass
