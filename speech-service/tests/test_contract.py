import json
import os
import io
import pytest
from fastapi.testclient import TestClient

# Ensure MOCK=1 is set for testing
os.environ["MOCK"] = "1"
os.environ["MAX_QUEUE_DEPTH"] = "4"
from main import app

client = TestClient(app)

def create_dummy_wav(duration_bytes: int = 1024) -> io.BytesIO:
    # 44 bytes wav header + dummy PCM
    header = b"RIFF" + (duration_bytes + 36).to_bytes(4, "little") + b"WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data" + duration_bytes.to_bytes(4, "little")
    pcm = b"\x01\x00" * (duration_bytes // 2)
    return io.BytesIO(header + pcm)

def test_1_health_endpoint():
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "queue_depth" in data
    assert "avg_latency_ms" in data
    assert "device" in data
    assert data["mock"] is True

def test_2_process_chunk_with_audio():
    wav_file = create_dummy_wav(4000)
    response = client.post(
        "/v1/process-chunk",
        data={
            "room_id": "room1",
            "participant_id": "p-1",
            "chunk_id": "p-1-0",
            "src_lang": "en",
            "tgt_langs": json.dumps(["hi", "kn"]),
            "want_audio": "true"
        },
        files={"audio": ("chunk.wav", wav_file, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chunk_id"] == "p-1-0"
    assert data["participant_id"] == "p-1"
    assert data["detected_lang"] == "en"
    assert len(data["source_text"]) > 0
    assert "hi" in data["translations"]
    assert "kn" in data["translations"]
    assert data["translations"]["hi"]["audio_url"] is not None
    assert data["timings_ms"]["tts"] > 0
    assert data["timings_ms"]["total"] > 0

def test_3_process_chunk_without_audio():
    wav_file = create_dummy_wav(4000)
    response = client.post(
        "/v1/process-chunk",
        data={
            "room_id": "room1",
            "participant_id": "p-1",
            "chunk_id": "p-1-1",
            "src_lang": "en",
            "tgt_langs": json.dumps(["hi"]),
            "want_audio": "false"
        },
        files={"audio": ("chunk.wav", wav_file, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["translations"]["hi"]["audio_url"] is None
    assert data["timings_ms"]["tts"] == 0

def test_4_process_chunk_silence():
    # Empty or silent audio
    wav_file = io.BytesIO(b"\x00" * 128)
    response = client.post(
        "/v1/process-chunk",
        data={
            "room_id": "room1",
            "participant_id": "p-1",
            "chunk_id": "p-1-2",
            "src_lang": "en",
            "tgt_langs": json.dumps(["hi"]),
            "want_audio": "false"
        },
        files={"audio": ("silent.wav", wav_file, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source_text"] == ""
    assert data["translations"] == {}

def test_5_process_chunk_auto_src_lang():
    wav_file = create_dummy_wav(4000)
    response = client.post(
        "/v1/process-chunk",
        data={
            "room_id": "room1",
            "participant_id": "p-2",
            "chunk_id": "p-2-0",
            "src_lang": "auto",
            "tgt_langs": json.dumps(["hi", "kn"]),
            "want_audio": "true"
        },
        files={"audio": ("chunk.wav", wav_file, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["detected_lang"] in ["en", "hi", "kn"]

def test_6_audio_static_files():
    for filename in ["sample.wav", "mock_en.wav", "mock_hi.wav", "mock_kn.wav"]:
        response = client.get(f"/audio/{filename}")
        assert response.status_code == 200
        assert len(response.content) > 44

def test_7_invalid_tgt_langs_422():
    wav_file = create_dummy_wav(1000)
    response = client.post(
        "/v1/process-chunk",
        data={
            "room_id": "room1",
            "participant_id": "p-1",
            "chunk_id": "p-1-3",
            "src_lang": "en",
            "tgt_langs": "not-valid-json",
            "want_audio": "false"
        },
        files={"audio": ("chunk.wav", wav_file, "audio/wav")}
    )
    assert response.status_code == 422

def test_8_queue_depth_429():
    import main
    original_depth = main.active_requests
    try:
        main.active_requests = main.MAX_QUEUE_DEPTH
        wav_file = create_dummy_wav(1000)
        response = client.post(
            "/v1/process-chunk",
            data={
                "room_id": "room1",
                "participant_id": "p-1",
                "chunk_id": "p-1-4",
                "src_lang": "en",
                "tgt_langs": json.dumps(["hi"]),
                "want_audio": "false"
            },
            files={"audio": ("chunk.wav", wav_file, "audio/wav")}
        )
        assert response.status_code == 429
    finally:
        main.active_requests = original_depth
