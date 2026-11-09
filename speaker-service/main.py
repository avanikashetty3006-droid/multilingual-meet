import asyncio
import json
import logging
import os
import time
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from vad import VadStream
from token_manager import TokenManager
from mock import MockSpeakerService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("speaker-service")

MOCK = os.getenv("MOCK", "1") == "1"

app = FastAPI(title="Speaker Service (Role 4)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

room_managers: Dict[str, TokenManager] = {}
token_subscribers: Dict[str, Set[WebSocket]] = {}
mock_service = MockSpeakerService()


def get_token_manager(room_id: str) -> TokenManager:
    if room_id not in room_managers:
        room_managers[room_id] = TokenManager(room_id)
    return room_managers[room_id]


async def broadcast_token_update(room_id: str, ts_ms: int):
    tm = get_token_manager(room_id)
    update_msg = tm.state(ts_ms)
    subs = list(token_subscribers.get(room_id, []))
    for ws in subs:
        try:
            await ws.send_json(update_msg)
        except Exception:
            pass


@app.get("/v1/health")
async def health():
    return {"status": "ok", "mock": MOCK}


@app.websocket("/ws/token/{room_id}")
async def token_ws(websocket: WebSocket, room_id: str):
    await websocket.accept()
    if room_id not in token_subscribers:
        token_subscribers[room_id] = set()
    token_subscribers[room_id].add(websocket)

    # Send current state
    tm = get_token_manager(room_id)
    await websocket.send_json(tm.state(int(time.time() * 1000)))

    rotator_task = None
    if MOCK:
        rotator_task = asyncio.create_task(
            mock_service.run_token_rotator(room_id, websocket.send_json)
        )

    try:
        while True:
            # Keep alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if rotator_task:
            rotator_task.cancel()
        token_subscribers[room_id].discard(websocket)


@app.websocket("/ws/vad/{room_id}/{participant_id}")
async def vad_ws(websocket: WebSocket, room_id: str, participant_id: str):
    await websocket.accept()
    tm = get_token_manager(room_id)
    vad = VadStream(participant_id)
    mock_service.register_participant(room_id, participant_id)

    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            now_ms = int(time.time() * 1000)
            event = vad.process_frame(frame_bytes, now_ms)

            if event == "speech_start":
                changed = tm.on_speech_start(participant_id, now_ms)
                await websocket.send_json({
                    "type": "vad",
                    "participant_id": participant_id,
                    "state": "speech_start",
                    "ts_ms": now_ms,
                })
                if changed:
                    await broadcast_token_update(room_id, now_ms)

            elif event == "speech_end":
                changed = tm.on_speech_end(participant_id, now_ms)
                await websocket.send_json({
                    "type": "vad",
                    "participant_id": participant_id,
                    "state": "speech_end",
                    "ts_ms": now_ms,
                })
                if changed:
                    await broadcast_token_update(room_id, now_ms)

    except WebSocketDisconnect:
        pass
    finally:
        mock_service.unregister_participant(room_id, participant_id)
        now_ms = int(time.time() * 1000)
        changed = tm.on_participant_leave(participant_id, now_ms)
        if changed:
            await broadcast_token_update(room_id, now_ms)
