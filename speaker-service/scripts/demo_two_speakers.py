"""Two-speaker WebSocket demo & Python test client for speaker-service.

Connects to WS /ws/token/{room}, plus two WS /ws/vad/{room}/{pid} streams
that replay a 16 kHz mono PCM16 WAV sequentially then overlapping, printing
every `vad` and `token_update` JSON message received.

Usage (with speaker-service running on port 8002):
    python scripts/demo_two_speakers.py --wav tests/fixtures/speech_sample.wav
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import wave
from pathlib import Path

import websockets

FRAME_BYTES = 1024
FRAME_S = 0.032
SILENT_FRAME = b"\x00" * FRAME_BYTES


def load_wav_frames(wav_path: Path) -> list[bytes]:
    with wave.open(str(wav_path), "rb") as wf:
        if (wf.getframerate(), wf.getnchannels(), wf.getsampwidth()) != (16000, 1, 2):
            raise SystemExit("WAV must be 16 kHz, mono, 16-bit PCM")
        raw = wf.readframes(wf.getnframes())
    return [raw[i : i + FRAME_BYTES] for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES)]


async def stream_participant(
    base_ws: str,
    room: str,
    pid: str,
    frames: list[bytes],
    delay_s: float,
    stop: asyncio.Event,
) -> None:
    url = f"{base_ws}/ws/vad/{room}/{pid}"
    async with websockets.connect(url) as ws:
        async def recv_vad():
            async for raw in ws:
                print(f"[VAD:{pid}] {raw}")

        recv_task = asyncio.create_task(recv_vad())
        try:
            t0 = time.monotonic()
            idx = 0
            next_t = t0
            while not stop.is_set():
                elapsed = time.monotonic() - t0
                if elapsed >= delay_s and idx < len(frames):
                    frame = frames[idx]
                    idx += 1
                else:
                    frame = SILENT_FRAME
                await ws.send(frame)
                next_t += FRAME_S
                wait = next_t - time.monotonic()
                if wait > 0:
                    await asyncio.sleep(wait)
        finally:
            recv_task.cancel()


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server", default="ws://localhost:8002")
    p.add_argument("--room", default="demo-room")
    p.add_argument(
        "--wav",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "speech_sample.wav",
    )
    p.add_argument("--duration", type=float, default=8.0)
    args = p.parse_args()

    frames = load_wav_frames(args.wav)
    base_ws = args.server.rstrip("/")
    stop = asyncio.Event()

    async def listen_tokens():
        async with websockets.connect(f"{base_ws}/ws/token/{args.room}") as ws:
            async for raw in ws:
                data = json.loads(raw)
                print(f"[TOKEN] holder={data['holder']} overlap={data['overlap']} ts={data['ts_ms']}")

    tok_task = asyncio.create_task(listen_tokens())
    p1_task = asyncio.create_task(stream_participant(base_ws, args.room, "p-1", frames, 0.2, stop))
    p2_task = asyncio.create_task(stream_participant(base_ws, args.room, "p-2", frames, 1.5, stop))

    await asyncio.sleep(args.duration)
    stop.set()
    await asyncio.gather(p1_task, p2_task, return_exceptions=True)
    tok_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
