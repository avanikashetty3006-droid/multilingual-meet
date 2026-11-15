import asyncio
from collections import deque
import json
import logging
import os
import tempfile
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
    version="0.2.0",
    description="ASR -> MT -> TTS Pipeline for Multilingual Video Conferencing (Contract A6)"
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

# Pipeline components for MOCK=0
asr_model = None
translator = None
tts_engine = None


def get_pipeline():
    """Lazily initializes the real ASR, MT, and TTS models for MOCK=0."""
    global asr_model, translator, tts_engine
    if asr_model is None:
        from asr import ASRModel
        from translate import IndicTranslator
        from tts import TTSEngine

        logger.info("Initializing real AI pipeline components (ASR -> MT -> TTS)...")
        asr_model = ASRModel(model_size=os.getenv("WHISPER_SIZE", "base"))
        translator = IndicTranslator()
        tts_engine = TTSEngine(output_dir=AUDIO_DIR)
    return asr_model, translator, tts_engine


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
    
    device = "cpu"
    if not MOCK_MODE:
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            pass

    return {
        "status": "ok",
        "queue_depth": active_requests,
        "avg_latency_ms": round(avg_latency, 2),
        "device": device,
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
    Handles both MOCK=1 and real AI pipeline (MOCK=0).
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
            # Real Pipeline: Step 5 (ASR -> MT -> TTS)
            if is_silence:
                result = {
                    "chunk_id": chunk_id,
                    "participant_id": participant_id,
                    "detected_lang": src_lang if src_lang != "auto" else "en",
                    "source_text": "",
                    "translations": {},
                    "timings_ms": {"asr": 0, "mt": 0, "tts": 0, "total": 0},
                }
            else:
                asr, mt_engine, tts = get_pipeline()

                # Save incoming bytes to temp wav file for faster-whisper
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                    tmp_wav.write(audio_bytes)
                    tmp_wav_path = tmp_wav.name

                try:
                    # 1. ASR
                    t_asr_start = time.time()
                    source_text, detected_lang = await asyncio.to_thread(
                        asr.transcribe, tmp_wav_path, src_lang, prev_text
                    )
                    asr_ms = int((time.time() - t_asr_start) * 1000)

                    # Silence check after ASR
                    if not source_text.strip():
                        result = {
                            "chunk_id": chunk_id,
                            "participant_id": participant_id,
                            "detected_lang": detected_lang,
                            "source_text": "",
                            "translations": {},
                            "timings_ms": {"asr": asr_ms, "mt": 0, "tts": 0, "total": asr_ms},
                        }
                    else:
                        # 2. MT (concurrent per target language)
                        t_mt_start = time.time()
                        translate_tasks = [
                            asyncio.to_thread(mt_engine.translate, source_text, detected_lang, tgt)
                            for tgt in target_languages
                        ]
                        translated_texts = await asyncio.gather(*translate_tasks)
                        mt_ms = int((time.time() - t_mt_start) * 1000)

                        # 3. TTS (concurrent per language only if want_audio is True)
                        t_tts_start = time.time()
                        if is_want_audio:
                            tts_tasks = [
                                asyncio.to_thread(tts.synthesize, t_text, tgt)
                                for t_text, tgt in zip(translated_texts, target_languages)
                            ]
                            audio_files = await asyncio.gather(*tts_tasks)
                            tts_ms = int((time.time() - t_tts_start) * 1000)
                        else:
                            audio_files = [None] * len(target_languages)
                            tts_ms = 0

                        # Assemble translations mapping
                        translations = {}
                        for tgt, t_text, fname in zip(target_languages, translated_texts, audio_files):
                            audio_url = f"{SPEECH_PUBLIC_URL}/audio/{fname}" if fname else None
                            translations[tgt] = {
                                "text": t_text,
                                "audio_url": audio_url
                            }

                        total_ms = int((time.time() - start_ts) * 1000)
                        result = {
                            "chunk_id": chunk_id,
                            "participant_id": participant_id,
                            "detected_lang": detected_lang,
                            "source_text": source_text,
                            "translations": translations,
                            "timings_ms": {
                                "asr": asr_ms,
                                "mt": mt_ms,
                                "tts": tts_ms,
                                "total": total_ms,
                            },
                        }
                finally:
                    if os.path.exists(tmp_wav_path):
                        try:
                            os.remove(tmp_wav_path)
                        except OSError:
                            pass

        elapsed_ms = (time.time() - start_ts) * 1000.0
        latency_history.append(elapsed_ms)
        return JSONResponse(status_code=status.HTTP_200_OK, content=result)

    finally:
        async with request_lock:
            active_requests = max(0, active_requests - 1)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
