"""Call Server Hub - FastAPI Implementation.

Role 2: Hub connecting Frontend (Role 1), Speech Service (Role 3), and Speaker Service (Role 4).
"""

import asyncio
import csv
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    SPEECH_SERVICE_URL,
    MOCK,
    MAX_OVERLAP,
    MAX_QUEUE_DEPTH,
)
from rooms import RoomManager, Participant, Room
from network_monitor import (
    ListenerNetworkState,
    should_want_audio,
    should_drop_overlap_for_queue,
)
from clients import SpeechServiceClient, SpeakerServiceClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("call-server")

SUPPORTED_LANGUAGES = {"en", "hi", "kn", "ta", "te", "ml", "mr"}
METRICS_FILE = Path(__file__).resolve().parent / "metrics.csv"
METRICS_INITIALIZED = False


def log_metrics(
    ts_ms: int,
    room_id: str,
    chunk_id: str,
    lane: str,
    mode: str,
    n_listeners: int,
    chunk_ms: int,
    timings: Dict[str, Any],
    speech_total_ms: int,
    e2e_ms: int,
    network_state: str,
):
    global METRICS_INITIALIZED
    try:
        write_header = False
        if not METRICS_INITIALIZED:
            if not METRICS_FILE.exists():
                write_header = True
            METRICS_INITIALIZED = True

        with open(METRICS_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow([
                    "ts_ms",
                    "room_id",
                    "chunk_id",
                    "lane",
                    "mode",
                    "n_listeners",
                    "chunk_ms",
                    "asr_ms",
                    "mt_ms",
                    "tts_ms",
                    "speech_total_ms",
                    "e2e_ms",
                    "network_state",
                ])
            writer.writerow([
                ts_ms,
                room_id,
                chunk_id,
                lane,
                mode,
                n_listeners,
                chunk_ms,
                timings.get("asr", 0),
                timings.get("mt", 0),
                timings.get("tts", 0),
                speech_total_ms,
                e2e_ms,
                network_state,
            ])
    except Exception as e:
        logger.warning(f"Failed to write metrics: {e}")


room_manager = RoomManager()
speech_client = SpeechServiceClient()
speaker_client = SpeakerServiceClient()


def generate_livekit_token(room_name: str, participant_identity: str, participant_name: str) -> str:
    """Generates a LiveKit JWT token using livekit-api or dev fallback."""
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
            now = time.time()
            health = await speech_client.fetch_health()
            speech_latency = health.get("avg_latency_ms")
            if speech_latency is not None:
                speech_latency = float(speech_latency)

            for room in list(room_manager.rooms.values()):
                for pid, p in list(room.participants.items()):
                    if p.latest_net_stats is None:
                        # Do nothing until first net_stats has arrived
                        continue

                    stats_age_s = now - p.latest_net_stats_ts
                    stats = p.latest_net_stats
                    is_first_eval = not p.net_state.has_evaluated
                    new_mode, changed, reason = p.net_state.record_window(
                        rtt_ms=float(stats.get("rtt_ms", 0)),
                        packet_loss_pct=float(stats.get("packet_loss_pct", 0.0)),
                        bitrate_kbps=float(stats.get("bitrate_kbps", 0)),
                        speech_latency_ms=speech_latency,
                        stats_age_s=stats_age_s,
                    )
                    p.mode = new_mode
                    if changed or is_first_eval:
                        logger.info(f"Mode update for {pid} to {new_mode} (reason: {reason})")
                        if p.ws:
                            try:
                                await p.ws.send_json({
                                    "type": "mode",
                                    "mode": new_mode,
                                    "reason": reason,
                                })
                            except Exception:
                                pass
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
            await asyncio.sleep(3.0)
            step += 1
            now_ms = int(time.time() * 1000)

            for room in list(room_manager.rooms.values()):
                # Ensure fake participants exist so a single tab receives translations
                if "p-asha-mock" not in room.participants:
                    room.participants["p-asha-mock"] = Participant(
                        participant_id="p-asha-mock",
                        name="Asha (mock)",
                        lang="hi",
                        room_id=room.room_id,
                    )
                if "p-ravi-mock" not in room.participants:
                    room.participants["p-ravi-mock"] = Participant(
                        participant_id="p-ravi-mock",
                        name="Ravi (mock)",
                        lang="kn",
                        room_id=room.room_id,
                    )

                pids = list(room.participants.keys())
                if not pids:
                    continue

                # Flip mode about every 15 seconds (5 steps * 3s)
                if step % 5 == 0:
                    for p in room.participants.values():
                        if p.ws:
                            new_m = "subtitle" if p.mode == "audio" else "audio"
                            p.mode = new_m
                            await p.ws.send_json({
                                "type": "mode",
                                "mode": new_m,
                                "reason": "mock_network_flip",
                            })

                # Rotate speaker every 3s
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

                speaker = room.participants.get(holder)
                if speaker:
                    for pid, listener in list(room.participants.items()):
                        if pid == holder or not listener.ws:
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
                            "audio_url": f"{SPEECH_SERVICE_URL}/audio/sample.wav" if listener.mode == "audio" else None,
                            "ts_ms": now_ms,
                        })

                # Occasionally emit an overlap-lane subtitle (no audio)
                if step % 4 == 0 and overlap:
                    ov_pid = overlap[0]
                    ov_speaker = room.participants.get(ov_pid)
                    if ov_speaker:
                        for pid, listener in list(room.participants.items()):
                            if pid == ov_pid or not listener.ws:
                                continue
                            target_lang = listener.lang or "hi"
                            await listener.ws.send_json({
                                "type": "translation",
                                "chunk_id": f"{ov_pid}-ov-{step}",
                                "from": ov_pid,
                                "from_name": ov_speaker.name,
                                "lane": "overlap",
                                "mode": listener.mode,
                                "src_lang": ov_speaker.lang or "en",
                                "lang": target_lang,
                                "source_text": "Yes, I agree with that point.",
                                "text": "हाँ, मैं उस बात से सहमत हूँ" if target_lang == "hi" else "ಹೌದು, ನಾನು ಅದನ್ನು ಒಪ್ಪುತ್ತೇನೆ",
                                "audio_url": None,
                                "ts_ms": now_ms,
                            })
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Mock gateway error: {e}")


