"""
scenario_code.py — Voice coding assistant scenario.

The user describes a coding task or question verbally. Nemotron
provides code explanations, short snippets, and debugging help
optimised for spoken delivery alongside terminal output.

Run:
    python scenarios/scenario_code.py
    python scenarios/scenario_code.py --text-only
    python scenarios/scenario_code.py --language python
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config
from foundry_client import FoundryClient
from speech_handler import MicrophoneRecorder, TextToSpeech

console = Console()

CODE_SYSTEM_PROMPT_TEMPLATE = (
    "You are a voice coding assistant. The user will describe coding questions "
    "or tasks verbally. You are working in {language}. "
    "Rules:\n"
    "1. Speak your explanation in 1–3 sentences — this is read aloud.\n"
    "2. After your spoken explanation, output any code in a fenced code block.\n"
    "3. Keep code snippets under 20 lines.\n"
    "4. If the user asks you to explain existing code, describe what it does in plain English.\n"
    "5. Never apologise or add disclaimers."
)


def extract_code_blocks(text: str) -> tuple[str, list[str]]:
    """
    Split a response into the spoken explanation (no code fences)
    and a list of code blocks.

    Returns:
        (spoken_text, [code_snippet, ...])
    """
    import re
    code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)
    spoken = re.sub(r"```.*?```", "", text, flags=re.DOTALL).strip()
    return spoken, code_blocks


def run_code_assistant(language: str = "Python", text_only: bool = False) -> None:
    config = load_config()
    config.nemotron.system_prompt = CODE_SYSTEM_PROMPT_TEMPLATE.format(language=language)
    config.nemotron.max_tokens = 512
    config.nemotron.temperature = 0.5
    config.nemotron.stream = False   # easier to parse code blocks from complete response

    recorder = MicrophoneRecorder(config) if not text_only else None
    tts = TextToSpeech(config.tts)

    console.print(f"[bold magenta]Voice Coding Assistant — Nemotron ({language})[/bold magenta]")
    console.print("[dim]Describe what you want to code. Say 'exit' to quit.[/dim]\n")

    history = [{"role": "system", "content": config.nemotron.system_prompt}]

    with FoundryClient(config) as foundry:
        tts.speak(f"Voice coding assistant ready. I'm set up for {language}. What would you like to build?")

        while True:
            try:
                if text_only:
                    user_input = input("You (code task): ").strip()
                else:
                    console.print("[dim]Describe your coding task …[/dim]")
                    wav = recorder.record_utterance()
                    user_input = foundry.transcribe(wav)
                    wav.unlink(missing_ok=True)

                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    tts.speak("Goodbye, happy coding!")
                    break

                console.print(f"\n[blue]You:[/blue] {user_input}")
                history.append({"role": "user", "content": user_input})

                response = foundry.chat_completion(history)
                history.append({"role": "assistant", "content": response})

                spoken, code_blocks = extract_code_blocks(response)

                # Speak the explanation
                if spoken:
                    console.print(f"[green]Nemotron:[/green] {spoken}")
                    tts.speak(spoken)

                # Display code blocks with syntax highlighting (not spoken)
                for i, block in enumerate(code_blocks, start=1):
                    if len(code_blocks) > 1:
                        console.print(f"\n[dim]Code block {i}:[/dim]")
                    syntax = Syntax(block.strip(), language.lower(), theme="monokai", line_numbers=True)
                    console.print(syntax)

                console.print()

            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    args = sys.argv[1:]
    lang_idx = next((i for i, a in enumerate(args) if a == "--language"), None)
    language = args[lang_idx + 1] if lang_idx is not None and lang_idx + 1 < len(args) else "Python"
    text_only = "--text-only" in args
    run_code_assistant(language=language, text_only=text_only)
