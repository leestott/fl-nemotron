"""
scenario_qa.py — Voice Q&A scenario.

A focused question-and-answer assistant optimised for factual queries.
Nemotron answers in 1–2 sentences for voice delivery.

Run:
    python scenarios/scenario_qa.py
    python scenarios/scenario_qa.py --text-only
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config, NemotronConfig
from foundry_client import FoundryClient
from speech_handler import MicrophoneRecorder, TextToSpeech

console = Console()

QA_SYSTEM_PROMPT = (
    "You are a concise voice Q&A assistant powered by Nemotron, running locally. "
    "Answer every question in exactly 1–2 sentences. "
    "If you don't know, say so clearly in one sentence. "
    "Do not add caveats, disclaimers, or preamble."
)


def run_qa(text_only: bool = False) -> None:
    config = load_config()
    config.nemotron.system_prompt = QA_SYSTEM_PROMPT
    config.nemotron.max_tokens = 128
    config.nemotron.temperature = 0.3   # lower temperature = more factual

    recorder = MicrophoneRecorder(config) if not text_only else None
    tts = TextToSpeech(config.tts)

    console.print("[bold magenta]Voice Q&A — Nemotron (Foundry Local)[/bold magenta]")
    console.print("[dim]Ask any factual question. Say 'exit' to quit.[/dim]\n")

    with FoundryClient(config) as foundry:
        tts.speak("Voice Q and A ready. Ask me anything.")
        history = [{"role": "system", "content": QA_SYSTEM_PROMPT}]

        while True:
            try:
                if text_only:
                    user_input = input("Question: ").strip()
                else:
                    console.print("[dim]Listening …[/dim]")
                    wav = recorder.record_utterance()
                    user_input = foundry.transcribe(wav)
                    wav.unlink(missing_ok=True)

                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    tts.speak("Goodbye!")
                    break

                console.print(f"[blue]Q:[/blue] {user_input}")
                history.append({"role": "user", "content": user_input})

                answer = foundry.chat_completion(history)
                history.append({"role": "assistant", "content": answer})

                console.print(f"[green]A:[/green] {answer}\n")
                tts.speak(answer)

            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    run_qa(text_only="--text-only" in sys.argv)
