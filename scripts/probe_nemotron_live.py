"""Probe whether Nemotron Speech Streaming works via the live audio session API.

This bypasses the file-based AudioClient.transcribe() path (which currently
fails because foundry-local-core does not register the `nemotron_speech`
multi-modal model type) and instead uses LiveAudioTranscriptionSession,
which calls a different native entry point.
"""
from __future__ import annotations

import sys
import time
import wave

from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore[import]


def main() -> int:
    alias = "nemotron-speech-streaming-en-0.6b"

    FoundryLocalManager.initialize(Configuration(app_name="fl-nemotron-probe"))
    mgr = FoundryLocalManager.instance
    model = mgr.catalog.get_model(alias)
    if model is None:
        print(f"FAIL: '{alias}' not in catalog")
        return 1

    print(f"Downloading {alias} …")
    model.download()
    print(f"Loading {alias} …")
    model.load()

    ac = model.get_audio_client()
    sess = ac.create_live_transcription_session()
    sess.settings.sample_rate = 16000
    sess.settings.channels = 1
    sess.settings.bits_per_sample = 16
    sess.settings.language = "en"

    # Pick a sample audio file — prefer a real one if user dropped one in, else 2s of silence
    sample = None
    for candidate in ("sample.wav", "scripts/sample.wav"):
        try:
            with wave.open(candidate, "rb") as w:
                if w.getframerate() == 16000 and w.getnchannels() == 1 and w.getsampwidth() == 2:
                    sample = w.readframes(w.getnframes())
                    print(f"Using audio: {candidate} ({len(sample)} bytes)")
                    break
        except (FileNotFoundError, wave.Error):
            continue
    if sample is None:
        sample = b"\x00\x00" * 16000 * 2  # 2s silence PCM16 mono 16k
        print(f"Using 2s silence ({len(sample)} bytes)")

    print("Starting session …")
    try:
        sess.start()
    except Exception as exc:
        print(f"FAIL on start(): {type(exc).__name__}: {exc}")
        return 2

    # Push audio in ~100ms chunks
    chunk = 3200  # 100ms @ 16k mono 16-bit
    try:
        for i in range(0, len(sample), chunk):
            sess.append(sample[i : i + chunk])
        print("All audio appended. Draining stream (up to 10s) …")

        deadline = time.time() + 10
        transcript_parts: list[str] = []
        for resp in sess.get_stream():
            for part in resp.content:
                text = getattr(part, "text", "") or getattr(part, "transcript", "") or ""
                if text:
                    transcript_parts.append(text)
                    print(f"  → {text!r}")
            if time.time() > deadline:
                print("  (deadline reached)")
                break

        print("Stopping session …")
        sess.stop()
        print("RESULT:", " ".join(transcript_parts) or "<empty>")
        print("SUCCESS — live transcription session works with Nemotron.")
        return 0
    except Exception as exc:
        print(f"FAIL during streaming: {type(exc).__name__}: {exc}")
        try:
            sess.stop()
        except Exception:
            pass
        return 3


if __name__ == "__main__":
    sys.exit(main())
