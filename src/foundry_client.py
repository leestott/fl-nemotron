"""
foundry_client.py — Foundry Local SDK 1.1.x wrapper.

Uses the official Foundry Local Python SDK (`foundry-local-sdk` >= 1.1.0) to
manage the runtime, download/load models, and expose chat + transcription
clients directly via per-model OpenAI-compatible clients.

Requires foundry-local-sdk >= 1.1.0 (module name: `foundry_local_sdk`). Earlier
0.5.x releases used a different module name and a different API surface; they
are not supported by this client.

No CLI invocations: all model lifecycle calls go through the SDK.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from config import AppConfig

logger = logging.getLogger(__name__)


class NemotronSTTUnsupportedError(RuntimeError):
    """Raised when the local foundry-local-core runtime cannot transcribe with
    the Nemotron Speech Streaming model (missing `nemotron_speech` multi-modal
    model type registration in the bundled ONNX Runtime GenAI)."""


# Ordered fallback chains used when the requested alias is not in the local
# catalog (catalog content varies by hardware / SDK version).
_CHAT_FALLBACKS = (
    "qwen2.5-0.5b",
    "qwen2.5-1.5b",
    "phi-4-mini",
    "mistral-nemo-12b-instruct",
)
# STT is Nemotron-only by design (Nemotron Speech Streaming).
_STT_FALLBACKS = (
    "nemotron-speech-streaming-en-0.6b",
)


class FoundryClient:
    """
    Wraps the Foundry Local SDK 1.1.x to expose:
      - chat_completion()   → text response from the chat model
      - stream_completion() → streaming token generator
      - transcribe()        → speech-to-text via NVIDIA Nemotron Speech Streaming
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._manager = None
        self._chat_model = None
        self._stt_model = None
        self._chat_client = None
        self._audio_client = None

    # ──────────────────────────────────────────────────────────────────────
    # Initialisation
    # ──────────────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Start the Foundry Local service and download/load both models."""
        try:
            from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "foundry-local-sdk >= 1.1.0 is not installed. "
                "Run: pip install 'foundry-local-sdk>=1.1.0'"
            ) from exc

        logger.info("Starting Foundry Local service via SDK 1.1.x …")
        FoundryLocalManager.initialize(Configuration(app_name=self._config.app_name))
        self._manager = FoundryLocalManager.instance

        chat_alias = self._resolve_alias(
            self._config.nemotron.model_alias, _CHAT_FALLBACKS, "chat"
        )
        self._config.nemotron.model_alias = chat_alias
        self._chat_model = self._manager.catalog.get_model(chat_alias)

        stt_alias = self._resolve_alias(
            self._config.stt.model_alias, _STT_FALLBACKS, "speech-to-text"
        )
        self._config.stt.model_alias = stt_alias
        self._stt_model = self._manager.catalog.get_model(stt_alias)

        for label, model in (("chat", self._chat_model), ("STT", self._stt_model)):
            if not model.is_cached:
                logger.info("Downloading %s model: %s", label, model.alias)
                model.download()
            if not model.is_loaded:
                logger.info("Loading %s model: %s", label, model.alias)
                model.load()

        self._chat_client = self._chat_model.get_chat_client()
        self._audio_client = self._stt_model.get_audio_client()

        logger.info(
            "Foundry Local ready. Chat: %s | STT: %s",
            self._chat_model.alias, self._stt_model.alias,
        )

    def _resolve_alias(self, requested: str, fallbacks: tuple[str, ...], kind: str) -> str:
        """Return the requested alias if available, else the first matching fallback."""
        if self._manager.catalog.get_model(requested) is not None:
            return requested

        for candidate in fallbacks:
            if candidate == requested:
                continue
            if self._manager.catalog.get_model(candidate) is not None:
                logger.warning(
                    "%s alias '%s' not in catalog. Falling back to '%s'.",
                    kind.capitalize(), requested, candidate,
                )
                return candidate

        available = sorted({m.alias for m in self._manager.catalog.list_models()})
        raise RuntimeError(
            f"No compatible {kind} model found. Requested '{requested}'. "
            f"Available aliases: {available}"
        )

    # ──────────────────────────────────────────────────────────────────────
    # Chat completions
    # ──────────────────────────────────────────────────────────────────────

    def chat_completion(self, messages: list[dict]) -> str:
        response = self._chat_client.complete_chat(messages=messages)
        return response.choices[0].message.content or ""

    def stream_completion(self, messages: list[dict]) -> Iterator[str]:
        for chunk in self._chat_client.complete_streaming_chat(messages=messages):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # ──────────────────────────────────────────────────────────────────────
    # Audio transcription
    # ──────────────────────────────────────────────────────────────────────

    def transcribe(self, audio_path: str | Path) -> str:
        """Transcribe a WAV file via the Nemotron Speech Streaming model.

        Uses the live audio session API (`create_live_transcription_session`)
        rather than the file-based `AudioClient.transcribe`. The streaming
        model is built for the live API; the file-based path currently fails
        because foundry-local-core does not register `nemotron_speech` as a
        multi-modal model type.
        """
        from _nemotron_live import transcribe_wav_live

        try:
            return transcribe_wav_live(
                self._audio_client,
                audio_path,
                language=self._config.stt.language or "en",
            )
        except Exception as exc:
            msg = str(exc)
            if "nemotron_speech is not a registered multi-modal model type" in msg \
                    or "MultiModalProcessor cannot be created" in msg:
                raise NemotronSTTUnsupportedError(
                    "The installed foundry-local-core runtime does not yet "
                    "support the 'nemotron_speech' multi-modal model type. "
                    "Upgrade foundry-local-core when a build with "
                    "nemotron_speech support is released."
                ) from exc
            raise

    # ──────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        if not self._manager:
            return
        logger.info("Unloading Foundry Local models …")
        for model in (self._chat_model, self._stt_model):
            if model is None:
                continue
            try:
                if model.is_loaded:
                    model.unload()
            except Exception:
                pass

    def __enter__(self) -> "FoundryClient":
        self.initialize()
        return self

    def __exit__(self, *_) -> None:
        self.shutdown()
