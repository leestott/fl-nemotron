"""
utils.py — Shared helpers: logging setup, audio validation, model listing.
"""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def validate_wav(path: str | Path) -> bool:
    """Return True if the file is a readable WAV file."""
    try:
        with wave.open(str(path), "rb") as wf:
            return wf.getnframes() > 0
    except Exception:
        return False


def rms_of_wav(path: str | Path) -> float:
    """Return the RMS energy of a WAV file (0.0–1.0 float32 scale)."""
    from scipy.io import wavfile
    rate, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(data ** 2)))


def list_available_models() -> None:
    """Print all models available in the local Foundry catalog."""
    from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore
    config = Configuration(app_name="model-lister")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance
    print("\nAvailable models in Foundry Local catalog:")
    print("─" * 60)
    for model in manager.catalog.list_models():
        print(f"  {model.alias:<35}  {model.description or ''}")
    print()


def list_microphones() -> None:
    """Print all available microphone devices."""
    import sounddevice as sd
    print("\nAvailable audio input devices:")
    print("─" * 60)
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            print(f"  [{i:2d}]  {device['name']}")
    print()


if __name__ == "__main__":
    import sys
    if "--list-models" in sys.argv:
        list_available_models()
    if "--list-mics" in sys.argv:
        list_microphones()
