import asyncio
import json
import logging
import os
import time
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONFIG, MOCK_MODE, SPEECH_SERVICE_URL
from rooms import Participant, Room
from clients import SpeechServiceClient
from chunker import AudioChunker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("call-server")

app = FastAPI(
    title="Call Server Hub (Role 2)",
    version="0.1.0",
    description="Hub and Network Monitor for Multilingual Video Conferencing"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registry
rooms: Dict[str, Room] = {}
chunkers: Dict[str, AudioChunker] = {}
speech_client = SpeechServiceClient()

def get_or_create_room(room_id: str) -> Room:
    if room_id not in rooms:
        rooms[room_id] = Room(room_id)
    return rooms[room_id]

class JoinRequest(BaseModel):
    participant_id: str
    name: str
    lang: str = "en"

class JoinResponse(BaseModel):
    livekit_token: str
    livekit_url: str

@app.get("/v1/health")
async def health():
    return {
        "status": "ok",
        "mock": MOCK_MODE,
        "rooms": len(rooms),
        "service": "call-server"
    }

@app.post("/v1/rooms/{room_id}/join", response_model=JoinResponse)
async def join_room(room_id: str, req: JoinRequest):
    """
    Contract A4: Issues LiveKit token and URL.
    """
    room = get_or_create_room(room_id)
    p = Participant(req.participant_id, req.name, req.lang)
    room.add_participant(p)

    # In dev/mock mode, issue placeholder token
    fake_token = f"mock-token-{room_id}-{req.participant_id}"
    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    return JoinResponse(livekit_token=fake_token, livekit_url=livekit_url)

@app.websocket("/ws/room/{room_id}")
async def room_events_socket(websocket: WebSocket, room_id: str, participant_id: str):
    """
    Contract A4: JSON event socket for room coordination and network stats.
    """
    await websocket.accept()
    room = get_or_create_room(room_id)
    participant = room.participants.get(participant_id)
    if not participant:
        participant = Participant(participant_id, name="User", lang="en")
        room.add_participant(participant)
    participant.room_socket = websocket

    # Broadcast updated participant list
    async def broadcast_participants():
        plist = {"type": "participants", "list": room.get_participants_list()}
        for p in list(room.participants.values()):
            if p.room_socket:
                try:
                    await p.room_socket.send_text(json.dumps(plist))
                except Exception:
                    pass

    await broadcast_participants()

    # If MOCK=1, run periodic mock generator
    async def mock_generator():
        while MOCK_MODE:
            await asyncio.sleep(4.0)
            if websocket.client_state.name != "CONNECTED":
                break
            ts_ms = int(time.time() * 1000)
            # Periodic mock active speaker
            active_speaker_msg = {
                "type": "active_speaker",
                "holder": participant_id,
                "overlap": [],
                "ts_ms": ts_ms
            }
            # Periodic mock translation
            translation_msg = {
                "type": "translation",
                "chunk_id": f"{participant_id}-mock",
                "from": participant_id,
                "from_name": participant.name,
                "lane": "main",
                "mode": participant.net_state.current_mode,
                "src_lang": "en",
                "lang": participant.lang,
                "source_text": "Hello, welcome to multilingual meet.",
                "text": "नमस्ते, बहुभाषी बैठक में आपका स्वागत है।",
                "audio_url": f"{SPEECH_SERVICE_URL}/audio/sample.wav" if participant.net_state.current_mode == "audio" else None,
                "ts_ms": ts_ms
            }
            try:
                await websocket.send_text(json.dumps(active_speaker_msg))
                await websocket.send_text(json.dumps(translation_msg))
            except Exception:
                break

    mock_task = asyncio.create_task(mock_generator()) if MOCK_MODE else None

    try:
        while True:
            text = await websocket.receive_text()
            data = json.loads(text)
            msg_type = data.get("type")

            if msg_type == "hello":
                participant.name = data.get("name", participant.name)
                participant.lang = data.get("lang", participant.lang)
                await broadcast_participants()

            elif msg_type == "set_lang":
                participant.lang = data.get("lang", participant.lang)
                await broadcast_participants()

            elif msg_type == "net_stats":
                # Evaluate network state
                rtt = float(data.get("rtt_ms", 100))
                loss = float(data.get("packet_loss_pct", 0.0))
                bitrate = float(data.get("bitrate_kbps", 800))
                speech_health = await speech_client.get_health()
                speech_lat = float(speech_health.get("avg_latency_ms", 800))

                new_mode = participant.net_state.update(rtt, loss, bitrate, speech_lat)
                if new_mode:
                    mode_event = {
                        "type": "mode",
                        "mode": new_mode,
                        "reason": "network_eval"
                    }
                    await websocket.send_text(json.dumps(mode_event))

    except WebSocketDisconnect:
        logger.info(f"Room socket disconnected: {participant_id}")
    finally:
        if mock_task:
            mock_task.cancel()
        room.remove_participant(participant_id)
        await broadcast_participants()

@app.websocket("/ws/audio/{room_id}/{participant_id}")
async def audio_stream_socket(websocket: WebSocket, room_id: str, participant_id: str):
    """
    Contract A4: Receives continuous 1024-byte mic PCM frames.
    Buffers and chunks into WAV, then fans out to Speech Service.
    """
    await websocket.accept()
    room = get_or_create_room(room_id)
    key = f"{room_id}:{participant_id}"
    chunker = chunkers.setdefault(key, AudioChunker(participant_id))

    try:
        while True:
            frame = await websocket.receive_bytes()
            wav_chunk = chunker.add_frame(frame)
            if wav_chunk:
                chunk_id = chunker.next_chunk_id()
                tgt_langs = room.get_unique_target_languages(participant_id)
                want_audio = room.any_listener_wants_audio(participant_id)
                speaker = room.participants.get(participant_id)
                src_lang = speaker.lang if speaker else "en"

                # Async call to speech service
                asyncio.create_task(
                    dispatch_chunk_to_speech(
                        room=room,
                        speaker_id=participant_id,
                        chunk_id=chunk_id,
                        wav_data=wav_chunk,
                        src_lang=src_lang,
                        tgt_langs=tgt_langs,
                        want_audio=want_audio
                    )
                )
    except WebSocketDisconnect:
        logger.info(f"Audio stream closed: {participant_id}")
        chunkers.pop(key, None)

async def dispatch_chunk_to_speech(
    room: Room,
    speaker_id: str,
    chunk_id: str,
    wav_data: bytes,
    src_lang: str,
    tgt_langs: list,
    want_audio: bool
):
    if not tgt_langs:
        return

    result = await speech_client.process_chunk(
        audio_wav=wav_data,
        room_id=room.room_id,
        participant_id=speaker_id,
        chunk_id=chunk_id,
        src_lang=src_lang,
        tgt_langs=tgt_langs,
        want_audio=want_audio
    )
    if not result:
        return

    translations = result.get("translations", {})
    speaker = room.participants.get(speaker_id)
    speaker_name = speaker.name if speaker else "Unknown"
    is_holder = (room.token_holder == speaker_id)
    lane = "main" if is_holder else "overlap"
    ts_ms = int(time.time() * 1000)

    # Broadcast to each listener in their language
    for p in room.participants.values():
        if p.participant_id == speaker_id or p.lang == src_lang:
            continue
        trans_info = translations.get(p.lang)
        if not trans_info:
            continue

        listener_mode = p.net_state.current_mode
        # If in subtitle mode or in overlap lane, audio_url is null
        audio_url = trans_info.get("audio_url") if (listener_mode == "audio" and lane == "main") else None

        event = {
            "type": "translation",
            "chunk_id": chunk_id,
            "from": speaker_id,
            "from_name": speaker_name,
            "lane": lane,
            "mode": listener_mode,
            "src_lang": src_lang,
            "lang": p.lang,
            "source_text": result.get("source_text", ""),
            "text": trans_info.get("text", ""),
            "audio_url": audio_url,
            "ts_ms": ts_ms
        }
        if p.room_socket:
            try:
                await p.room_socket.send_text(json.dumps(event))
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
