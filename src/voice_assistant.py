"""
voice_assistant.py — Main orchestration loop for the Foundry Local Nemotron Voice Assistant.

Implements a press-to-talk or voice-activity-detection (VAD) conversation loop:

  1. Wait for the user (press ENTER or speak above threshold)
  2. Record speech via MicrophoneRecorder
  3. Transcribe audio → text via local Nemotron STT (FoundryClient)
  4. Send transcript to Nemotron with conversation history → get response
  5. Speak response via TextToSpeech
  6. Repeat

Run:
    python src/voice_assistant.py
    python src/voice_assistant.py --press-to-talk
    python src/voice_assistant.py --text-only    # keyboard input, no microphone
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

# Add src/ to path when running directly
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from foundry_client import FoundryClient
from speech_handler import MicrophoneRecorder, TextToSpeech

console = Console()

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress noisy third-party loggers
    for lib in ("httpx", "httpcore", "openai", "sounddevice"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ──────────────────────────────────────────────────────────────────────────────
# Conversation history
# ──────────────────────────────────────────────────────────────────────────────

class ConversationHistory:
    """Maintains a rolling window of chat messages."""

    def __init__(self, system_prompt: str, limit: int = 10) -> None:
        self._limit = limit
        self._messages: list[dict] = [
            {"role": "system", "content": system_prompt}
        ]

    def add_user(self, text: str) -> None:
        self._messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str) -> None:
        self._messages.append({"role": "assistant", "content": text})

    def _trim(self) -> None:
        """Keep system prompt + last N user/assistant pairs."""
        non_system = [m for m in self._messages if m["role"] != "system"]
        if len(non_system) > self._limit * 2:
            non_system = non_system[-(self._limit * 2):]
        self._messages = [self._messages[0]] + non_system

    def get(self) -> list[dict]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages = [self._messages[0]]
        console.print("[yellow]Conversation history cleared.[/yellow]")


# ──────────────────────────────────────────────────────────────────────────────
# Main assistant loop
# ──────────────────────────────────────────────────────────────────────────────

class VoiceAssistant:
    """Orchestrates the full voice interaction loop."""

    # Commands the user can say or type
    COMMANDS = {
        "exit":    ("exit", "quit", "bye", "goodbye"),
        "clear":   ("clear history", "reset", "start over", "new conversation"),
        "help":    ("help", "what can you do", "commands"),
    }

    def __init__(self, args: argparse.Namespace) -> None:
        self._args = args
        self._config = load_config()
        self._foundry = FoundryClient(self._config)
        self._recorder = MicrophoneRecorder(self._config) if not args.text_only else None
        self._tts = TextToSpeech(self._config.tts)
        self._history = ConversationHistory(
            system_prompt=self._config.nemotron.system_prompt,
            limit=self._config.conversation_history_limit,
        )

    def run(self) -> None:
        """Start the assistant. Runs until the user exits."""
        self._print_banner()

        console.print("[bold cyan]Starting Foundry Local …[/bold cyan]")
        with self._foundry:
            console.print(
                f"[green]✓ Nemotron ({self._config.nemotron.model_alias}) loaded[/green]"
            )
            console.print(
                f"[green]✓ Nemotron STT  ({self._config.stt.model_alias}) loaded[/green]"
            )
            console.print()
            self._tts.speak("Hello! I am your Nemotron voice assistant, running entirely on your device.")
            self._main_loop()

    def _main_loop(self) -> None:
        while True:
            try:
                user_text = self._get_input()
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Exiting.[/yellow]")
                self._tts.speak("Goodbye!")
                break

            if not user_text:
                continue

            # Check for control commands
            cmd = self._detect_command(user_text.lower())
            if cmd == "exit":
                self._tts.speak("Goodbye! Shutting down.")
                break
            elif cmd == "clear":
                self._history.clear()
                self._tts.speak("Conversation history cleared. What would you like to talk about?")
                continue
            elif cmd == "help":
                self._show_help()
                continue

            # Regular conversation turn
            self._history.add_user(user_text)
            console.print(f"\n[bold blue]You:[/bold blue] {user_text}")

            response = self._get_response()
            self._history.add_assistant(response)

            console.print(f"[bold green]Nemotron:[/bold green] {response}\n")
            self._tts.speak(response)

    def _get_input(self) -> str:
        """Get user input — microphone or keyboard depending on mode."""
        if self._args.text_only:
            return self._get_text_input()
        elif self._args.press_to_talk:
            return self._get_voice_press_to_talk()
        else:
            return self._get_voice_vad()

    def _get_text_input(self) -> str:
        try:
            return input("[bold]You (type):[/bold] ").strip()
        except EOFError:
            return "exit"

    def _get_voice_vad(self) -> str:
        console.print("[dim]Listening … (speak to start, silence to stop)[/dim]")
        wav_path = self._recorder.record_utterance(
            on_start=lambda: console.print("[cyan]🎤 Recording …[/cyan]"),
            on_stop=lambda:  console.print("[cyan]✓ Transcribing …[/cyan]"),
        )
        return self._transcribe(wav_path)

    def _get_voice_press_to_talk(self) -> str:
        wav_path = self._recorder.record_press_to_talk()
        console.print("[cyan]✓ Transcribing …[/cyan]")
        return self._transcribe(wav_path)

    def _transcribe(self, wav_path: Path) -> str:
        text = self._foundry.transcribe(wav_path)
        # Clean up temp file
        try:
            wav_path.unlink()
        except OSError:
            pass
        return text

    def _get_response(self) -> str:
        """Get a response from Nemotron, streaming tokens to the console."""
        cfg = self._config.nemotron
        if cfg.stream:
            tokens = []
            console.print("[bold green]Nemotron:[/bold green] ", end="")
            for token in self._foundry.stream_completion(self._history.get()):
                console.print(token, end="", highlight=False)
                tokens.append(token)
            console.print()
            # Remove duplicate print in main loop by returning the assembled text
            full = "".join(tokens)
            # Update history with the assembled response (already added below)
            return full
        else:
            return self._foundry.chat_completion(self._history.get())

    def _detect_command(self, text: str) -> str | None:
        for cmd, phrases in self.COMMANDS.items():
            if any(p in text for p in phrases):
                return cmd
        return None

    def _show_help(self) -> None:
        help_text = (
            "You can ask me anything. I'll answer using Nemotron running locally on your device.\n\n"
            "Special commands:\n"
            "  • 'clear history' / 'reset' — start a new conversation\n"
            "  • 'exit' / 'quit' / 'bye'   — shut down the assistant\n"
            "  • 'help'                     — show this message\n\n"
            "See scenarios/ for specialised modes: Q&A, code assistant, document summariser."
        )
        console.print(Panel(help_text, title="Help", border_style="blue"))
        self._tts.speak(
            "I can answer questions, help with code, or summarise documents. "
            "Just speak naturally. Say exit to quit."
        )

    @staticmethod
    def _print_banner() -> None:
        banner = Text()
        banner.append("  Foundry Local", style="bold magenta")
        banner.append(" · ", style="dim")
        banner.append("NVIDIA Nemotron", style="bold green")
        banner.append(" · ", style="dim")
        banner.append("Voice Assistant\n", style="bold white")
        banner.append("  On-device AI — no cloud, no API keys, no data leaving your device",
                       style="dim")
        console.print(Panel(banner, border_style="magenta"))


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Foundry Local Nemotron Voice Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/voice_assistant.py                   # VAD mode (auto-detect speech)
  python src/voice_assistant.py --press-to-talk   # Press ENTER to start/stop
  python src/voice_assistant.py --text-only       # Keyboard input, no microphone
  python src/voice_assistant.py --debug           # Verbose logging
        """,
    )
    parser.add_argument("--press-to-talk", action="store_true",
                        help="Press ENTER to start and stop recording")
    parser.add_argument("--text-only", action="store_true",
                        help="Use keyboard input instead of microphone")
    parser.add_argument("--debug", action="store_true",
                        help="Enable verbose debug logging")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    setup_logging(args.debug or os.getenv("DEBUG", "").lower() == "true")
    assistant = VoiceAssistant(args)
    assistant.run()
