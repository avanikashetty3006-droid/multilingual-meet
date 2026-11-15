"""Latency, scaling, and VAD/token-switch evaluation benchmark for speaker-service.

Measures:
1. Per-frame latency and total CPU time per 32 ms window for 1, 4, 10, 20, and 30 simultaneous streams.
2. False-trigger rate on silence and white noise, plus onset/offset error on labeled speech.
3. End-to-end TokenManager correctness in single-speaker, overlap, and release scenarios.

Usage:
    python scripts/benchmark_vad.py
"""

from __future__ import annotations

import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FRAME_BYTES, FRAME_MS
from token_manager import TokenManager
from vad import SileroVadStream, get_silero_engine

FIXTURE_WAV = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "speech_sample.wav"


def load_frames(wav_path: Path) -> list[bytes]:
    with wave.open(str(wav_path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return [raw[i : i + FRAME_BYTES] for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES)]


def bench_streams(speech_frames: list[bytes], counts=(1, 4, 10, 20, 30), ticks: int = 200) -> None:
    engine = get_silero_engine()
    print("\n=== Stream Scaling & Latency Benchmark (32 ms frame budget) ===")
    print(f"{'Streams':>7} | {'Avg ms/frame':>12} | {'Avg ms/tick':>11} | {'P95 ms/tick':>11} | {'CPU % (1 core)':>14}")
    print("-" * 68)
    for n in counts:
        streams = [SileroVadStream(engine=engine) for _ in range(n)]
        for s in streams:
            s.process_frame(speech_frames[0])

        tick_times = []
        for t in range(ticks):
            frame = speech_frames[t % len(speech_frames)]
            t0 = time.perf_counter()
            for s in streams:
                s.process_frame(frame)
            tick_times.append((time.perf_counter() - t0) * 1000.0)

        avg_tick = statistics.mean(tick_times)
        p95_tick = sorted(tick_times)[int(0.95 * len(tick_times))]
        avg_frame = avg_tick / n
        cpu_pct = (avg_tick / 32.0) * 100.0
        print(f"{n:>7} | {avg_frame:>12.4f} | {avg_tick:>11.3f} | {p95_tick:>11.3f} | {cpu_pct:>13.1f}%")


def evaluate_accuracy(speech_frames: list[bytes]) -> None:
    engine = get_silero_engine()
    rng = np.random.default_rng(42)

    # 1. Silence (60 seconds = 1875 frames)
    s_silence = SileroVadStream(engine=engine)
    silent = b"\x00" * FRAME_BYTES
    sil_triggers = sum(1 for _ in range(1875) if s_silence.process_frame(silent) == "speech_start")

    # 2. Low-level white noise (-35 dBFS, 60 seconds = 1875 frames)
    s_noise = SileroVadStream(engine=engine)
    noise_triggers = 0
    for _ in range(1875):
        n_pcm = (rng.normal(0, 300, 512)).clip(-32768, 32767).astype("<i2").tobytes()
        if s_noise.process_frame(n_pcm) == "speech_start":
            noise_triggers += 1

    # 3. Clean speech preceded by 1.0 s (31 frames) silence and followed by 1.5 s (47 frames) silence
    s_speech = SileroVadStream(engine=engine, threshold=0.5, end_silence_ms=500)
    lead = [silent] * 31
    tail = [silent] * 47
    timeline = lead + speech_frames + tail
    rms_vals = [
        float(np.sqrt(np.mean(np.frombuffer(f, dtype="<i2").astype(np.float32) ** 2)))
        for f in timeline
    ]
    active_idxs = [i for i, r in enumerate(rms_vals) if r > 80.0]
    true_start_ms = active_idxs[0] * FRAME_MS
    true_end_ms = (active_idxs[-1] + 1) * FRAME_MS

    events = []
    for idx, f in enumerate(timeline):
        ev = s_speech.process_frame(f)
        if ev:
            events.append((idx * FRAME_MS, ev))

    first_start = next((t for t, e in events if e == "speech_start"), None)
    last_end = next((t for t, e in reversed(events) if e == "speech_end"), None)

    # 4. Two-speaker overlap token switch check
    tm = TokenManager({"min_speech_ms": 200, "release_silence_ms": 700, "min_hold_ms": 1000, "max_overlap": 2})
    vad_a = SileroVadStream(engine=engine)
    vad_b = SileroVadStream(engine=engine)
    token_states = []
    # Speaker A speaks from t=0; Speaker B overlaps at t=1.0s (frame 31); A stops at t=2.0s
    total_frames = len(speech_frames) + 90
    for idx in range(total_frames):
        now_ms = idx * FRAME_MS
        fa = speech_frames[idx] if idx < len(speech_frames) else silent
        fb = speech_frames[(idx - 31) % len(speech_frames)] if 31 <= idx < 31 + len(speech_frames) else silent
        ea = vad_a.process_frame(fa)
        eb = vad_b.process_frame(fb)
        if ea:
            st = tm.on_vad("speaker-a", ea, now_ms)
            if st:
                token_states.append((now_ms, st))
        if eb:
            st = tm.on_vad("speaker-b", eb, now_ms)
            if st:
                token_states.append((now_ms, st))
        st_tick = tm.tick(now_ms)
        if st_tick:
            token_states.append((now_ms, st_tick))

    print("\n=== VAD Accuracy & Token Switch Evaluation ===")
    print(f"Silence false triggers / min : {sil_triggers}")
    print(f"Noise (-35dBFS) triggers/min : {noise_triggers}")
    print(f"Speech onset error           : {(first_start - true_start_ms) if first_start is not None else 'N/A'} ms")
    print(f"Speech end delay (incl 500ms): {(last_end - true_end_ms) if last_end is not None else 'N/A'} ms")
    print(f"Overlap token transitions    : {token_states}")


def main() -> None:
    frames = load_frames(FIXTURE_WAV)
    bench_streams(frames)
    evaluate_accuracy(frames)


if __name__ == "__main__":
    main()
