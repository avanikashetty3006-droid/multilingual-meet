"""MOCK=0 endpoint tests with FAKE engines (no models needed). Needs fastapi:  pytest -q tests/test_real_mode.py"""
import threading
import time

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from pipeline import Pipeline  # noqa: E402
from tests.test_pipeline import FakeASR, FakeMT, FakeTTS, silence, tone  # noqa: E402


class SlowASR(FakeASR):
    def transcribe(self, *a):
        time.sleep(1.0)
        return super().transcribe(*a)


def post(c, wav, want="true", tgt='["hi","kn"]', src="en"):
    return c.post("/v1/process-chunk", files={"audio": ("c.wav", wav, "audio/wav")},
                  data={"room_id": "r", "participant_id": "p", "chunk_id": "c1", "src_lang": src,
                        "tgt_langs": tgt, "want_audio": want})


@pytest.fixture
def real(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MOCK", False)
    monkeypatch.setattr(main, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(main, "pipeline", Pipeline(FakeASR(), FakeMT(), FakeTTS(), tmp_path / "audio", "http://localhost:8001"))
    monkeypatch.setattr(main, "device", "cpu")
    return main


def test_real_mode_contract_shape(real):
    with TestClient(main.app) as c:
        b = post(c, tone()).json()
        assert set(b) == {"chunk_id", "participant_id", "detected_lang", "source_text", "translations", "timings_ms"}
        assert set(b["timings_ms"]) == {"asr", "mt", "tts", "total"}
        assert b["source_text"] == "Hello everyone" and set(b["translations"]) == {"hi", "kn"}
        url = b["translations"]["hi"]["audio_url"]
        assert c.get(url.replace("http://localhost:8001", "")).status_code == 200


def test_silence_is_200_empty(real):
    with TestClient(main.app) as c:
        r = post(c, silence())
        assert r.status_code == 200 and r.json()["source_text"] == "" and r.json()["translations"] == {}


def test_health_reports_models_loaded_and_latency(real):
    with TestClient(main.app) as c:
        post(c, tone())
        h = c.get("/v1/health").json()
        assert h["models_loaded"] is True and h["mock"] is False and h["device"] == "cpu" and h["avg_latency_ms"] >= 0
        assert {"status", "queue_depth", "avg_latency_ms", "device", "models_loaded"} <= set(h)


def test_missing_models_gives_503_and_health_error(monkeypatch):
    monkeypatch.setattr(main, "MOCK", False)
    monkeypatch.setattr(main, "pipeline", None)
    monkeypatch.setattr(main, "load_error", "FileNotFoundError: NLLB model folder not found")
    monkeypatch.setattr(main, "load_models_blocking", lambda: None)
    with TestClient(main.app) as c:
        r = post(c, tone())
        assert r.status_code == 503 and "NLLB" in r.json()["detail"]
        h = c.get("/v1/health").json()
        assert h["models_loaded"] is False and h["status"] == "error"


def test_health_answers_fast_while_a_chunk_is_processing(real, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "pipeline", Pipeline(SlowASR(), FakeMT(), FakeTTS(), tmp_path / "audio", "http://x"))
    with TestClient(main.app) as c:
        t = threading.Thread(target=lambda: post(c, tone()))
        t.start()
        time.sleep(0.2)
        t0 = time.perf_counter()
        assert c.get("/v1/health").status_code == 200
        assert (time.perf_counter() - t0) < 0.2
        t.join()


def test_busy_returns_429_in_real_mode(real):
    with TestClient(main.app) as c:
        main.in_flight = main.MAX_QUEUE_DEPTH
        try:
            assert post(c, tone()).status_code == 429
        finally:
            main.in_flight = 0


def test_engine_crash_is_500_not_a_hang(real, monkeypatch, tmp_path):
    class Boom(FakeASR):
        def transcribe(self, *a):
            raise RuntimeError("cuda out of memory")
    monkeypatch.setattr(main, "pipeline", Pipeline(Boom(), FakeMT(), FakeTTS(), tmp_path / "audio", "http://x"))
    with TestClient(main.app) as c:
        assert post(c, tone()).status_code == 500
        assert main.in_flight == 0
