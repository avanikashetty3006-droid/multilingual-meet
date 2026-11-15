"""speech-service (Role 3): FastAPI on port 8001.

Run mock:  MOCK=1 uvicorn main:app --port 8001
Run real:  MOCK=0 uvicorn main:app --port 8001      (needs requirements-real.txt and the NLLB model, see README)
"""
import asyncio
import json
import logging
import os
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import mock
from pipeline import Pipeline, cleanup_old_audio

log = logging.getLogger("speech-service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

MOCK = os.getenv("MOCK", "1") == "1"
PUBLIC_URL = os.getenv("SPEECH_PUBLIC_URL", "http://localhost:8001").rstrip("/")
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "8"))
AUDIO_DIR = Path(os.getenv("AUDIO_DIR", str(Path(__file__).parent / "audio")))
AUDIO_MAX_AGE_S = int(os.getenv("AUDIO_MAX_AGE_S", "600"))
WORKERS = int(os.getenv("WORKERS", "1"))   # model calls run in this many threads (CPU: keep 1)

latencies = deque(maxlen=20)  # rolling real processing times (ms)
in_flight = 0                 # requests running or waiting right now

pipeline = None               # set when the real models are loaded (MOCK=0)
device = "cpu"
load_error = None             # text shown in /v1/health and in 503 answers
whisper_name = None
executor = ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="speech")


def load_models_blocking():
    """Runs in a thread at startup. Never raises: a missing model must not crash the service."""
    global pipeline, device, load_error, whisper_name
    try:
        import engines
        asr, mt, tts, dev = engines.load_real_pipeline_parts()
        pipeline = Pipeline(asr, mt, tts, AUDIO_DIR, PUBLIC_URL)
        device, whisper_name, load_error = dev, engines.WHISPER_MODEL, None
        log.info("real pipeline ready on %s", dev)
    except Exception as e:  # noqa: BLE001
        load_error = f"{type(e).__name__}: {e}"
        log.error("could not load models: %s", load_error)


async def cleanup_loop():
    while True:
        await asyncio.sleep(60)
        try:
            n = cleanup_old_audio(AUDIO_DIR, AUDIO_MAX_AGE_S)
            if n:
                log.info("deleted %d old audio files", n)
        except Exception:
            log.exception("audio cleanup failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    mock.ensure_audio_files(AUDIO_DIR)
    tasks = [asyncio.create_task(cleanup_loop())]
    if not MOCK and pipeline is None:
        tasks.append(asyncio.create_task(asyncio.to_thread(load_models_blocking)))
    yield
    for t in tasks:
        t.cancel()
    executor.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="speech-service", lifespan=lifespan)


@app.get("/v1/health")
async def health():
    avg = round(sum(latencies) / len(latencies)) if latencies else 0
    body = {"status": "ok", "mock": MOCK, "queue_depth": in_flight, "avg_latency_ms": avg,
            "device": device, "models_loaded": MOCK or pipeline is not None}
    if not MOCK:
        body["whisper_model"] = whisper_name
        if pipeline is None:
            body["status"] = "loading" if load_error is None else "error"
            body["error"] = load_error
    return body


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
    if not MOCK and pipeline is None:
        raise HTTPException(503, f"models not loaded: {load_error or 'still loading, try again in a minute'}")

    want = want_audio.strip().lower() == "true"
    data = await audio.read()

    in_flight += 1
    start = time.perf_counter()
    try:
        if MOCK:
            result = await mock.process(data, src_lang, targets, want, PUBLIC_URL)
        else:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(executor, pipeline.run, data, src_lang, targets, want, prev_text)
    except HTTPException:
        raise
    except Exception:
        log.exception("process-chunk failed")
        raise HTTPException(500, "processing failed")
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