def ensure_token_subscription(room: Room):
    """Starts room-level token subscription once if not in mock mode."""
    if MOCK:
        return
    if room.token_task is None or room.token_task.done():
        async def on_token_update(data: Dict[str, Any]):
            holder = data.get("holder")
            overlap = data.get("overlap", [])
            now_ms = data.get("ts_ms", int(time.time() * 1000))
            room.update_token_state(holder, overlap, max_overlap=MAX_OVERLAP)
            await room.broadcast_json({
                "type": "active_speaker",
                "holder": room.token_holder,
                "overlap": room.overlap,
                "ts_ms": now_ms,
            })

        room.token_task = asyncio.create_task(
            speaker_client.subscribe_tokens(room.room_id, on_token_update)
        )


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
    # FIX 7: validate supported languages
    if body.lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{body.lang}'. Supported languages are: {sorted(SUPPORTED_LANGUAGES)}",
        )

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

                # FIX 7: if participant was already created (e.g. by /ws/audio connecting first), update it!
                if current_pid in room.participants:
                    p = room.participants[current_pid]
                    p.name = name
                    p.lang = lang
                    p.ws = websocket
                    participant = p
                else:
                    participant = Participant(
                        participant_id=current_pid,
                        name=name,
                        lang=lang,
                        room_id=room_id,
                        ws=websocket,
                    )
                    room.participants[current_pid] = participant

                ensure_token_subscription(room)

                # Send initial mode and participants list
                await websocket.send_json({
                    "type": "mode",
                    "mode": participant.mode,
                    "reason": "initial_state",
                })
                await room.broadcast_json({
                    "type": "participants",
                    "list": room.get_participant_list(),
                })
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
                        "rtt_ms": float(data.get("rtt_ms", 50)),
                        "packet_loss_pct": float(data.get("packet_loss_pct", 0.0)),
                        "bitrate_kbps": float(data.get("bitrate_kbps", 1000)),
                        "jitter_ms": float(data.get("jitter_ms", 5)),
                    }
                    p.latest_net_stats_ts = time.time()

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


