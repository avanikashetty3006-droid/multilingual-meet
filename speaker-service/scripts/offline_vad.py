"""Offline WAV VAD inspector (Step 2 / Deliverable).

Reads a 16 kHz mono PCM16 WAV file in 512-sample (32 ms) frames through
Silero ONNX VAD (or energy gate with --mock) and prints detected segments.

Usage:
    python scripts/offline_vad.py tests/fixtures/speech_sample.wav
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FRAME_BYTES, FRAME_MS
from vad import EnergyGateVadStream, SileroVadStream, get_silero_engine


def detect_segments(wav_path: Path, threshold: float = 0.5, end_silence_ms: int = 500, mock: bool = False):
    with wave.open(str(wav_path), "rb") as wf:
        fmt = (wf.getframerate(), wf.getnchannels(), wf.getsampwidth())
        if fmt != (16000, 1, 2):
            raise SystemExit(
                f"Expected 16 kHz mono 16-bit PCM WAV, got {fmt[0]} Hz, {fmt[1]} ch, {fmt[2]*8}-bit"
            )
        raw = wf.readframes(wf.getnframes())
        duration_s = wf.getnframes() / wf.getframerate()

    if mock:
        vad = EnergyGateVadStream(end_silence_ms=end_silence_ms)
    else:
        vad = SileroVadStream(engine=get_silero_engine(), threshold=threshold, end_silence_ms=end_silence_ms)

    segments = []
    start_ms = None
    n_frames = len(raw) // FRAME_BYTES

    for i in range(n_frames):
        t_ms = i * FRAME_MS
        frame = raw[i * FRAME_BYTES : (i + 1) * FRAME_BYTES]
        ev = vad.process_frame(frame)
        if ev == "speech_start":
            start_ms = t_ms
        elif ev == "speech_end" and start_ms is not None:
            segments.append((start_ms, t_ms))
            start_ms = None

    if start_ms is not None:
        segments.append((start_ms, n_frames * FRAME_MS))

    return duration_s, segments


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("wav", type=Path, help="Path to 16 kHz mono PCM16 WAV")
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--end-silence-ms", type=int, default=500)
    p.add_argument("--mock", action="store_true", help="Use energy-gate VAD instead of Silero ONNX")
    args = p.parse_args()

    duration_s, segments = detect_segments(args.wav, args.threshold, args.end_silence_ms, args.mock)
    print(f"File: {args.wav} ({duration_s:.2f}s) | backend={'energy-gate' if args.mock else 'silero-onnx'}")
    if not segments:
        print("  No speech segments detected.")
        return
    for idx, (s_ms, e_ms) in enumerate(segments, 1):
        print(f"  Segment {idx}: {s_ms/1000:.3f}s -> {e_ms/1000:.3f}s (duration {(e_ms - s_ms)/1000:.3f}s)")


if __name__ == "__main__":
    main()
