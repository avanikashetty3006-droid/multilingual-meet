"""Load testing & simulation bot client.

Spawns N concurrent participant bots that join a room, send periodic network stats,
and stream simulated mic PCM frames.
"""

import asyncio
import json
import random
import sys
import websockets

async def run_bot(room_id: str, bot_id: str, name: str, lang: str, base_url: str = "ws://localhost:8000"):
    room_ws_url = f"{base_url}/ws/room/{room_id}?participant_id={bot_id}"
    audio_ws_url = f"{base_url}/ws/audio/{room_id}/{bot_id}"

    print(f"[{bot_id}] Connecting to room {room_id} as {name} ({lang})...")

    async def handle_room_events(ws):
        # 1. Send hello
        await ws.send(json.dumps({
            "type": "hello",
            "participant_id": bot_id,
            "name": name,
            "lang": lang,
        }))

        # 2. Periodic net_stats every 2s
        while True:
            await asyncio.sleep(2.0)
            stats = {
                "type": "net_stats",
                "rtt_ms": random.randint(40, 110),
                "packet_loss_pct": round(random.uniform(0.1, 1.2), 1),
                "bitrate_kbps": random.randint(700, 1200),
                "jitter_ms": random.randint(3, 10),
            }
            await ws.send(json.dumps(stats))

    async def handle_audio_stream(ws):
        # Send 512-sample PCM16 silent/noise frames (1024 bytes) every 32ms
        dummy_frame = b"\x00" * 1024
        while True:
            await ws.send(dummy_frame)
            await asyncio.sleep(0.032)

    try:
        async with websockets.connect(room_ws_url) as r_ws, websockets.connect(audio_ws_url) as a_ws:
            await asyncio.gather(
                handle_room_events(r_ws),
                handle_audio_stream(a_ws),
            )
    except Exception as e:
        print(f"[{bot_id}] Stopped: {e}")

async def main(num_bots: int = 4, room_id: str = "stress-room"):
    languages = ["en", "hi", "kn", "ta", "te"]
    tasks = []
    for i in range(num_bots):
        bot_id = f"bot-{i+1}"
        name = f"Bot {i+1}"
        lang = languages[i % len(languages)]
        tasks.append(run_bot(room_id, bot_id, name, lang))

    print(f"Starting {num_bots} bots in {room_id}...")
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    asyncio.run(main(count))
