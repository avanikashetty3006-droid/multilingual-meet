import asyncio
import json
import logging
import os
import time
from typing import Dict, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from token_manager import TokenManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("speaker-service")

MOCK_MODE = os.getenv("MOCK", "1") == "1"

app = FastAPI(
    title="Speaker Detection Service (Role 4)",
    version="0.1.0",
    description="VAD and Token Passing Service for Multilingual Video Conferencing"
)

# In-memory room token managers & subscribers
room_managers: Dict[str, TokenManager] = {}
token_subscribers: Dict[str, Set[WebSocket]] = {}
room_participants: Dict[str, Set[str]] = {}


def get_or_create_manager(room_id: str) -> TokenManager:
    if room_id not in room_managers:
        room_managers[room_id] = TokenManager(room_id)
        room_participants[room_id] = set()
    return room_managers[room_id]


async def broadcast_token_update(room_id: str, message: dict):
    subscribers = token_subscribers.get(room_id, set())
    disconnected = set()
    for ws in subscribers:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            disconnected.add(ws)
    for ws in disconnected:
        subscribers.remove(ws)


@app.get("/v1/health")
async def health():
    return {
        "status": "ok",
        "mock": MOCK_MODE,
        "service": "speaker-service",
        "rooms_tracked": len(room_managers)
    }


@app.websocket("/ws/vad/{room_id}/{participant_id}")
async def vad_socket(websocket: WebSocket, room_id: str, participant_id: str):
    """
    Contract A5: Receives 1024-byte binary mic frames.
    Sends: {"type":"vad","participant_id":...,"state":"speech_start"|"speech_end","ts_ms":...}
    """
    await websocket.accept()
    manager = get_or_create_manager(room_id)
    room_participants[room_id].add(participant_id)

    frame_counter = 0
    is_speaking = False

    try:
        while True:
            data = await websocket.receive_bytes()
            if len(data) != 1024:
                continue

            frame_counter += 1
            ts_ms = int(time.time() * 1000)

            if MOCK_MODE:
                # Mock VAD: simulate speech bursts every ~30 frames (~1 sec)
                if frame_counter % 30 == 0:
                    is_speaking = not is_speaking
                    state = "speech_start" if is_speaking else "speech_end"
                    vad_event = {
                        "type": "vad",
                        "participant_id": participant_id,
                        "state": state,
                        "ts_ms": ts_ms
                    }
                    await websocket.send_text(json.dumps(vad_event))

                    # Update token manager
                    if is_speaking:
                        if manager.on_speech_start(participant_id, ts_ms):
                            await broadcast_token_update(room_id, manager.get_state(ts_ms))
                    else:
                        if manager.on_speech_end(participant_id, ts_ms):
                            await broadcast_token_update(room_id, manager.get_state(ts_ms))

    except WebSocketDisconnect:
        logger.info(f"VAD socket closed for {participant_id} in {room_id}")
    finally:
        ts_ms = int(time.time() * 1000)
        room_participants[room_id].discard(participant_id)
        if manager.on_disconnect(participant_id, ts_ms):
            await broadcast_token_update(room_id, manager.get_state(ts_ms))


@app.websocket("/ws/token/{room_id}")
async def token_socket(websocket: WebSocket, room_id: str):
    """
    Contract A5: Emits {"type":"token_update","room_id":...,"holder":...|null,"overlap":[...],"ts_ms":...}
    """
    await websocket.accept()
    if room_id not in token_subscribers:
        token_subscribers[room_id] = set()
    token_subscribers[room_id].add(websocket)

    manager = get_or_create_manager(room_id)

    # Immediately send current state
    await websocket.send_text(json.dumps(manager.get_state()))

    # Background task for mock rotation if in MOCK mode
    async def mock_rotator_loop():
        idx = 0
        while MOCK_MODE:
            await asyncio.sleep(5.0)
            p_list = list(room_participants.get(room_id, []))
            if not p_list:
                p_list = ["p-1", "p-2"]  # fallback mock participants
            holder = p_list[idx % len(p_list)]
            overlap = [p for p in p_list if p != holder][:2]
            idx += 1
            ts_ms = int(time.time() * 1000)
            update = {
                "type": "token_update",
                "room_id": room_id,
                "holder": holder,
                "overlap": overlap,
                "ts_ms": ts_ms
            }
            await broadcast_token_update(room_id, update)

    rotator_task = asyncio.create_task(mock_rotator_loop()) if MOCK_MODE else None

    try:
        while True:
            # Keep socket open and consume any incoming ping/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"Token socket disconnected for room {room_id}")
    finally:
        token_subscribers[room_id].discard(websocket)
        if rotator_task:
            rotator_task.cancel()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
