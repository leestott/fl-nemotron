"""
scenario_summarize.py — Voice document summariser scenario.

The user speaks or pastes a block of text, and Nemotron produces
a spoken summary. Demonstrates Nemotron's long-context processing.

Run:
    python scenarios/scenario_summarize.py
    python scenarios/scenario_summarize.py --file path/to/document.txt
    python scenarios/scenario_summarize.py --text-only
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from foundry_client import FoundryClient
from speech_handler import MicrophoneRecorder, TextToSpeech

console = Console()

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a document summariser. "
    "When given text, produce a spoken summary of 2–4 sentences that captures "
    "the key points. The summary will be read aloud, so avoid lists or bullet points."
)

DICTATE_SYSTEM_PROMPT = (
    "You are a transcription assistant. "
    "The user will dictate text to you. Collect everything they say. "
    "When they say 'summarise' or 'done', produce a 2–4 sentence spoken summary "
    "of everything dictated. Avoid lists or bullet points."
)


def summarize_file(file_path: str, text_only: bool = False) -> None:
    """Summarise a text file and speak the result."""
    config = load_config()
    config.nemotron.max_tokens = 256
    config.nemotron.temperature = 0.4
    tts = TextToSpeech(config.tts)

    text = Path(file_path).read_text(encoding="utf-8")
    console.print(f"[bold]Summarising:[/bold] {file_path} ({len(text)} chars)")

    messages = [
        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
        {"role": "user",   "content": f"Please summarise this:\n\n{text}"},
    ]

    with FoundryClient(config) as foundry:
        summary = foundry.chat_completion(messages)
        console.print(f"\n[green]Summary:[/green] {summary}\n")
        tts.speak(summary)


def voice_dictate_and_summarize(text_only: bool = False) -> None:
    """
    Dictation mode: user speaks a document, then says 'summarise'.
    Nemotron accumulates the dictated text and produces a summary.
    """
    config = load_config()
    config.nemotron.max_tokens = 300
    config.nemotron.temperature = 0.4
    recorder = MicrophoneRecorder(config) if not text_only else None
    tts = TextToSpeech(config.tts)

    console.print("[bold magenta]Voice Document Summariser — Nemotron[/bold magenta]")
    console.print("[dim]Dictate your document. Say 'summarise' or 'done' when finished.[/dim]\n")

    dictated_chunks: list[str] = []

    with FoundryClient(config) as foundry:
        tts.speak("Dictation mode ready. Speak your document, then say summarise when done.")

        while True:
            try:
                if text_only:
                    chunk = input("Dictate (or 'summarise'): ").strip()
                else:
                    console.print("[dim]Listening …[/dim]")
                    wav = recorder.record_utterance()
                    chunk = foundry.transcribe(wav)
                    wav.unlink(missing_ok=True)

                if not chunk:
                    continue
                console.print(f"[dim]Heard:[/dim] {chunk}")

                if chunk.lower() in ("summarise", "summarize", "done", "finish", "exit"):
                    break

                dictated_chunks.append(chunk)

            except KeyboardInterrupt:
                break

        if not dictated_chunks:
            tts.speak("No content was dictated.")
            return

        full_text = " ".join(dictated_chunks)
        console.print(f"\n[dim]Full dictation ({len(full_text)} chars):[/dim]\n{full_text}\n")

        messages = [
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user",   "content": f"Summarise this dictated text:\n\n{full_text}"},
        ]

        console.print("[cyan]Generating summary …[/cyan]")
        summary = foundry.chat_completion(messages)
        console.print(f"[green]Summary:[/green] {summary}\n")
        tts.speak(summary)


if __name__ == "__main__":
    args = sys.argv[1:]
    text_only = "--text-only" in args
    file_idx = next((i for i, a in enumerate(args) if a == "--file"), None)

    if file_idx is not None and file_idx + 1 < len(args):
        summarize_file(args[file_idx + 1], text_only)
    else:
        voice_dictate_and_summarize(text_only)
