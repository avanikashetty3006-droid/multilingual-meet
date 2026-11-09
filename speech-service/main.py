import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from mock import mock_process_chunk, AUDIO_DIR
from asr import transcribe_audio
from translate import translate_text
from tts import synthesize_speech

MOCK = os.getenv("MOCK", "1") == "1"

app = FastAPI(title="Speech Service (Role 3)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/health")
async def health():
    return {
        "status": "ok",
        "queue_depth": 0,
        "avg_latency_ms": 950,
        "device": "cpu",
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path, media_type="audio/wav")


@app.post("/v1/process-chunk")
async def process_chunk(
    request: Request,
    audio: UploadFile = File(...),
    room_id: str = Form(...),
    participant_id: str = Form(...),
    chunk_id: str = Form(...),
    src_lang: str = Form("auto"),
    tgt_langs: str = Form("[]"),
    want_audio: str = Form("false"),
    prev_text: Optional[str] = Form(None),
):
    audio_bytes = await audio.read()
    try:
        targets = json.loads(tgt_langs)
    except Exception:
        targets = []
    wants_audio = want_audio.lower() == "true"

    base_url = str(request.base_url).rstrip("/")

    if MOCK:
        return await mock_process_chunk(
            audio_bytes=audio_bytes,
            room_id=room_id,
            participant_id=participant_id,
            chunk_id=chunk_id,
            src_lang=src_lang,
            tgt_langs=targets,
            want_audio=wants_audio,
            base_url=base_url,
        )

    t0 = time.time()
    t_asr_0 = time.time()
    detected_lang, source_text = transcribe_audio(audio_bytes, src_lang)
    asr_ms = int((time.time() - t_asr_0) * 1000)

    t_mt_0 = time.time()
    translations = {}
    tts_ms_acc = 0

    for lang in targets:
        trans_text = translate_text(source_text, detected_lang, lang)
        audio_url = None
        if wants_audio:
            t_tts_0 = time.time()
            filename = synthesize_speech(trans_text, lang, chunk_id)
            tts_ms_acc += int((time.time() - t_tts_0) * 1000)
            if filename:
                audio_url = f"{base_url}/audio/{filename}"

        translations[lang] = {
            "text": trans_text,
            "audio_url": audio_url,
        }

    mt_ms = int((time.time() - t_mt_0) * 1000) - tts_ms_acc
    total_ms = int((time.time() - t0) * 1000)

    return {
        "chunk_id": chunk_id,
        "participant_id": participant_id,
        "detected_lang": detected_lang,
        "source_text": source_text,
        "translations": translations,
        "timings_ms": {
            "asr": asr_ms,
            "mt": max(0, mt_ms),
            "tts": tts_ms_acc,
            "total": total_ms,
        },
    }
