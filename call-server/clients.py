import httpx
import logging
from typing import List, Optional
from config import SPEECH_SERVICE_URL

logger = logging.getLogger("call-server.clients")

class SpeechServiceClient:
    def __init__(self, base_url: str = SPEECH_SERVICE_URL, timeout_sec: float = 6.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec

    async def get_health(self) -> dict:
        async with httpx.AsyncClient(timeout=2.0) as client:
            try:
                resp = await client.get(f"{self.base_url}/v1/health")
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.warning(f"Speech service health check failed: {e}")
        return {"status": "unreachable", "queue_depth": 0, "avg_latency_ms": 9999}

    async def process_chunk(
        self,
        audio_wav: bytes,
        room_id: str,
        participant_id: str,
        chunk_id: str,
        src_lang: str,
        tgt_langs: List[str],
        want_audio: bool,
        prev_text: Optional[str] = None
    ) -> Optional[dict]:
        import json
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            try:
                files = {"audio": ("chunk.wav", audio_wav, "audio/wav")}
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

                resp = await client.post(f"{self.base_url}/v1/process-chunk", data=data, files=files)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    logger.warning(f"Speech service busy (429) for chunk {chunk_id}")
                else:
                    logger.error(f"Speech service error {resp.status_code}: {resp.text}")
            except httpx.TimeoutException:
                logger.error(f"Speech service timeout (> {self.timeout_sec}s) for chunk {chunk_id}. Dropping chunk.")
            except Exception as e:
                logger.error(f"Failed to process chunk via speech service: {e}")
        return None