async def process_and_fanout_chunk(
    room: Room,
    speaker: Participant,
    chunk_id: str,
    wav_bytes: bytes,
    chunk_cut_time: float,
):
    """Processes speech chunk with speech service and fans out translations according to contract."""
    # FIX 5: Lane comes from speaker's current lane at chunk time
    lane = speaker.lane
    if lane is None and MOCK:
        lane = "main" if room.token_holder == speaker.participant_id else "overlap"

    # Only translate lane "main" and "overlap"; drop chunks whose speaker has no lane
    if lane not in ("main", "overlap"):
        logger.info(f"Dropping chunk {chunk_id}: speaker {speaker.participant_id} has no valid lane ({lane})")
        return

    # In-flight queue check: drop OVERLAP chunks first if queue overloaded
    if should_drop_overlap_for_queue(
        lane=lane,
        in_flight=room.in_flight_speech_calls,
        queue_depth=speech_client.queue_depth,
        max_queue_depth=MAX_QUEUE_DEPTH,
    ):
        logger.warning(
            f"Dropping OVERLAP chunk {chunk_id}: room in-flight={room.in_flight_speech_calls}, speech queue={speech_client.queue_depth}"
        )
        return

    # Unique target languages in the room, excluding speaker's language
    tgt_langs = [l for l in room.get_unique_target_languages(speaker.participant_id) if l != speaker.lang]
    if not tgt_langs:
        return

    # want_audio is True ONLY for MAIN lane AND at least one listener is in audio mode
    is_any_audio = room.is_any_listener_in_audio_mode(speaker.participant_id)
    want_audio = should_want_audio(lane, is_any_audio)

    # Call speech service once per chunk
    room.in_flight_speech_calls += 1
    t0_speech = time.time()
    try:
        speech_result = await speech_client.process_chunk(
            audio_wav_bytes=wav_bytes,
            room_id=room.room_id,
            participant_id=speaker.participant_id,
            chunk_id=chunk_id,
            src_lang=speaker.lang or "auto",
            tgt_langs=tgt_langs,
            want_audio=want_audio,
        )
    finally:
        room.in_flight_speech_calls = max(0, room.in_flight_speech_calls - 1)

    if not speech_result:
        return

    detected_lang = speech_result.get("detected_lang", speaker.lang)
    source_text = speech_result.get("source_text", "")
    translations = speech_result.get("translations", {})
    timings = speech_result.get("timings_ms", {})
    speech_total_ms = int((time.time() - t0_speech) * 1000)
    now_ms = int(time.time() * 1000)

    delivered_count = 0
    audio_listeners = 0
    sub_listeners = 0

    # Deliver to each listener
    for pid, listener in list(room.participants.items()):
        if pid == speaker.participant_id:
            continue
        if listener.lang == detected_lang:
            continue

        if listener.mode == "audio":
            audio_listeners += 1
        else:
            sub_listeners += 1

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
                delivered_count += 1
            except Exception:
                pass

    e2e_ms = int((time.time() - chunk_cut_time) * 1000)
    chunk_ms = max(0, (len(wav_bytes) - 44) // 32)
    net_state_str = f"{audio_listeners}audio/{sub_listeners}subtitle"

    # Log to metrics.csv
    log_metrics(
        ts_ms=now_ms,
        room_id=room.room_id,
        chunk_id=chunk_id,
        lane=lane,
        mode="audio" if want_audio else "subtitle",
        n_listeners=delivered_count,
        chunk_ms=chunk_ms,
        timings=timings,
        speech_total_ms=speech_total_ms,
        e2e_ms=e2e_ms,
        network_state=net_state_str,
    )


@app.websocket("/ws/audio/{room_id}/{participant_id}")
async def audio_stream_ws(websocket: WebSocket, room_id: str, participant_id: str):
    await websocket.accept()
    room = await room_manager.get_or_create_room(room_id)

    # FIX 7: reuse existing participant if created via room socket or previous audio socket
    participant = room.participants.get(participant_id)
    if not participant:
        participant = Participant(participant_id=participant_id, name="User", lang="en", room_id=room_id)
        room.participants[participant_id] = participant

    chunker = participant.chunker
    ensure_token_subscription(room)

    vad_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    vad_task: Optional[asyncio.Task] = None

    # FIX 3: VAD forwarding client when MOCK=0
    if not MOCK:
        async def on_vad_state(state: str):
            if state == "speech_start":
                chunker.on_vad_speech_start()
            elif state == "speech_end":
                chunk_info = chunker.on_vad_speech_end()
                if chunk_info:
                    cid, wav_bytes = chunk_info
                    asyncio.create_task(
                        process_and_fanout_chunk(room, participant, cid, wav_bytes, time.time())
                    )

        vad_task = asyncio.create_task(
            speaker_client.forward_vad_stream(room_id, participant_id, vad_queue, on_vad_state)
        )

    wrong_size_count = 0

    try:
        while True:
            # FIX 7: use websocket.receive() to gracefully ignore text frames
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" not in message:
                continue

            frame_bytes = message["bytes"]
            if len(frame_bytes) != 1024:
                wrong_size_count += 1
                if wrong_size_count <= 3:
                    logger.warning(
                        f"Ignored frame of size {len(frame_bytes)} from {participant_id} (expected 1024)"
                    )
                continue

            # Forward to VAD queue (drop if full so loop never blocks)
            if not MOCK:
                try:
                    vad_queue.put_nowait(frame_bytes)
                except asyncio.QueueFull:
                    pass

            chunk_info = chunker.add_frame(frame_bytes)
            if chunk_info:
                chunk_id, wav_bytes = chunk_info
                asyncio.create_task(
                    process_and_fanout_chunk(room, participant, chunk_id, wav_bytes, time.time())
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Audio WS error for {participant_id}: {e}")
    finally:
        if vad_task:
            vad_task.cancel()
        trailing = chunker.on_vad_speech_end()
        if trailing:
            chunk_id, wav_bytes = trailing
            asyncio.create_task(
                process_and_fanout_chunk(room, participant, chunk_id, wav_bytes, time.time())
            )
        # Clean up leftover participant if hello never arrived
        if participant.name == "User" and participant.ws is None:
            await room_manager.remove_participant(room_id, participant_id)
