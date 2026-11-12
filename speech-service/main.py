import asyncio
from collections import deque
import json
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from mock import process_chunk_mock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("speech-service")

# Configurations from Environment
MOCK_MODE = os.getenv("MOCK", "1") == "1"
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "8"))
SPEECH_PUBLIC_URL = os.getenv("SPEECH_PUBLIC_URL", "http://localhost:8001").rstrip("/")
AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

app = FastAPI(
    title="Speech Translation Service (Role 3)",
    version="0.1.0",
    description="ASR -> MT -> TTS Pipeline for Multilingual Video Conferencing"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Concurrency & Metric tracking
active_requests = 0
request_lock = asyncio.Lock()
latency_history = deque(maxlen=20)


@app.get("/v1/health")
async def health_check():
    """
    Contract A6: Returns status, queue_depth, avg_latency_ms, device.
    Polled every 2s by Call Server (Role 2) network monitor.
    """
    avg_latency = (
        sum(latency_history) / len(latency_history)
        if latency_history
        else 800.0 if MOCK_MODE else 0.0
    )
    return {
        "status": "ok",
        "queue_depth": active_requests,
        "avg_latency_ms": round(avg_latency, 2),
        "device": "cpu",
        "mock": MOCK_MODE,
    }


@app.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """
    Contract A6: Serves generated speech and sample audio files.
    """
    file_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{filename}' not found"
        )
    return FileResponse(file_path, media_type="audio/wav")


@app.post("/v1/process-chunk")
async def process_chunk(
    audio: UploadFile = File(...),
    room_id: str = Form(...),
    participant_id: str = Form(...),
    chunk_id: str = Form(...),
    src_lang: str = Form("auto"),
    tgt_langs: str = Form(...),
    want_audio: str = Form("false"),
    prev_text: Optional[str] = Form(None),
):
    """
    Contract A6: Takes audio chunk and returns transcript, translations, and audio URLs.
    """
    global active_requests

    # Queue limit check (Contract A6/Role 3 Step 7)
    async with request_lock:
        if active_requests >= MAX_QUEUE_DEPTH:
            logger.warning(f"Queue full ({active_requests}/{MAX_QUEUE_DEPTH}). Returning 429.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service busy: queue depth exceeded"
            )
        active_requests += 1

    start_ts = time.time()

    try:
        # Parse inputs
        try:
            target_languages = json.loads(tgt_langs)
            if not isinstance(target_languages, list):
                raise ValueError("tgt_langs must be a JSON array")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid JSON format for tgt_langs. Expected list string e.g. [\"hi\",\"kn\"]"
            )

        is_want_audio = want_audio.strip().lower() in ("true", "1", "yes")

        # Read audio chunk
        audio_bytes = await audio.read()
        is_silence = False

        # Basic silence check (very small payload or zero-filled buffer)
        if len(audio_bytes) < 256:
            is_silence = True
        else:
            # Check for header-only or flat silence
            pcm_payload = audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
            if all(b == 0 for b in pcm_payload[:256]):
                is_silence = True

        if MOCK_MODE:
            result = await process_chunk_mock(
                chunk_id=chunk_id,
                participant_id=participant_id,
                src_lang=src_lang,
                tgt_langs=target_languages,
                want_audio=is_want_audio,
                is_silence=is_silence,
                prev_text=prev_text,
            )
        else:
            # Step 2 to 5: Real pipeline
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="real pipeline not built yet"
            )

        elapsed_ms = (time.time() - start_ts) * 1000.0
        latency_history.append(elapsed_ms)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    finally:
        async with request_lock:
            active_requests = max(0, active_requests - 1)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
