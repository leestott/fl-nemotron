"""
app.py — FastAPI web application for the Foundry Local Nemotron Voice Assistant.

Provides a browser-based chat UI with:
  - Streaming chat responses via Server-Sent Events (SSE)
  - Microphone audio transcription endpoint
  - Model status API
  - Automatic demo mode fallback when Foundry Local is unavailable

Run (from project root):
    .venv\\Scripts\\uvicorn.exe app:app --app-dir src --host 0.0.0.0 --port 8000
    .venv\\Scripts\\uvicorn.exe app:app --app-dir src --reload --port 8000   # dev mode
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue as _queue
import sys
import tempfile
import threading
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure src/ is importable when running via --app-dir src
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from demo_client import DemoClient

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────────────────────
# Application state
# ─────────────────────────────────────────────────────────────────────────────

_ai_client = None
_demo_mode = True


def _init_ai_client() -> None:
    global _ai_client, _demo_mode
    try:
        from foundry_client import FoundryClient
        config = load_config()
        client = FoundryClient(config)
        client.initialize()
        _ai_client = client
        _demo_mode = False
        logger.info("Foundry Local initialised — running Nemotron chat + Nemotron STT on-device")
    except Exception as exc:
        logger.warning("Foundry Local unavailable (%s) — starting in demo mode", exc)
        _ai_client = DemoClient()
        _demo_mode = True


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Foundry Local Nemotron Voice Assistant",
    description="On-device AI voice assistant — no cloud required",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (CSS, JS, images if needed)
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.on_event("startup")
async def _startup() -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _init_ai_client)


@app.on_event("shutdown")
async def _shutdown() -> None:
    if _ai_client:
        _ai_client.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index() -> HTMLResponse:
    html_path = _static_dir / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def status() -> dict:
    """Return current model status and demo/foundry mode."""
    config = load_config()
    return {
        "mode": "demo" if _demo_mode else "foundry",
        "demo": _demo_mode,
        "models": {
            "nemotron": {
                "alias": config.nemotron.model_alias,
                "loaded": not _demo_mode,
            },
            "stt": {
                "alias": config.stt.model_alias,
                "loaded": not _demo_mode,
            },
        },
    }


class ChatRequest(BaseModel):
    messages: list[dict]
    stream: bool = True


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Chat endpoint.
    - stream=true  → text/event-stream (SSE), each event: data: {"token":"..."}
    - stream=false → JSON {"response": "..."}
    """
    if req.stream:
        return StreamingResponse(
            _sse_generator(req.messages),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(
        None, _ai_client.chat_completion, req.messages
    )
    return {"response": text}


async def _sse_generator(messages: list[dict]) -> AsyncIterator[str]:
    """Run the sync streaming generator in a thread, yielding SSE events."""
    token_q: _queue.Queue[str | None] = _queue.Queue()
    done = threading.Event()

    def _producer() -> None:
        try:
            for token in _ai_client.stream_completion(messages):
                token_q.put(token)
        except Exception as exc:
            token_q.put(f"\x00ERROR:{exc}")   # sentinel for errors
        finally:
            token_q.put(None)   # end sentinel
            done.set()

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    try:
        while True:
            try:
                item = token_q.get(timeout=0.05)
            except _queue.Empty:
                await asyncio.sleep(0)
                continue

            if item is None:
                break
            if isinstance(item, str) and item.startswith("\x00ERROR:"):
                err = item[7:]
                yield f"data: {json.dumps({'error': err})}\n\n"
                break
            yield f"data: {json.dumps({'token': item})}\n\n"
            await asyncio.sleep(0)   # yield control to event loop
    finally:
        yield "data: [DONE]\n\n"
        thread.join(timeout=5)


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """
    Accept an audio file (WebM/WAV/MP3) and return the transcription via the
    local NVIDIA Nemotron Speech Streaming model.
    """
    from foundry_client import NemotronSTTUnsupportedError

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        loop = asyncio.get_event_loop()
        try:
            text = await loop.run_in_executor(
                None, _ai_client.transcribe, tmp_path
            )
        except NemotronSTTUnsupportedError as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "nemotron_stt_unsupported",
                    "message": str(exc),
                },
            )
        except Exception as exc:
            logger.exception("Transcription failed")
            return JSONResponse(
                status_code=500,
                content={"error": "transcription_failed", "message": str(exc)},
            )
        return {"text": text or ""}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Direct execution
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
