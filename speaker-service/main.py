"""Speaker Service (Role 4): VAD + Speaking Token Manager on port 8002.

Interfaces (CONTRACT A5):
- WS /ws/vad/{room_id}/{participant_id}: binary 1024-byte PCM16 16kHz mono frames -> vad JSON on state change.
- WS /ws/token/{room_id}: subscribes to token_update JSON (sent immediately on connect, then on change).

Additive endpoints (documented in README):
- GET /v1/health
- GET /v1/rooms/{room_id}/state
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

import config as cfg
from mock import MockRoomRotator, create_mock_vad_stream
from token_manager import TokenManager
from vad import BaseVadStream, SileroOnnxEngine, SileroVadStream, get_silero_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("speaker-service")


def _mono_ms() -> int:
    return int(time.monotonic() * 1000)


def _epoch_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class StreamEntry:
    conn_id: int
    participant_id: str
    websocket: WebSocket
    vad: BaseVadStream
    last_frame_mono_ms: int


@dataclass
class RoomState:
    room_id: str
    token_manager: TokenManager
    rotator: MockRoomRotator
    streams: Dict[str, StreamEntry] = field(default_factory=dict)
    subscribers: Set[WebSocket] = field(default_factory=set)

    def current_token_payload(self, mock_rotate: bool) -> Dict[str, Any]:
        if mock_rotate:
            snap = self.rotator.snapshot(list(self.streams.keys()))
        else:
            snap = self.token_manager.state()
        return {
            "type": "token_update",
            "room_id": self.room_id,
            "holder": snap["holder"],
            "overlap": snap["overlap"],
            "ts_ms": _epoch_ms(),
        }


class SpeakerServiceState:
    """In-memory state registry shared across /ws/vad and /ws/token connections."""

    def __init__(
        self,
        mock: bool = cfg.MOCK,
        mock_rotate: bool = cfg.MOCK_ROTATE,
        mock_rotate_interval_s: float = cfg.MOCK_ROTATE_INTERVAL_S,
        token_config: Optional[Dict[str, Any]] = None,
        vad_threshold: float = cfg.VAD_THRESHOLD,
        vad_neg_threshold: float = cfg.VAD_NEG_THRESHOLD,
        vad_start_frames: int = cfg.VAD_START_FRAMES,
        vad_end_silence_ms: int = cfg.VAD_END_SILENCE_MS,
        stall_timeout_ms: int = cfg.VAD_STALL_TIMEOUT_MS,
        tick_interval_ms: int = cfg.TICK_INTERVAL_MS,
        max_frame_queue: int = cfg.MAX_FRAME_QUEUE,
    ) -> None:
        self.mock = mock
        self.mock_rotate = mock_rotate
        self.mock_rotate_interval_ms = int(mock_rotate_interval_s * 1000)
        self.token_config = token_config if token_config is not None else cfg.get_token_config()
        self.vad_threshold = vad_threshold
        self.vad_neg_threshold = vad_neg_threshold
        self.vad_start_frames = vad_start_frames
        self.vad_end_silence_ms = vad_end_silence_ms
        self.stall_timeout_ms = stall_timeout_ms
        self.tick_interval_s = max(0.01, tick_interval_ms / 1000.0)
        self.max_frame_queue = max(1, max_frame_queue)

        self.rooms: Dict[str, RoomState] = {}
        self._conn_seq: int = 0
        self._silero_engine: Optional[SileroOnnxEngine] = None

    def next_conn_id(self) -> int:
        self._conn_seq += 1
        return self._conn_seq

    def ensure_vad_ready(self) -> None:
        if not self.mock and self._silero_engine is None:
            self._silero_engine = get_silero_engine()

    def create_vad_stream(self) -> BaseVadStream:
        if self.mock:
            return create_mock_vad_stream()
        self.ensure_vad_ready()
        return SileroVadStream(
            engine=self._silero_engine,
            threshold=self.vad_threshold,
            neg_threshold=self.vad_neg_threshold,
            start_frames=self.vad_start_frames,
            end_silence_ms=self.vad_end_silence_ms,
        )

    def get_or_create_room(self, room_id: str) -> RoomState:
        room = self.rooms.get(room_id)
        if room is None:
            room = RoomState(
                room_id=room_id,
                token_manager=TokenManager(self.token_config),
                rotator=MockRoomRotator(interval_ms=self.mock_rotate_interval_ms),
            )
            self.rooms[room_id] = room
        return room

    def cleanup_room_if_empty(self, room_id: str) -> None:
        room = self.rooms.get(room_id)
        if room is not None and not room.streams and not room.subscribers:
            self.rooms.pop(room_id, None)

    def total_streams(self) -> int:
        return sum(len(r.streams) for r in self.rooms.values())

    async def broadcast_token_state(self, room: RoomState, state_dict: Dict[str, Any]) -> None:
        logger.info(
            "TOKEN room=%s holder=%s overlap=%s",
            room.room_id,
            state_dict["holder"],
            state_dict["overlap"],
        )
        if not room.subscribers:
            return
        payload = json.dumps(
            {
                "type": "token_update",
                "room_id": room.room_id,
                "holder": state_dict["holder"],
                "overlap": state_dict["overlap"],
                "ts_ms": _epoch_ms(),
            }
        )
        dead: List[WebSocket] = []
        subscribers = list(room.subscribers)
        results = await asyncio.gather(
            *(ws.send_text(payload) for ws in subscribers),
            return_exceptions=True,
        )
        for ws, res in zip(subscribers, results):
            if isinstance(res, Exception):
                dead.append(ws)
        for ws in dead:
            room.subscribers.discard(ws)

    async def send_vad_event(self, websocket: WebSocket, participant_id: str, vad_state: str) -> None:
        payload = json.dumps(
            {
                "type": "vad",
                "participant_id": participant_id,
                "state": vad_state,
                "ts_ms": _epoch_ms(),
            }
        )
        await websocket.send_text(payload)


def create_app(
    mock: Optional[bool] = None,
    mock_rotate: Optional[bool] = None,
    token_config: Optional[Dict[str, Any]] = None,
    stall_timeout_ms: Optional[int] = None,
    tick_interval_ms: Optional[int] = None,
) -> FastAPI:
    """Create configured FastAPI app (also supports isolated instances in tests)."""
    state = SpeakerServiceState(
        mock=cfg.MOCK if mock is None else mock,
        mock_rotate=cfg.MOCK_ROTATE if mock_rotate is None else mock_rotate,
        token_config=token_config,
        stall_timeout_ms=cfg.VAD_STALL_TIMEOUT_MS if stall_timeout_ms is None else stall_timeout_ms,
        tick_interval_ms=cfg.TICK_INTERVAL_MS if tick_interval_ms is None else tick_interval_ms,
    )

    async def tick_loop() -> None:
        while True:
            try:
                await asyncio.sleep(state.tick_interval_s)
                now_mono = _mono_ms()

                for room in list(state.rooms.values()):
                    # 1. Detect muted/stalled streams that stopped sending frames mid-speech
                    for pid, entry in list(room.streams.items()):
                        if entry.vad.is_speaking and (now_mono - entry.last_frame_mono_ms) >= state.stall_timeout_ms:
                            forced = entry.vad.force_end()
                            if forced == "speech_end":
                                logger.info("STALL_END room=%s pid=%s", room.room_id, pid)
                                try:
                                    await state.send_vad_event(entry.websocket, pid, "speech_end")
                                except Exception:
                                    pass
                                if not (state.mock and state.mock_rotate):
                                    new_state = room.token_manager.on_vad(pid, "speech_end", now_mono)
                                    if new_state is not None:
                                        await state.broadcast_token_state(room, new_state)

                    # 2. Advance token timers (or fake mock rotation)
                    if state.mock and state.mock_rotate:
                        new_state = room.rotator.current_or_rotate(list(room.streams.keys()), now_mono)
                    else:
                        new_state = room.token_manager.tick(now_mono)

                    if new_state is not None:
                        await state.broadcast_token_state(room, new_state)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("tick_loop error: %s", exc)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not state.mock:
            state.ensure_vad_ready()
            logger.info("Silero ONNX VAD warmed up (model=%s, threshold=%.2f, end_silence=%dms)",
                        cfg.VAD_MODEL_PATH.name, state.vad_threshold, state.vad_end_silence_ms)
        else:
            logger.info("Running in MOCK=1 mode (energy-gate VAD, mock_rotate=%s)", state.mock_rotate)

        tick_task = asyncio.create_task(tick_loop())
        try:
            yield
        finally:
            tick_task.cancel()
            try:
                await tick_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="VAAK Speaker Service (Role 4)", lifespan=lifespan)
    app.state.speaker_state = state

    @app.get("/v1/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "mock": state.mock,
            "rooms": len(state.rooms),
            "streams": state.total_streams(),
        }

    @app.get("/v1/rooms/{room_id}/state")
    async def room_state(room_id: str) -> Dict[str, Any]:
        room = state.rooms.get(room_id)
        if room is None:
            raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")
        snap = (
            room.rotator.snapshot(list(room.streams.keys()))
            if (state.mock and state.mock_rotate)
            else room.token_manager.state()
        )
        return {
            "room_id": room_id,
            "holder": snap["holder"],
            "overlap": snap["overlap"],
            "streams": sorted(room.streams.keys()),
            "subscribers": len(room.subscribers),
        }

    @app.websocket("/ws/vad/{room_id}/{participant_id}")
    async def ws_vad(websocket: WebSocket, room_id: str, participant_id: str) -> None:
        await websocket.accept()
        room = state.get_or_create_room(room_id)
        conn_id = state.next_conn_id()
        vad_stream = state.create_vad_stream()
        entry = StreamEntry(
            conn_id=conn_id,
            participant_id=participant_id,
            websocket=websocket,
            vad=vad_stream,
            last_frame_mono_ms=_mono_ms(),
        )

        # If this participant reconnected before the old socket closed, reset token state cleanly
        old_entry = room.streams.get(participant_id)
        room.streams[participant_id] = entry
        if old_entry is not None and not (state.mock and state.mock_rotate):
            reset_state = room.token_manager.on_disconnect(participant_id, _mono_ms())
            if reset_state is not None:
                await state.broadcast_token_state(room, reset_state)

        logger.info("JOIN room=%s pid=%s mock=%s", room_id, participant_id, state.mock)

        if state.mock and state.mock_rotate:
            rot_state = room.rotator.current_or_rotate(list(room.streams.keys()), _mono_ms(), force=True)
            if rot_state is not None:
                await state.broadcast_token_state(room, rot_state)

        frame_queue: Deque[bytes] = deque(maxlen=state.max_frame_queue)
        frame_ready = asyncio.Event()
        closed = False
        wrong_size_logged = 0
        dropped_logged = 0

        async def reader() -> None:
            nonlocal closed, wrong_size_logged, dropped_logged
            try:
                while True:
                    msg = await websocket.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    frame_bytes = msg.get("bytes")
                    if frame_bytes is None:
                        continue
                    if len(frame_bytes) != cfg.FRAME_BYTES:
                        if wrong_size_logged < 3:
                            wrong_size_logged += 1
                            logger.warning(
                                "Ignored frame size=%d room=%s pid=%s (expected %d)",
                                len(frame_bytes),
                                room_id,
                                participant_id,
                                cfg.FRAME_BYTES,
                            )
                        continue

                    entry.last_frame_mono_ms = _mono_ms()
                    if len(frame_queue) >= state.max_frame_queue and dropped_logged < 3:
                        dropped_logged += 1
                        logger.warning("Dropping oldest frame room=%s pid=%s (queue full=%d)",
                                       room_id, participant_id, state.max_frame_queue)
                    frame_queue.append(frame_bytes)
                    frame_ready.set()
                    if len(frame_queue) >= 1:
                        await asyncio.sleep(0)
            except WebSocketDisconnect:
                pass
            except Exception as exc:
                logger.debug("VAD reader closed room=%s pid=%s (%s)", room_id, participant_id, exc)
            finally:
                closed = True
                frame_ready.set()

        reader_task = asyncio.create_task(reader())
        try:
            while not closed:
                if not frame_queue:
                    frame_ready.clear()
                    if closed:
                        break
                    await frame_ready.wait()
                    continue

                frame_bytes = frame_queue.popleft()
                vad_event = entry.vad.process_frame(frame_bytes)
                if vad_event is not None:
                    await state.send_vad_event(websocket, participant_id, vad_event)
                    if not (state.mock and state.mock_rotate):
                        new_state = room.token_manager.on_vad(participant_id, vad_event, _mono_ms())
                        if new_state is not None:
                            await state.broadcast_token_state(room, new_state)
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("VAD processor closed room=%s pid=%s (%s)", room_id, participant_id, exc)
        finally:
            if not reader_task.done():
                reader_task.cancel()
                try:
                    await reader_task
                except asyncio.CancelledError:
                    pass

            current = room.streams.get(participant_id)
            if current is not None and current.conn_id == conn_id:
                room.streams.pop(participant_id, None)
                logger.info("LEAVE room=%s pid=%s", room_id, participant_id)
                if state.mock and state.mock_rotate:
                    rot_state = room.rotator.current_or_rotate(list(room.streams.keys()), _mono_ms(), force=True)
                    if rot_state is not None:
                        await state.broadcast_token_state(room, rot_state)
                else:
                    disc_state = room.token_manager.on_disconnect(participant_id, _mono_ms())
                    if disc_state is not None:
                        await state.broadcast_token_state(room, disc_state)
            state.cleanup_room_if_empty(room_id)

    @app.websocket("/ws/token/{room_id}")
    async def ws_token(websocket: WebSocket, room_id: str) -> None:
        await websocket.accept()
        room = state.get_or_create_room(room_id)
        room.subscribers.add(websocket)
        logger.info("SUBSCRIBER_JOIN room=%s total=%d", room_id, len(room.subscribers))

        try:
            initial_payload = room.current_token_payload(state.mock and state.mock_rotate)
            await websocket.send_text(json.dumps(initial_payload))
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.debug("Token subscriber closed room=%s (%s)", room_id, exc)
        finally:
            room.subscribers.discard(websocket)
            logger.info("SUBSCRIBER_LEAVE room=%s total=%d", room_id, len(room.subscribers))
            state.cleanup_room_if_empty(room_id)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=cfg.HOST, port=cfg.PORT, reload=False)
