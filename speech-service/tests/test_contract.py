"""Contract tests. Run from speech-service/:  MOCK=1 pytest -q"""
import io
import math
import os
import random
import struct
import wave

from fastapi.testclient import TestClient

import main

SR = 16000


def make_wav(kind="tone", seconds=1.0) -> bytes:
    n = int(SR * seconds)
    if kind == "tone":
        samples = [int(9000 * math.sin(2 * math.pi * 440 * i / SR)) for i in range(n)]
    elif kind == "noise":
        samples = [random.randint(-40, 40) for _ in range(n)]
    else:
        samples = [0] * n
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    return buf.getvalue()


def post(client, wav, want_audio="false", tgt='["hi","kn"]', src="en"):
    return client.post(
        "/v1/process-chunk",
        files={"audio": ("chunk.wav", wav, "audio/wav")},
        data={
            "room_id": "r1", "participant_id": "p1", "chunk_id": "c1",
            "src_lang": src, "tgt_langs": tgt, "want_audio": want_audio,
        },
    )


def check_schema(body):
    assert set(body) == {"chunk_id", "participant_id", "detected_lang",
                         "source_text", "translations", "timings_ms"}
    assert set(body["timings_ms"]) == {"asr", "mt", "tts", "total"}
    for t in body["translations"].values():
        assert set(t) == {"text", "audio_url"}


def test_schema_with_audio():
    with TestClient(main.app) as c:
        body = post(c, make_wav(), want_audio="true").json()
        check_schema(body)
        assert set(body["translations"]) == {"hi", "kn"}
        for t in body["translations"].values():
            assert t["audio_url"].startswith("http")
            assert c.get(t["audio_url"].replace(main.PUBLIC_URL, "")).status_code == 200


def test_want_audio_false_skips_tts():
    with TestClient(main.app) as c:
        body = post(c, make_wav(), want_audio="false").json()
        check_schema(body)
        assert body["timings_ms"]["tts"] == 0
        assert all(t["audio_url"] is None for t in body["translations"].values())


def test_silence_and_noise_return_200_empty():
    with TestClient(main.app) as c:
        for kind in ("silence", "noise"):
            r = post(c, make_wav(kind))
            assert r.status_code == 200
            assert r.json()["source_text"] == ""
            assert r.json()["translations"] == {}


def test_garbage_audio_does_not_crash():
    with TestClient(main.app) as c:
        r = post(c, b"not a wav")
        assert r.status_code == 200 and r.json()["source_text"] == ""


def test_auto_language_works():
    with TestClient(main.app) as c:
        r = post(c, make_wav(), src="auto")
        assert r.status_code == 200 and r.json()["detected_lang"]


def test_bad_tgt_langs_is_422():
    with TestClient(main.app) as c:
        assert post(c, make_wav(), tgt="hi,kn").status_code == 422


def test_busy_returns_429():
    with TestClient(main.app) as c:
        main.in_flight = main.MAX_QUEUE_DEPTH
        try:
            assert post(c, make_wav()).status_code == 429
        finally:
            main.in_flight = 0


def test_health_shape_and_sample_files():
    with TestClient(main.app) as c:
        h = c.get("/v1/health").json()
        assert {"queue_depth", "avg_latency_ms"} <= set(h)
        for f in ("sample.wav", "mock_en.wav", "mock_hi.wav", "mock_kn.wav"):
            assert c.get(f"/audio/{f}").status_code == 200
