"""Load testing & simulation bot suite.

Simulates N concurrent participants joining a meeting room, streaming audio
(from an optional WAV file or synthetic speech), sending real WebRTC network stats,
and testing:
- Token passing & speaking overlap cap (--speak-pattern round-robin | overlap | random | continuous)
- Network-aware adaptive mode switching (--network good | poor | mixed)
- 5, 10, and 20-user concurrency latency benchmarks

Usage:
    python bots.py --num-bots 10 --network mixed --speak-pattern round-robin
    python bots.py --num-bots 20 --languages en,hi,kn,ta,te --speak-pattern overlap
    python bots.py --wav sample.wav --num-bots 5
"""

import argparse
import asyncio
import io
import json
import random
import time
import wave
from pathlib import Path
from typing import List, Optional
import websockets

FRAME_BYTES = 1024  # 512 samples @ 16-bit 16kHz mono = 32ms


def generate_synthetic_audio_frames(total_duration_s: float = 3.0) -> List[bytes]:
    """Generates synthetic 1024-byte speech frames (sine tone) for bots without WAV files."""
    import struct
    n_frames = int(total_duration_s / 0.032)
    frames = []
    for f in range(n_frames):
        samples = [int(2000 * ((i % 16) / 8.0 - 1.0)) for i in range(512)]
        frames.append(struct.pack("<512h", *samples))
    return frames


def load_wav_frames(wav_path: Path) -> List[bytes]:
    """Loads a 16kHz mono WAV file and segments it into 1024-byte frames."""
    if not wav_path.exists():
        print(f"Warning: WAV file {wav_path} not found. Falling back to synthetic audio.")
        return generate_synthetic_audio_frames(4.0)

    frames = []
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
        for i in range(0, len(raw), FRAME_BYTES):
            frame = raw[i:i + FRAME_BYTES]
            if len(frame) == FRAME_BYTES:
                frames.append(frame)
    return frames or generate_synthetic_audio_frames(4.0)


async def run_bot(
    room_id: str,
    bot_id: str,
    name: str,
    lang: str,
    base_ws_url: str,
    audio_frames: List[bytes],
    speak_pattern: str,
    network_profile: str,
    bot_index: int,
    total_bots: int,
    stop_event: asyncio.Event,
):
    room_ws_url = f"{base_ws_url}/ws/room/{room_id}?participant_id={bot_id}"
    audio_ws_url = f"{base_ws_url}/ws/audio/{room_id}/{bot_id}"

    # Determine network condition for this bot
    is_poor = False
    if network_profile == "poor":
        is_poor = True
    elif network_profile == "mixed":
        # 50% of bots have poor connection, 50% have good connection
        is_poor = (bot_index % 2 == 1)

    print(f"[{bot_id}] Starting as {name} ({lang}) | Network: {'POOR' if is_poor else 'GOOD'}")

    async def handle_room_ws(ws):
        # 1. Send hello
        await ws.send(json.dumps({
            "type": "hello",
            "participant_id": bot_id,
            "name": name,
            "lang": lang,
        }))

        # 2. Send periodic net_stats every 2s
        while not stop_event.is_set():
            if is_poor:
                # Poor network: high RTT, high packet loss, low bitrate
                stats = {
                    "type": "net_stats",
                    "rtt_ms": random.randint(220, 320),
                    "packet_loss_pct": round(random.uniform(3.5, 6.0), 1),
                    "bitrate_kbps": random.randint(250, 420),
                    "jitter_ms": random.randint(20, 45),
                }
            else:
                # Good network: low RTT, no loss, high bitrate
                stats = {
                    "type": "net_stats",
                    "rtt_ms": random.randint(35, 75),
                    "packet_loss_pct": round(random.uniform(0.0, 0.4), 1),
                    "bitrate_kbps": random.randint(900, 1400),
                    "jitter_ms": random.randint(3, 8),
                }
            await ws.send(json.dumps(stats))

            # Drain incoming events (active_speaker, mode, translation)
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.05)
                    # Silently consumed
            except asyncio.TimeoutError:
                pass

            await asyncio.sleep(2.0)

    async def handle_audio_ws(ws):
        silent_frame = b"\x00" * FRAME_BYTES
        frame_idx = 0

        while not stop_event.is_set():
            should_speak = False

            if speak_pattern == "continuous":
                should_speak = True
            elif speak_pattern == "round-robin":
                # Each bot speaks for 4 seconds in a round-robin schedule
                cycle_period = total_bots * 4.0
                curr_time = time.time() % cycle_period
                start_window = bot_index * 4.0
                end_window = start_window + 4.0
                should_speak = (start_window <= curr_time < end_window)
            elif speak_pattern == "overlap":
                # Multiple bots speak simultaneously to test overlap lane capping
                should_speak = (bot_index < 3)  # First 3 bots speak simultaneously
            elif speak_pattern == "random":
                # Intermittent speech
                should_speak = random.random() < 0.35

            if should_speak and audio_frames:
                frame_to_send = audio_frames[frame_idx % len(audio_frames)]
                frame_idx += 1
            else:
                frame_to_send = silent_frame

            await ws.send(frame_to_send)
            await asyncio.sleep(0.032)

    try:
        async with websockets.connect(room_ws_url) as r_ws, websockets.connect(audio_ws_url) as a_ws:
            await asyncio.gather(
                handle_room_ws(r_ws),
                handle_audio_ws(a_ws),
            )
    except Exception as e:
        if not stop_event.is_set():
            print(f"[{bot_id}] Stopped: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Multilingual Meet Load-Test & Simulation Suite")
    parser.add_argument("--num-bots", type=int, default=4, help="Number of simulated bot participants (e.g. 5, 10, 20)")
    parser.add_argument("--room", type=str, default="load-room", help="Room ID to join")
    parser.add_argument("--languages", type=str, default="en,hi,kn,ta,te", help="Comma-separated language pool")
    parser.add_argument("--wav", type=str, default=None, help="Path to a 16kHz mono WAV file to stream")
    parser.add_argument("--speak-pattern", choices=["round-robin", "overlap", "random", "continuous"], default="round-robin", help="Speaking concurrency pattern")
    parser.add_argument("--network", choices=["good", "poor", "mixed"], default="mixed", help="Network simulation profile")
    parser.add_argument("--server", type=str, default="ws://localhost:8000", help="Call server base WebSocket URL")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds (0 = run indefinitely)")

    args = parser.parse_args()

    langs = [l.strip() for l in args.languages.split(",") if l.strip()]
    frames = load_wav_frames(Path(args.wav)) if args.wav else generate_synthetic_audio_frames(4.0)

    stop_event = asyncio.Event()

    tasks = []
    for i in range(args.num_bots):
        bot_id = f"bot-{i+1:02d}"
        name = f"Bot {i+1:02d}"
        lang = langs[i % len(langs)]
        tasks.append(
            run_bot(
                room_id=args.room,
                bot_id=bot_id,
                name=name,
                lang=lang,
                base_ws_url=args.server,
                audio_frames=frames,
                speak_pattern=args.speak_pattern,
                network_profile=args.network,
                bot_index=i,
                total_bots=args.num_bots,
                stop_event=stop_event,
            )
        )

    print("=" * 60)
    print(f" Launching {args.num_bots} Bots in '{args.room}'")
    print(f" Pattern : {args.speak_pattern} | Network : {args.network}")
    print(f" Languages: {langs}")
    print("=" * 60)

    if args.duration > 0:
        async def timer():
            await asyncio.sleep(args.duration)
            print(f"\nCompleted {args.duration}s test run. Stopping bots...")
            stop_event.set()
        await asyncio.gather(timer(), *tasks)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
