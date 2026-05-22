"""
speech_handler.py — Microphone capture, voice activity detection, and TTS output.

Handles:
  - Recording audio from the microphone (sounddevice)
  - Voice activity detection (silence-based auto-stop)
  - Writing captured audio to a temp WAV file for Whisper
  - Text-to-speech output via pyttsx3 (offline) or edge-tts (online, richer voices)
"""

from __future__ import annotations

import io
import logging
import queue
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
from scipy.io import wavfile

from config import AppConfig, TTSConfig

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Microphone Recording
# ──────────────────────────────────────────────────────────────────────────────

class MicrophoneRecorder:
    """
    Records audio from the system microphone with voice-activity-based auto-stop.

    Usage:
        recorder = MicrophoneRecorder(config)
        wav_path = recorder.record_utterance()   # blocks until speech ends
    """

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config.audio
        self._temp_dir = Path(config.audio.temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    def record_utterance(
        self,
        on_start: Callable | None = None,
        on_stop: Callable | None = None,
    ) -> Path:
        """
        Record one utterance from the microphone.

        Starts recording when sound is detected above the silence threshold,
        then stops after a configured period of silence.

        Args:
            on_start: Optional callback invoked when speech starts.
            on_stop:  Optional callback invoked when recording ends.

        Returns:
            Path to the saved 16 kHz mono WAV file.
        """
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        recording: list[np.ndarray] = []
        speech_started = False
        silence_start: float | None = None

        def audio_callback(indata: np.ndarray, frames: int, time_info, status):
            nonlocal speech_started, silence_start
            if status:
                logger.warning("Audio status: %s", status)
            chunk = indata.copy()
            audio_queue.put(chunk)

        logger.debug("Opening microphone stream (device=%s)", self._cfg.device_index)
        with sd.InputStream(
            samplerate=self._cfg.sample_rate,
            channels=self._cfg.channels,
            dtype="float32",
            device=self._cfg.device_index,
            callback=audio_callback,
            blocksize=int(self._cfg.sample_rate * 0.05),   # 50 ms blocks
        ):
            deadline = time.monotonic() + self._cfg.record_seconds
            while time.monotonic() < deadline:
                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                rms = float(np.sqrt(np.mean(chunk ** 2)))

                if rms >= self._cfg.silence_threshold:
                    if not speech_started:
                        speech_started = True
                        silence_start = None
                        logger.debug("Speech detected (rms=%.4f)", rms)
                        if on_start:
                            on_start()
                    else:
                        silence_start = None
                    recording.append(chunk)
                else:
                    if speech_started:
                        if silence_start is None:
                            silence_start = time.monotonic()
                        elif time.monotonic() - silence_start >= self._cfg.silence_duration:
                            logger.debug("Silence detected — stopping")
                            break
                        recording.append(chunk)

        if on_stop:
            on_stop()

        if not recording:
            logger.warning("No speech detected in recording window")
            # Return a near-silent file so Whisper can return an empty string
            silent = np.zeros(
                (int(self._cfg.sample_rate * 0.5), self._cfg.channels), dtype="float32"
            )
            recording = [silent]

        audio_data = np.concatenate(recording, axis=0)
        return self._save_wav(audio_data)

    def record_press_to_talk(self) -> Path:
        """
        Record until the user presses ENTER. Useful for testing or
        in environments where voice-activity detection is unreliable.
        """
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        stop_event = threading.Event()
        recording: list[np.ndarray] = []

        def audio_callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())

        def drain_queue():
            while not stop_event.is_set() or not audio_queue.empty():
                try:
                    recording.append(audio_queue.get(timeout=0.05))
                except queue.Empty:
                    pass

        with sd.InputStream(
            samplerate=self._cfg.sample_rate,
            channels=self._cfg.channels,
            dtype="float32",
            device=self._cfg.device_index,
            callback=audio_callback,
        ):
            drain_thread = threading.Thread(target=drain_queue, daemon=True)
            drain_thread.start()
            input("  🎤  Recording … press ENTER to stop\n")
            stop_event.set()
            drain_thread.join()

        audio_data = np.concatenate(recording, axis=0) if recording else np.zeros(
            (self._cfg.sample_rate,), dtype="float32"
        )
        return self._save_wav(audio_data)

    def _save_wav(self, audio: np.ndarray) -> Path:
        """Convert float32 audio to int16 WAV and save to the temp directory."""
        if audio.ndim > 1 and audio.shape[1] == 1:
            audio = audio.flatten()
        int16_audio = (audio * 32767).astype(np.int16)
        output_path = self._temp_dir / f"utterance_{int(time.time()*1000)}.wav"
        wavfile.write(str(output_path), self._cfg.sample_rate, int16_audio)
        logger.debug("Saved utterance: %s (%d samples)", output_path, len(int16_audio))
        return output_path


# ──────────────────────────────────────────────────────────────────────────────
# Text-to-Speech
# ──────────────────────────────────────────────────────────────────────────────

class TextToSpeech:
    """
    Speaks text aloud using the configured TTS engine.

    Supported engines:
      - 'pyttsx3'  — fully offline, cross-platform, no network required
      - 'edge-tts' — neural voices via Microsoft Edge TTS (requires network)
    """

    def __init__(self, config: TTSConfig) -> None:
        self._cfg = config
        self._engine = None
        self._init_engine()

    def _init_engine(self) -> None:
        if self._cfg.engine == "pyttsx3":
            self._init_pyttsx3()
        elif self._cfg.engine == "edge-tts":
            logger.info("TTS engine: edge-tts (neural, requires network)")
        else:
            raise ValueError(f"Unknown TTS engine: {self._cfg.engine!r}")

    def _init_pyttsx3(self) -> None:
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate",   self._cfg.rate)
            self._engine.setProperty("volume", self._cfg.volume)
            if self._cfg.voice_name:
                voices = self._engine.getProperty("voices")
                for v in voices:
                    if self._cfg.voice_name.lower() in v.name.lower():
                        self._engine.setProperty("voice", v.id)
                        logger.info("TTS voice set to: %s", v.name)
                        break
            logger.info("TTS engine: pyttsx3 (offline)")
        except ImportError as exc:
            raise ImportError(
                "pyttsx3 is not installed. Run: pip install pyttsx3"
            ) from exc

    def speak(self, text: str) -> None:
        """Speak the given text aloud. Blocks until speech completes."""
        if not text or not text.strip():
            return
        logger.debug("Speaking: %s", text[:80])
        if self._cfg.engine == "pyttsx3":
            self._speak_pyttsx3(text)
        elif self._cfg.engine == "edge-tts":
            self._speak_edge_tts(text)

    def _speak_pyttsx3(self, text: str) -> None:
        self._engine.say(text)
        self._engine.runAndWait()

    def _speak_edge_tts(self, text: str) -> None:
        """Speak using edge-tts (async, run in subprocess)."""
        import asyncio
        import edge_tts  # type: ignore[import]
        import subprocess, sys, tempfile, os

        async def _run():
            communicate = edge_tts.Communicate(text, self._cfg.edge_voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            await communicate.save(tmp_path)
            return tmp_path

        tmp = asyncio.run(_run())
        try:
            # Play the MP3 using the system default player
            if sys.platform == "win32":
                os.startfile(tmp)
                time.sleep(len(text) / 15)   # rough duration estimate
            else:
                subprocess.run(["afplay" if sys.platform == "darwin" else "mpg123", tmp],
                               capture_output=True)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def stop(self) -> None:
        """Stop any in-progress speech (pyttsx3 only)."""
        if self._cfg.engine == "pyttsx3" and self._engine:
            self._engine.stop()
