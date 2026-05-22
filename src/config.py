"""
config.py — Application configuration for the Foundry Local Nemotron Voice Assistant.

All tuneable parameters live here. Override via environment variables or .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AudioConfig:
    """Microphone capture and audio processing settings."""
    sample_rate: int = 16_000          # Hz — Whisper expects 16 kHz
    channels: int = 1                  # Mono
    record_seconds: float = 5.0        # Max recording window per utterance
    silence_threshold: float = 0.01    # RMS below this = silence
    silence_duration: float = 1.5      # Seconds of silence before auto-stop
    device_index: int | None = None    # None = system default microphone
    temp_dir: str = field(default_factory=lambda: os.getenv("AUDIO_TEMP_DIR", "audio_samples"))


@dataclass
class WhisperConfig:
    """Foundry Local Whisper model settings."""
    model_alias: str = field(
        default_factory=lambda: os.getenv("WHISPER_MODEL", "whisper-base")
    )
    language: str = field(
        default_factory=lambda: os.getenv("WHISPER_LANGUAGE", "en")
    )


@dataclass
class NemotronConfig:
    """Foundry Local Nemotron (LLM) model settings."""
    model_alias: str = field(
        default_factory=lambda: os.getenv("NEMOTRON_MODEL", "qwen2.5-0.5b")
    )
    system_prompt: str = field(
        default_factory=lambda: os.getenv(
            "SYSTEM_PROMPT",
            (
                "You are a concise, helpful voice assistant. "
                "Your answers are spoken aloud, so keep them under 3 sentences unless the user "
                "explicitly asks for more detail. Be direct and conversational."
            ),
        )
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS", "256"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE", "0.7"))
    )
    stream: bool = field(
        default_factory=lambda: os.getenv("STREAM_RESPONSE", "true").lower() == "true"
    )


@dataclass
class TTSConfig:
    """Text-to-speech output settings."""
    engine: str = field(
        default_factory=lambda: os.getenv("TTS_ENGINE", "pyttsx3")  # pyttsx3 | edge-tts
    )
    rate: int = field(
        default_factory=lambda: int(os.getenv("TTS_RATE", "175"))   # words per minute
    )
    volume: float = field(
        default_factory=lambda: float(os.getenv("TTS_VOLUME", "0.9"))
    )
    voice_name: str | None = field(
        default_factory=lambda: os.getenv("TTS_VOICE")  # None = engine default
    )
    # edge-tts specific (requires network)
    edge_voice: str = field(
        default_factory=lambda: os.getenv("EDGE_TTS_VOICE", "en-US-AriaNeural")
    )


@dataclass
class AppConfig:
    """Top-level application configuration."""
    app_name: str = "foundry-nemotron-voice"
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    conversation_history_limit: int = field(
        default_factory=lambda: int(os.getenv("HISTORY_LIMIT", "10"))
    )
    wake_word: str | None = field(
        default_factory=lambda: os.getenv("WAKE_WORD")  # None = press-to-talk mode
    )

    audio: AudioConfig = field(default_factory=AudioConfig)
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    nemotron: NemotronConfig = field(default_factory=NemotronConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)


def load_config() -> AppConfig:
    """Return a fully populated AppConfig instance."""
    return AppConfig()
