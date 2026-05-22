"""
foundry_client.py — Foundry Local SDK wrapper.

Manages the lifecycle of:
  - FoundryLocalManager (singleton, initialised once)
  - Nemotron chat model
  - Whisper audio transcription model

Uses the OpenAI-compatible client exposed by Foundry Local for chat completions
so the same code can target the local endpoint or a cloud endpoint with a
one-line change.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Iterator

from openai import OpenAI

from config import AppConfig

logger = logging.getLogger(__name__)


class FoundryClient:
    """
    Wraps the Foundry Local SDK to expose:
      - chat_completion()   → text response from Nemotron
      - stream_completion() → streaming token generator from Nemotron
      - transcribe()        → speech-to-text via Whisper
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._manager: FoundryLocalManager | None = None
        self._chat_model = None
        self._audio_model = None
        self._openai_client: OpenAI | None = None

    # ──────────────────────────────────────────────────────────────────────────
    # Initialisation
    # ──────────────────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """Download and load both models. Call once at startup."""
        logger.info("Initialising Foundry Local runtime …")

        try:
            from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "foundry-local-sdk is not installed. "
                "Run: pip install foundry-local-sdk  (or foundry-local-sdk-winml on Windows)"
            ) from exc

        sdk_config = Configuration(app_name=self._config.app_name)
        FoundryLocalManager.initialize(sdk_config)
        self._manager = FoundryLocalManager.instance

        self._load_chat_model()
        self._load_audio_model()
        self._openai_client = self._build_openai_client()

        logger.info("Foundry Local ready. Chat: %s | STT: %s",
                    self._config.nemotron.model_alias,
                    self._config.whisper.model_alias)

    def _load_chat_model(self) -> None:
        alias = self._config.nemotron.model_alias
        logger.info("Loading chat model: %s", alias)
        try:
            self._chat_model = self._manager.catalog.get_model(alias)
            if self._chat_model is None:
                fallback_aliases = (
                    "phi-4-mini",
                    "qwen2.5-1.5b",
                    "qwen2.5-0.5b",
                    "mistral-nemo-12b-instruct",
                )
                for candidate in fallback_aliases:
                    self._chat_model = self._manager.catalog.get_model(candidate)
                    if self._chat_model is not None:
                        logger.warning(
                            "Model alias '%s' not found. Falling back to '%s'.",
                            alias,
                            candidate,
                        )
                        self._config.nemotron.model_alias = candidate
                        break

            if self._chat_model is None:
                available = [m.alias for m in self._manager.catalog.list_models()[:20]]
                raise RuntimeError(
                    f"No compatible chat model found. Requested '{alias}'. "
                    f"Sample available aliases: {available}"
                )

            self._chat_model.download()
            self._chat_model.load()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load chat model '{self._config.nemotron.model_alias}'.\n{exc}"
            ) from exc

    def _load_audio_model(self) -> None:
        alias = self._config.whisper.model_alias
        logger.info("Loading Whisper model: %s", alias)
        try:
            self._audio_model = self._manager.catalog.get_model(alias)
            if self._audio_model is None:
                fallback_aliases = ("whisper-base", "whisper-small")
                for candidate in fallback_aliases:
                    self._audio_model = self._manager.catalog.get_model(candidate)
                    if self._audio_model is not None:
                        logger.warning(
                            "Whisper alias '%s' not found. Falling back to '%s'.",
                            alias,
                            candidate,
                        )
                        self._config.whisper.model_alias = candidate
                        break

            if self._audio_model is None:
                available = [m.alias for m in self._manager.catalog.list_models() if "whisper" in m.alias.lower()]
                raise RuntimeError(
                    f"No compatible Whisper model found. Requested '{alias}'. "
                    f"Available aliases: {available}"
                )

            self._audio_model.download()
            self._audio_model.load()
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load Whisper model '{self._config.whisper.model_alias}'.\n{exc}"
            ) from exc

    def _build_openai_client(self) -> OpenAI:
        """
        Build an OpenAI-compatible client pointed at the Foundry Local endpoint.
        The local server runs at http://localhost:<port>/v1 and requires no real key.
        """
        # Start the Foundry Local HTTP service if not already running.
        # SDK API differs by version: service_url/start_service vs urls/start_web_service.
        service_url = None

        if hasattr(self._manager, "service_url"):
            service_url = getattr(self._manager, "service_url")
            if not service_url and hasattr(self._manager, "start_service"):
                self._manager.start_service()
                service_url = getattr(self._manager, "service_url")
        else:
            urls = getattr(self._manager, "urls", None)
            if not urls and hasattr(self._manager, "start_web_service"):
                self._manager.start_web_service()
                urls = getattr(self._manager, "urls", None)
            if isinstance(urls, list) and urls:
                service_url = urls[0]
            elif isinstance(urls, str):
                service_url = urls

        if not service_url:
            raise RuntimeError("Foundry Local web service URL is unavailable after SDK initialization")

        logger.info("Foundry Local service at %s", service_url)
        return OpenAI(
            base_url=f"{service_url}/v1",
            api_key="foundry-local",   # value is ignored by local server
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Chat completions
    # ──────────────────────────────────────────────────────────────────────────

    def chat_completion(self, messages: list[dict]) -> str:
        """
        Send a list of OpenAI-format messages to Nemotron and return the full
        response text.

        Args:
            messages: e.g. [{"role":"system","content":"..."}, {"role":"user","content":"..."}]

        Returns:
            The assistant's reply as a plain string.
        """
        cfg = self._config.nemotron
        response = self._openai_client.chat.completions.create(
            model=cfg.model_alias,
            messages=messages,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            stream=False,
        )
        return response.choices[0].message.content or ""

    def stream_completion(self, messages: list[dict]) -> Iterator[str]:
        """
        Stream token-by-token output from Nemotron.

        Yields:
            Individual token strings as they arrive from the model.
        """
        cfg = self._config.nemotron
        stream = self._openai_client.chat.completions.create(
            model=cfg.model_alias,
            messages=messages,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    # ──────────────────────────────────────────────────────────────────────────
    # Audio transcription (Whisper)
    # ──────────────────────────────────────────────────────────────────────────

    def transcribe(self, audio_path: str | Path) -> str:
        """
        Transcribe a WAV file using the local Whisper model.

        Args:
            audio_path: Path to a 16 kHz mono WAV file.

        Returns:
            Transcribed text, stripped of leading/trailing whitespace.
        """
        audio_path = str(audio_path)
        logger.debug("Transcribing: %s", audio_path)

        # Use the native SDK audio client
        audio_client = self._audio_model.get_audio_client()
        audio_client.settings.language = self._config.whisper.language
        result = audio_client.transcribe(audio_path)
        return (result.text or "").strip()

    def transcribe_openai_compat(self, audio_path: str | Path) -> str:
        """
        Alternative: transcribe using the OpenAI-compatible REST endpoint.
        Useful when testing against different client libraries.
        """
        with open(audio_path, "rb") as f:
            result = self._openai_client.audio.transcriptions.create(
                model=self._config.whisper.model_alias,
                file=f,
                response_format="text",
            )
        return (result or "").strip()

    # ──────────────────────────────────────────────────────────────────────────
    # Cleanup
    # ──────────────────────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Unload models and release resources."""
        logger.info("Shutting down Foundry Local …")
        if self._chat_model:
            try:
                self._chat_model.unload()
            except Exception:
                pass
        if self._audio_model:
            try:
                self._audio_model.unload()
            except Exception:
                pass

    def __enter__(self) -> "FoundryClient":
        self.initialize()
        return self

    def __exit__(self, *_) -> None:
        self.shutdown()
