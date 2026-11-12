"""WebSocket and HTTP integration tests using FastAPI TestClient (Role 4, Step 5)."""

from __future__ import annotations

import struct
import sys
import time
import wave
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FRAME_BYTES
from main import create_app

FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "speech_sample.wav"
SILENT_FRAME = b"\x00" * FRAME_BYTES


def _make_tone_frame(amplitude: int = 2000) -> bytes:
    samples = [int(amplitude * ((i % 16) / 8.0 - 1.0)) for i in range(512)]
    return struct.pack("<512h", *samples)


def _load_wav_frames(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return [raw[i : i + FRAME_BYTES] for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES)]


def test_health_and_initial_token_snapshot():
    app = create_app(mock=True, mock_rotate=False)
    with TestClient(app) as client:
        res = client.get("/v1/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok", "mock": True, "rooms": 0, "streams": 0}

        with client.websocket_connect("/ws/token/room-init") as tok_ws:
            init_msg = tok_ws.receive_json()
            assert init_msg["type"] == "token_update"
            assert init_msg["room_id"] == "room-init"
            assert init_msg["holder"] is None
            assert init_msg["overlap"] == []
            assert isinstance(init_msg["ts_ms"], int)

            res2 = client.get("/v1/health")
            assert res2.json()["rooms"] == 1
            assert res2.json()["streams"] == 0


from contextlib import ExitStack


def test_mock_vad_token_flow_and_disconnect_release():
    # Fast hysteresis in test config so TestClient executes in < 100 ms
    cfg = {"min_speech_ms": 0, "release_silence_ms": 100, "min_hold_ms": 100, "max_overlap": 2}
    app = create_app(mock=True, mock_rotate=False, token_config=cfg, tick_interval_ms=20)
    tone = _make_tone_frame(2000)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/token/r1") as tok_ws:
            assert tok_ws.receive_json()["holder"] is None

            stack = ExitStack()
            vad1 = stack.enter_context(client.websocket_connect("/ws/vad/r1/p-1"))
            # Wrong-sized frame is ignored without crashing
            vad1.send_bytes(b"bad")
            for _ in range(4):
                vad1.send_bytes(tone)
            vad_msg = vad1.receive_json()
            assert vad_msg["type"] == "vad"
            assert vad_msg["participant_id"] == "p-1"
            assert vad_msg["state"] == "speech_start"

            tok_msg = tok_ws.receive_json()
            assert tok_msg["holder"] == "p-1"
            assert tok_msg["overlap"] == []

            # Debug room state endpoint
            rstate = client.get("/v1/rooms/r1/state").json()
            assert rstate["holder"] == "p-1"
            assert rstate["streams"] == ["p-1"]

            # Second speaker joins and overlaps
            with client.websocket_connect("/ws/vad/r1/p-2") as vad2:
                for _ in range(4):
                    vad2.send_bytes(tone)
                assert vad2.receive_json()["state"] == "speech_start"

                tok_msg2 = tok_ws.receive_json()
                assert tok_msg2["holder"] == "p-1"
                assert tok_msg2["overlap"] == ["p-2"]

                # Disconnect p-1 while p-2 stays connected -> p-2 promoted immediately
                stack.close()
                tok_msg3 = tok_ws.receive_json()
                assert tok_msg3["holder"] == "p-2"
                assert tok_msg3["overlap"] == []

        # Both disconnected -> token released
        with client.websocket_connect("/ws/token/r1") as tok_ws2:
            assert tok_ws2.receive_json()["holder"] is None


def test_real_silero_vad_ws_endpoints():
    cfg = {"min_speech_ms": 0, "release_silence_ms": 100, "min_hold_ms": 100, "max_overlap": 2}
    app = create_app(mock=False, mock_rotate=False, token_config=cfg, tick_interval_ms=20)
    speech_frames = _load_wav_frames(FIXTURE_WAV)

    with TestClient(app) as client:
        assert client.get("/v1/health").json()["mock"] is False

        with client.websocket_connect("/ws/token/r-silero") as tok_ws:
            assert tok_ws.receive_json()["holder"] is None

            with client.websocket_connect("/ws/vad/r-silero/p-1") as vad1:
                for f in speech_frames + [SILENT_FRAME] * 25:
                    vad1.send_bytes(f)

                ev1 = vad1.receive_json()
                ev2 = vad1.receive_json()
                assert ev1["state"] == "speech_start"
                assert ev2["state"] == "speech_end"

                tok1 = tok_ws.receive_json()
                assert tok1["holder"] == "p-1"


def test_stall_timeout_emits_speech_end():
    cfg = {"min_speech_ms": 0, "release_silence_ms": 50, "min_hold_ms": 50, "max_overlap": 2}
    app = create_app(
        mock=True,
        mock_rotate=False,
        token_config=cfg,
        stall_timeout_ms=80,
        tick_interval_ms=20,
    )
    tone = _make_tone_frame(2000)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/token/r-stall") as tok_ws:
            assert tok_ws.receive_json()["holder"] is None
            with client.websocket_connect("/ws/vad/r-stall/p-1") as vad1:
                for _ in range(4):
                    vad1.send_bytes(tone)
                assert vad1.receive_json()["state"] == "speech_start"
                assert tok_ws.receive_json()["holder"] == "p-1"

                # Stop sending frames completely -> stall timeout emits speech_end & releases token
                time.sleep(0.2)
                assert vad1.receive_json()["state"] == "speech_end"
                assert tok_ws.receive_json()["holder"] is None


def test_multi_subscriber_broadcast_and_mock_rotate():
    app = create_app(mock=True, mock_rotate=True, tick_interval_ms=20)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/token/r-rot") as sub1, client.websocket_connect("/ws/token/r-rot") as sub2:
            assert sub1.receive_json()["holder"] is None
            assert sub2.receive_json()["holder"] is None

            with client.websocket_connect("/ws/vad/r-rot/p-1"):
                m1 = sub1.receive_json()
                m2 = sub2.receive_json()
                assert m1["holder"] == "p-1"
                assert m2["holder"] == "p-1"
