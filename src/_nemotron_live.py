"""Internal helper: transcribe a WAV file with Nemotron Speech Streaming via
the LiveAudioTranscriptionSession API.

This bypasses AudioClient.transcribe() which currently fails on Nemotron
because foundry-local-core does not register the `nemotron_speech` multi-modal
model type. The live-streaming API uses a different native entry point
(core_interop.start_audio_stream) which the streaming model supports.
"""
from __future__ import annotations

import threading
import wave
from pathlib import Path
from typing import Any


def transcribe_wav_live(
    audio_client: Any,
    wav_path: str | Path,
    *,
    language: str | None = "en",
    drain_timeout_s: float = 30.0,
) -> str:
    """Read a 16-bit mono WAV and transcribe it via a live session.

    Returns the joined transcript text (empty string if the audio is silent
    or contains no recognizable speech). Raises whatever the SDK raises if
    the session itself fails to start.
    """
    with wave.open(str(wav_path), "rb") as w:
        sample_rate = w.getframerate()
        channels = w.getnchannels()
        sample_width = w.getsampwidth()
        pcm = w.readframes(w.getnframes())

    session = audio_client.create_live_transcription_session()
    session.settings.sample_rate = sample_rate
    session.settings.channels = channels
    session.settings.bits_per_sample = sample_width * 8
    if language:
        session.settings.language = language

    session.start()

    # Push PCM in ~100 ms chunks from a worker thread, then stop the session
    # so the stream generator terminates.
    bytes_per_sec = sample_rate * channels * sample_width
    chunk_bytes = max(bytes_per_sec // 10, 1024)

    push_error: dict[str, BaseException] = {}

    def _pusher() -> None:
        try:
            for offset in range(0, len(pcm), chunk_bytes):
                session.append(pcm[offset : offset + chunk_bytes])
        except BaseException as exc:  # noqa: BLE001
            push_error["err"] = exc
        finally:
            try:
                session.stop()
            except Exception:  # noqa: BLE001
                pass

    pusher = threading.Thread(target=_pusher, daemon=True)
    pusher.start()

    parts: list[str] = []
    try:
        for resp in session.get_stream():
            for cp in getattr(resp, "content", []) or []:
                text = getattr(cp, "text", "") or getattr(cp, "transcript", "") or ""
                if text:
                    parts.append(text)
    finally:
        pusher.join(timeout=drain_timeout_s)

    if "err" in push_error:
        raise push_error["err"]
    return " ".join(p.strip() for p in parts if p.strip()).strip()
