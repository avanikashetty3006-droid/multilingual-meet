"""
Load Test Bot Generator (20+ participant rooms)
Simulates participants joining, streaming mic frames, and reporting net_stats.
"""
import asyncio
import json
import websockets

CALL_SERVER_WS = "ws://localhost:8000/ws/room"

async def simulate_bot(room_id: str, bot_id: str, name: str, lang: str):
    url = f"{CALL_SERVER_WS}/{room_id}?participant_id={bot_id}"
    try:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps({"type": "hello", "participant_id": bot_id, "name": name, "lang": lang}))
            print(f"[{bot_id}] Joined room {room_id} as {name} ({lang})")

            while True:
                await ws.send(json.dumps({
                    "type": "net_stats",
                    "rtt_ms": 110,
                    "packet_loss_pct": 0.2,
                    "bitrate_kbps": 750,
                    "jitter_ms": 8
                }))
                await asyncio.sleep(2.0)
    except Exception as e:
        print(f"[{bot_id}] Disconnected: {e}")

async def main():
    room = "test-room"
    bots = [
        simulate_bot(room, f"bot-{i}", f"Bot{i}", ["en", "hi", "kn"][i % 3])
        for i in range(10)
    ]
    await asyncio.gather(*bots)

if __name__ == "__main__":
    asyncio.run(main())
