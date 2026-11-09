"""Call Server Hub - FastAPI Implementation.

Role 2: Hub connecting Frontend (Role 1), Speech Service (Role 3), and Speaker Service (Role 4).
"""

import asyncio
import csv
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    MOCK,
    HEALTH_POLL_INTERVAL_S,
)
from rooms import RoomManager, Participant
from network_monitor import ListenerNetworkState
from clients import SpeechServiceClient, SpeakerServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("call-server")

METRICS_FILE = Path(__file__).resolve().parent / "metrics.csv"

# Initialize metrics file if needed
if not METRICS_FILE.exists():
    with open(METRICS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ts_ms", "chunk_id", "mode", "asr_ms", "mt_ms", "tts_ms", "total_ms", "network_state"])


def log_metrics(ts_ms: int, chunk_id: str, mode: str, timings: Dict[str, Any], net_state: str):
    try:
        with open(METRICS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                ts_ms,
                chunk_id,
                mode,
                timings.get("asr", 0),
                timings.get("mt", 0),
                timings.get("tts", 0),
                timings.get("total", 0),
                net_state,
            ])
    except Exception as e:
        logger.warning(f"Failed to write metric: {e}")


room_manager = RoomManager()
speech_client = SpeechServiceClient()
speaker_client = SpeakerServiceClient()


