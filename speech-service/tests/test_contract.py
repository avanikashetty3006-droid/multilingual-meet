import io
import json
import pytest
from fastapi.testclient import TestClient
import wave
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from main import app

client = TestClient(app)

def create_sample_wav() -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 32000)
    return buf.getvalue()

def test_health():
    res = client.get("/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "avg_latency_ms" in data

def test_process_chunk_contract():
    wav_bytes = create_sample_wav()
    files = {"audio": ("test.wav", wav_bytes, "audio/wav")}
    data = {
        "room_id": "test-room",
        "participant_id": "p-1",
        "chunk_id": "p-1-0",
        "src_lang": "auto",
        "tgt_langs": json.dumps(["hi", "kn"]),
        "want_audio": "true",
    }

    res = client.post("/v1/process-chunk", data=data, files=files)
    assert res.status_code == 200
    resp = res.json()

    assert resp["chunk_id"] == "p-1-0"
    assert resp["participant_id"] == "p-1"
    assert "detected_lang" in resp
    assert "source_text" in resp
    assert "translations" in resp
    assert "hi" in resp["translations"]
    assert "kn" in resp["translations"]
    assert "timings_ms" in resp
