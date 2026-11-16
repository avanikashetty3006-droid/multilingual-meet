"""Load testing & simulation bots (replacement for load-test/bots.py).

Each bot opens the same two WebSockets a browser opens:
  /ws/room/{room}?participant_id=...   JSON: hello + net_stats every 2 s, receives events (counted)
  /ws/audio/{room}/{participant_id}    binary 1024-byte PCM frames, paced in real time (32 ms each)

The bots join the CALL SERVER only (not the LiveKit video call), so they fill the participant list
but create no video tiles.

Examples:
    python bots.py --num-bots 5  --wav speech16k.wav --duration 60
    python bots.py --users 20 --languages en,hi,kn --speak-pattern overlap --overlap-count 6 --wav speech16k.wav
    python bots.py --num-bots 10 --network mixed --wav speech16k.wav

The WAV must be 16 kHz, mono, 16-bit PCM:
    ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 speech16k.wav
"""
import argparse
import asyncio
import json
import random
import sys
import time
import wave
from collections import Counter
from pathlib import Path
from typing import List

FRAME_BYTES = 1024          # 512 samples * 2 bytes = 32 ms
FRAME_S = 0.032
SILENT_FRAME = b"\x00" * FRAME_BYTES
FFMPEG_HINT = "ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 speech16k.wav"


# --------------------------------------------------------------------------- audio
def generate_synthetic_audio_frames(total_duration_s: float = 4.0) -> List[bytes]:
    """Sawtooth tone. A real VAD will NOT treat this as speech: use --wav for real tests."""
    import struct
    n_frames = int(total_duration_s / FRAME_S)
    frames = []
    for _ in range(n_frames):
        samples = [int(2000 * ((i % 16) / 8.0 - 1.0)) for i in range(512)]
        frames.append(struct.pack("<512h", *samples))
    return frames


def load_wav_frames(wav_path: Path) -> List[bytes]:
    """Read a 16 kHz mono PCM16 WAV into 1024-byte frames. Exits with a clear message if it is not."""
    if not wav_path.exists():
        sys.exit(f"WAV file not found: {wav_path}")
    with wave.open(str(wav_path), "rb") as wf:
        fmt = (wf.getframerate(), wf.getnchannels(), wf.getsampwidth())
        if fmt != (16000, 1, 2):
            sys.exit(
                f"WAV must be 16 kHz, mono, 16-bit PCM (got {fmt[0]} Hz, {fmt[1]} channel(s), {fmt[2] * 8}-bit).\n"
                f"Convert it with:\n  {FFMPEG_HINT}")
        raw = wf.readframes(wf.getnframes())
    frames = [raw[i:i + FRAME_BYTES] for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES)]
    if not frames:
        sys.exit("WAV file is too short (needs at least 32 ms of audio).")
    return frames