def generate_livekit_token(room_name: str, participant_identity: str, participant_name: str) -> str:
    """Generates a LiveKit JWT token using livekit-api or a dev fallback token."""
    try:
        from livekit.api import AccessToken, VideoGrants
        token = (
            AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity(participant_identity)
            .with_name(participant_name)
            .with_grants(VideoGrants(room_join=True, room=room_name))
        )
        return token.to_jwt()
    except Exception as e:
        logger.warning(f"Using fallback dev token generation ({e})")
        # Lightweight dev token fallback if native livekit-api fails
        import hmac
        import hashlib
        import base64

        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload_data = {
            "exp": int(time.time()) + 86400,
            "iss": LIVEKIT_API_KEY,
            "sub": participant_identity,
            "name": participant_name,
            "video": {"room": room_name, "roomJoin": True},
        }
        payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
        sig = hmac.new(LIVEKIT_API_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        signature = base64.urlsafe_b64encode(sig).decode().rstrip("=")
        return f"{header}.{payload}.{signature}"


async def network_evaluator_loop():
    """Periodic loop to evaluate listener network stats every 2s with hysteresis."""
    while True:
        try:
            await asyncio.sleep(2.0)
            health = await speech_client.fetch_health()
            speech_latency = float(health.get("avg_latency_ms", 950.0))

            for room in list(room_manager.rooms.values()):
                for pid, p in list(room.participants.items()):
                    stats = p.latest_net_stats
                    new_mode, changed, reason = p.net_state.record_window(
                        rtt_ms=float(stats.get("rtt_ms", 50)),
                        packet_loss_pct=float(stats.get("packet_loss_pct", 0.0)),
                        bitrate_kbps=float(stats.get("bitrate_kbps", 1000)),
                        speech_latency_ms=speech_latency,
                    )
                    if changed:
                        p.mode = new_mode
                        logger.info(f"Mode switched for {pid} to {new_mode} (reason: {reason})")
                        if p.ws:
                            await p.ws.send_json({
                                "type": "mode",
                                "mode": new_mode,
                                "reason": reason,
                            })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in network_evaluator_loop: {e}")


async def mock_gateway_loop():
    """In MOCK=1 mode, rotates active speaker and emits periodic demo translations."""
    if not MOCK:
        return
    step = 0
    while True:
        try:
            await asyncio.sleep(5.0)
            step += 1
            now_ms = int(time.time() * 1000)

            for room in list(room_manager.rooms.values()):
                pids = list(room.participants.keys())
                if not pids:
                    continue
                holder = pids[step % len(pids)]
                overlap = [p for p in pids if p != holder][:1]
                room.token_holder = holder
                room.overlap = overlap

                await room.broadcast_json({
                    "type": "active_speaker",
                    "holder": holder,
                    "overlap": overlap,
                    "ts_ms": now_ms,
                })

                # Also send a periodic mock translation
                speaker = room.participants.get(holder)
                if speaker:
                    for pid, listener in room.participants.items():
                        if pid == holder:
                            continue
                        target_lang = listener.lang or "hi"
                        await listener.ws.send_json({
                            "type": "translation",
                            "chunk_id": f"{holder}-{step}",
                            "from": holder,
                            "from_name": speaker.name,
                            "lane": "main",
                            "mode": listener.mode,
                            "src_lang": speaker.lang or "en",
                            "lang": target_lang,
                            "source_text": "Welcome to multilingual meet.",
                            "text": "मल्टीलिंगुअल मीट में आपका स्वागत है" if target_lang == "hi" else ("ಬಹುಭಾಷಾ ಸಭೆಗೆ ಸುಸ್ವಾಗತ" if target_lang == "kn" else "Welcome to multilingual meet."),
                            "audio_url": f"http://localhost:8001/audio/mock_{target_lang}.wav" if listener.mode == "audio" else None,
                            "ts_ms": now_ms,
                        })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Mock gateway loop error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    net_task = asyncio.create_task(network_evaluator_loop())
    mock_task = asyncio.create_task(mock_gateway_loop()) if MOCK else None
    yield
    net_task.cancel()
    if mock_task:
        mock_task.cancel()


app = FastAPI(title="Multilingual Meet Call Server (Role 2)", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JoinRequest(BaseModel):
    participant_id: str
    name: str
    lang: str = "en"


@app.get("/v1/health")
async def health_check():
    return {
        "status": "ok",
        "mock": MOCK,
        "rooms_count": len(room_manager.rooms),
    }


@app.post("/v1/rooms/{room_id}/join")
async def join_room(room_id: str, body: JoinRequest):
    token = generate_livekit_token(
        room_name=room_id,
        participant_identity=body.participant_id,
        participant_name=body.name,
    )
    return {
        "livekit_token": token,
        "livekit_url": LIVEKIT_URL,
    }


@app.websocket("/ws/room/{room_id}")
async def room_events_ws(websocket: WebSocket, room_id: str, participant_id: Optional[str] = None):
    await websocket.accept()
    room = await room_manager.get_or_create_room(room_id)
    current_pid = participant_id

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "hello":
                current_pid = data.get("participant_id") or current_pid
                name = data.get("name", "Guest")
                lang = data.get("lang", "en")

                participant = Participant(
                    participant_id=current_pid,
                    name=name,
                    lang=lang,
                    room_id=room_id,
                    ws=websocket,
                )
                room.participants[current_pid] = participant

                # Immediately send current mode and participants list
                await websocket.send_json({
                    "type": "mode",
                    "mode": participant.mode,
                    "reason": "initial_state",
                })
                await room.broadcast_json({
                    "type": "participants",
                    "list": room.get_participant_list(),
                })
                # Broadcast active speaker if any
                if room.token_holder:
                    await websocket.send_json({
                        "type": "active_speaker",
                        "holder": room.token_holder,
                        "overlap": room.overlap,
                        "ts_ms": int(time.time() * 1000),
                    })

            elif msg_type == "net_stats":
                if current_pid and current_pid in room.participants:
                    p = room.participants[current_pid]
                    p.latest_net_stats = {
                        "rtt_ms": data.get("rtt_ms", 50),
                        "packet_loss_pct": data.get("packet_loss_pct", 0.0),
                        "bitrate_kbps": data.get("bitrate_kbps", 1000),
                        "jitter_ms": data.get("jitter_ms", 5),
                    }

            elif msg_type == "set_lang":
                new_lang = data.get("lang")
                if current_pid and current_pid in room.participants and new_lang:
                    room.participants[current_pid].lang = new_lang
                    await room.broadcast_json({
                        "type": "participants",
                        "list": room.get_participant_list(),
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        if current_pid:
            await room_manager.remove_participant(room_id, current_pid)
            remaining_room = await room_manager.get_room(room_id)
            if remaining_room:
                await remaining_room.broadcast_json({
                    "type": "participants",
                    "list": remaining_room.get_participant_list(),
                })


async def process_and_fanout_chunk(room: Room, speaker: Participant, chunk_id: str, wav_bytes: bytes):
    """Processes speech chunk with speech service and fans out translations to listeners."""
    tgt_langs = room.get_unique_target_languages(speaker.participant_id)
    if not tgt_langs:
        return

    want_audio = room.is_any_listener_in_audio_mode(speaker.participant_id)

    speech_result = await speech_client.process_chunk(
        audio_wav_bytes=wav_bytes,
        room_id=room.room_id,
        participant_id=speaker.participant_id,
        chunk_id=chunk_id,
        src_lang=speaker.lang or "auto",
        tgt_langs=tgt_langs,
        want_audio=want_audio,
    )

    if not speech_result:
        return

    detected_lang = speech_result.get("detected_lang", speaker.lang)
    source_text = speech_result.get("source_text", "")
    translations = speech_result.get("translations", {})
    timings = speech_result.get("timings_ms", {})
    now_ms = int(time.time() * 1000)

    # Determine lane: "main" for token holder, "overlap" for others
    is_holder = (room.token_holder == speaker.participant_id)
    lane = "main" if is_holder else "overlap"

    # Log metrics
    log_metrics(
        ts_ms=now_ms,
        chunk_id=chunk_id,
        mode="audio" if want_audio else "subtitle",
        timings=timings,
        net_state="ok",
    )

    # Deliver to each listener
    for pid, listener in list(room.participants.items()):
        if pid == speaker.participant_id:
            continue  # Do not send listener their own speech
        if listener.lang == detected_lang:
            continue  # Skip if same language

        tr_entry = translations.get(listener.lang)
        if not tr_entry:
            continue

        # Overlapping talkers are always subtitle, audio_url is null
        # In audio mode, audio_url is provided only if lane is main
        audio_url = None
        if listener.mode == "audio" and lane == "main":
            audio_url = tr_entry.get("audio_url")

        msg = {
            "type": "translation",
            "chunk_id": chunk_id,
            "from": speaker.participant_id,
            "from_name": speaker.name,
            "lane": lane,
            "mode": listener.mode,
            "src_lang": detected_lang,
            "lang": listener.lang,
            "source_text": source_text,
            "text": tr_entry.get("text", ""),
            "audio_url": audio_url,
            "ts_ms": now_ms,
        }

        if listener.ws:
            try:
                await listener.ws.send_json(msg)
            except Exception:
                pass


@app.websocket("/ws/audio/{room_id}/{participant_id}")
async def audio_stream_ws(websocket: WebSocket, room_id: str, participant_id: str):
    await websocket.accept()
    room = await room_manager.get_or_create_room(room_id)
    participant = room.participants.get(participant_id)
    if not participant:
        participant = Participant(participant_id=participant_id, name="User", lang="en", room_id=room_id)
        room.participants[participant_id] = participant

    chunker = participant.chunker

    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            if len(frame_bytes) != 1024:
                logger.warning(f"Received invalid frame size {len(frame_bytes)} (expected 1024)")
                continue

            chunk_info = chunker.add_frame(frame_bytes)
            if chunk_info:
                chunk_id, wav_bytes = chunk_info
                asyncio.create_task(process_and_fanout_chunk(room, participant, chunk_id, wav_bytes))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Audio WS error for {participant_id}: {e}")
    finally:
        # Flush any trailing chunk
        trailing = chunker.on_vad_speech_end()
        if trailing:
            chunk_id, wav_bytes = trailing
            asyncio.create_task(process_and_fanout_chunk(room, participant, chunk_id, wav_bytes))
