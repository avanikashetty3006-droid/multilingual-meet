"""speech-service (Role 3): FastAPI on port 8001.

Run:  MOCK=1 uvicorn main:app --port 8001
"""
import json
import os
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import mock

MOCK = os.getenv("MOCK", "1") == "1"  # real pipeline arrives in Step 5
PUBLIC_URL = os.getenv("SPEECH_PUBLIC_URL", "http://localhost:8001").rstrip("/")
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "8"))
AUDIO_DIR = Path(__file__).parent / "audio"

latencies = deque(maxlen=20)  # rolling real processing times (ms)
in_flight = 0  # requests running or waiting right now


@asynccontextmanager
async def lifespan(app: FastAPI):
    mock.ensure_audio_files(AUDIO_DIR)
    yield


app = FastAPI(title="speech-service", lifespan=lifespan)


@app.get("/v1/health")
async def health():
    avg = round(sum(latencies) / len(latencies)) if latencies else 0
    return {"status": "ok", "mock": MOCK, "queue_depth": in_flight, "avg_latency_ms": avg}


@app.post("/v1/process-chunk")
async def process_chunk(
    audio: UploadFile = File(...),
    room_id: str = Form(...),
    participant_id: str = Form(...),
    chunk_id: str = Form(...),
    src_lang: str = Form(...),
    tgt_langs: str = Form("[]"),
    want_audio: str = Form("false"),
    prev_text: str = Form(""),
):
    global in_flight

    try:
        targets = json.loads(tgt_langs)
        if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            raise ValueError
    except ValueError:
        raise HTTPException(422, 'tgt_langs must be a JSON list like ["hi","kn"]')

    if in_flight >= MAX_QUEUE_DEPTH:
        raise HTTPException(429, "speech-service busy, try again")
    if not MOCK:
        raise HTTPException(503, "real pipeline not built yet, run with MOCK=1")

    want = want_audio.strip().lower() == "true"
    data = await audio.read()

    in_flight += 1
    start = time.perf_counter()
    try:
        result = await mock.process(data, src_lang, targets, want, PUBLIC_URL)
    finally:
        in_flight -= 1

    total = round((time.perf_counter() - start) * 1000)
    latencies.append(total)
    result["timings_ms"]["total"] = total
    return {"chunk_id": chunk_id, "participant_id": participant_id, **result}


@app.get("/audio/{file}")
async def get_audio(file: str):
    path = AUDIO_DIR / file
    if Path(file).name != file or not file.endswith(".wav") or not path.is_file():
        raise HTTPException(404, "audio not found")
    return FileResponse(path, media_type="audio/wav")