# --------------------------------------------------------------------------- behaviour (pure, testable)
def should_speak(pattern: str, bot_index: int, total_bots: int, elapsed_s: float,
                 overlap_count: int = 3, slot_s: float = 4.0, rng=random) -> bool:
    if pattern == "continuous":
        return True
    if pattern == "round-robin":
        return int(elapsed_s // slot_s) % total_bots == bot_index
    if pattern == "overlap":
        return bot_index < overlap_count          # the first N bots all talk at the same time
    if pattern == "random":
        return rng.random() < 0.35
    return False


def net_stats(poor: bool, rng=random) -> dict:
    if poor:
        return {"type": "net_stats", "rtt_ms": rng.randint(300, 450),
                "packet_loss_pct": round(rng.uniform(3.5, 6.0), 1),
                "bitrate_kbps": rng.randint(150, 400), "jitter_ms": rng.randint(30, 80)}
    return {"type": "net_stats", "rtt_ms": rng.randint(35, 75),
            "packet_loss_pct": round(rng.uniform(0.0, 0.4), 1),
            "bitrate_kbps": rng.randint(900, 1400), "jitter_ms": rng.randint(3, 8)}


def is_poor_bot(profile: str, bot_index: int) -> bool:
    return profile == "poor" or (profile == "mixed" and bot_index % 2 == 1)


# --------------------------------------------------------------------------- bot
async def run_bot(args, bot_index: int, lang: str, frames: List[bytes], stats: Counter,
                  stop: asyncio.Event) -> None:
    import websockets                                   # imported here so the helpers above work without it

    bot_id = f"bot-{bot_index + 1:02d}"
    poor = is_poor_bot(args.network, bot_index)
    base = args.server.rstrip("/")
    room_url = f"{base}/ws/room/{args.room}?participant_id={bot_id}"
    audio_url = f"{base}/ws/audio/{args.room}/{bot_id}"
    t0 = time.monotonic()
    print(f"[{bot_id}] {lang} | network {'POOR' if poor else 'GOOD'}")

    async def room_sender(ws):
        await ws.send(json.dumps({"type": "hello", "participant_id": bot_id,
                                  "name": f"Bot {bot_index + 1:02d}", "lang": lang}))
        while not stop.is_set():
            await ws.send(json.dumps(net_stats(poor)))
            await asyncio.sleep(2.0)

    async def room_receiver(ws):
        async for raw in ws:                            # read continuously and count what arrives
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            kind = msg.get("type", "?")
            stats[f"msg_{kind}"] += 1
            if kind == "translation":
                stats[f"translation_lane_{msg.get('lane')}"] += 1
                stats[f"translation_mode_{msg.get('mode')}"] += 1
                if poor and msg.get("audio_url"):
                    stats["ERROR_poor_bot_got_audio_url"] += 1
                if msg.get("lane") == "overlap" and msg.get("audio_url"):
                    stats["ERROR_overlap_with_audio_url"] += 1
            if kind == "mode":
                stats[f"mode_event_{msg.get('mode')}"] += 1

    async def audio_sender(ws):
        idx = 0
        next_t = time.monotonic()
        while not stop.is_set():
            elapsed = time.monotonic() - t0
            if frames and should_speak(args.speak_pattern, bot_index, args.num_bots, elapsed,
                                       args.overlap_count, args.slot):
                frame = frames[idx % len(frames)]
                idx += 1
            else:
                frame = SILENT_FRAME
            await ws.send(frame)
            stats["frames_sent"] += 1
            next_t += FRAME_S                           # absolute schedule: no drift, even with 20 bots
            delay = next_t - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                stats["frames_late"] += 1
                next_t = time.monotonic()

    try:
        async with websockets.connect(room_url) as r_ws, websockets.connect(audio_url) as a_ws:
            tasks = [asyncio.create_task(c) for c in (room_sender(r_ws), room_receiver(r_ws), audio_sender(a_ws))]
            await stop.wait()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        if not stop.is_set():
            stats["bots_failed"] += 1
            print(f"[{bot_id}] stopped: {e}")


def print_summary(stats: Counter, args) -> None:
    print("\n" + "=" * 60)
    print(f" SUMMARY ({args.num_bots} bots, pattern={args.speak_pattern}, network={args.network})")
    print("=" * 60)
    for key in sorted(stats):
        print(f" {key:<38} {stats[key]}")
    print("-" * 60)
    errors = sum(v for k, v in stats.items() if k.startswith("ERROR_"))
    print(" Rules checked here: poor bots never get audio_url; overlap lane never has audio_url ->",
          "OK" if errors == 0 else f"{errors} VIOLATIONS")
    print(" Check the overlap cap and latency in the call server's metrics.csv (columns lane, e2e_ms).")


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--num-bots", "--users", type=int, default=4, dest="num_bots", help="number of bots (5, 10, 20 ...)")
    p.add_argument("--room", default="load-room")
    p.add_argument("--languages", default="en,hi,kn", help="comma-separated language pool")
    p.add_argument("--wav", default=None, help="16 kHz mono PCM16 speech recording")
    p.add_argument("--speak-pattern", choices=["round-robin", "overlap", "random", "continuous"], default="round-robin")
    p.add_argument("--overlap-count", type=int, default=3, help="bots talking at once with --speak-pattern overlap")
    p.add_argument("--slot", type=float, default=4.0, help="seconds per turn in round-robin")
    p.add_argument("--network", choices=["good", "poor", "mixed"], default="mixed")
    p.add_argument("--server", default="ws://localhost:8000", help="call server WebSocket base URL")
    p.add_argument("--duration", type=int, default=30, help="seconds (0 = until Ctrl+C)")
    args = p.parse_args()

    langs = [l.strip() for l in args.languages.split(",") if l.strip()]
    if args.wav:
        frames = load_wav_frames(Path(args.wav))
    else:
        print("WARNING: no --wav given, streaming a synthetic tone. A real VAD will not treat it as speech.")
        frames = generate_synthetic_audio_frames()

    stats: Counter = Counter()
    stop = asyncio.Event()
    print("=" * 60)
    print(f" Launching {args.num_bots} bots in '{args.room}' | {args.speak_pattern} | network {args.network} | {langs}")
    print("=" * 60)

    bots = [asyncio.create_task(run_bot(args, i, langs[i % len(langs)], frames, stats, stop))
            for i in range(args.num_bots)]
    try:
        if args.duration > 0:
            await asyncio.sleep(args.duration)
        else:
            await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        stop.set()
        await asyncio.gather(*bots, return_exceptions=True)
        print_summary(stats, args)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
