"""HTTP and WebSocket client interfaces to Speech Service (Role 3) and Speaker Service (Role 4)."""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
import httpx
import websockets
from config import (
    SPEECH_SERVICE_URL,
    SPEAKER_SERVICE_URL,
    SPEECH_SERVICE_TIMEOUT_S,
    MOCK,
)

logger = logging.getLogger("call-server.clients")


class SpeechServiceClient:
    def __init__(self, base_url: str = SPEECH_SERVICE_URL):
        self.base_url = base_url.rstrip("/")
        self.avg_latency_ms: float = 950.0
        self.queue_depth: int = 0

    async def fetch_health(self) -> Dict[str, Any]:
        """Polls GET /v1/health from the speech service."""
        if MOCK:
            self.avg_latency_ms = 850.0
            return {"status": "ok", "queue_depth": 0, "avg_latency_ms": self.avg_latency_ms, "device": "cpu"}
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{self.base_url}/v1/health")
                if res.status_code == 200:
                    data = res.json()
                    self.avg_latency_ms = float(data.get("avg_latency_ms", 950.0))
                    self.queue_depth = int(data.get("queue_depth", 0))
                    return data
        except Exception as e:
            logger.warning(f"Speech service health check failed: {e}")
        return {"status": "unreachable", "queue_depth": self.queue_depth, "avg_latency_ms": self.avg_latency_ms}

    async def process_chunk(
        self,
        audio_wav_bytes: bytes,
        room_id: str,
        participant_id: str,
        chunk_id: str,
        src_lang: str,
        tgt_langs: List[str],
        want_audio: bool,
        prev_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Sends POST /v1/process-chunk as multipart/form-data."""
        if MOCK:
            await asyncio.sleep(0.3)
            # Produce mock canned translations as required by contract
            canned = {
                "hi": {"text": "सभी को नमस्कार", "audio_url": f"{self.base_url}/audio/mock_hi.wav" if want_audio else None},
                "kn": {"text": "ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ", "audio_url": f"{self.base_url}/audio/mock_kn.wav" if want_audio else None},
                "en": {"text": "Hello everyone", "audio_url": f"{self.base_url}/audio/mock_en.wav" if want_audio else None},
            }
            translations = {}
            for lang in tgt_langs:
                translations[lang] = canned.get(lang, {"text": f"[{lang}] Translated text", "audio_url": None})
            return {
                "chunk_id": chunk_id,
                "participant_id": participant_id,
                "detected_lang": "en" if src_lang == "auto" else src_lang,
                "source_text": "Hello everyone, speaking here.",
                "translations": translations,
                "timings_ms": {"asr": 300, "mt": 150, "tts": 250 if want_audio else 0, "total": 700 if want_audio else 450},
            }

        data = {
            "room_id": room_id,
            "participant_id": participant_id,
            "chunk_id": chunk_id,
            "src_lang": src_lang,
            "tgt_langs": json.dumps(tgt_langs),
            "want_audio": "true" if want_audio else "false",
        }
        if prev_text:
            data["prev_text"] = prev_text

        files = {"audio": (f"{chunk_id}.wav", audio_wav_bytes, "audio/wav")}

        try:
            async with httpx.AsyncClient(timeout=SPEECH_SERVICE_TIMEOUT_S) as client:
                res = await client.post(f"{self.base_url}/v1/process-chunk", data=data, files=files)
                if res.status_code == 200:
                    return res.json()
                logger.error(f"Speech service error {res.status_code}: {res.text}")
        except Exception as e:
            logger.error(f"Speech service call timed out or failed: {e}")
        return None


class SpeakerServiceClient:
    def __init__(self, base_url: str = SPEAKER_SERVICE_URL):
        self.base_url = base_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")

    async def connect_vad_stream(self, room_id: str, participant_id: str, on_vad_event):
        """Maintains WS /ws/vad/{room}/{pid} connection and feeds VAD events."""
        ws_url = f"{self.base_url}/ws/vad/{room_id}/{participant_id}"
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info(f"Connected to VAD service for {participant_id}")
                    async for msg in ws:
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            await on_vad_event(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"VAD stream connection retry in 2s ({e})")
                await asyncio.sleep(2.0)

    async def subscribe_tokens(self, room_id: str, on_token_update):
        """Subscribes to WS /ws/token/{room} and listens for token_update events."""
        ws_url = f"{self.base_url}/ws/token/{room_id}"
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    logger.info(f"Subscribed to token updates for room {room_id}")
                    async for msg in ws:
                        if isinstance(msg, str):
                            data = json.loads(msg)
                            await on_token_update(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Token update connection retry in 2s ({e})")
                await asyncio.sleep(2.0)
