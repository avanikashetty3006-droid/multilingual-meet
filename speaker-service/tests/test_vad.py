"""Unit tests for EnergyGateVadStream and SileroVadStream (Role 4, Step 4)."""

from __future__ import annotations

import struct
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import FRAME_BYTES
from vad import EnergyGateVadStream, SileroVadStream, get_silero_engine

FIXTURE_WAV = Path(__file__).resolve().parent / "fixtures" / "speech_sample.wav"
SILENT_FRAME = b"\x00" * FRAME_BYTES


def _load_wav_frames(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as wf:
        assert (wf.getframerate(), wf.getnchannels(), wf.getsampwidth()) == (16000, 1, 2)
        raw = wf.readframes(wf.getnframes())
    return [raw[i : i + FRAME_BYTES] for i in range(0, len(raw) - FRAME_BYTES + 1, FRAME_BYTES)]


def _make_tone_frame(amplitude: int = 2000) -> bytes:
    samples = [int(amplitude * ((i % 16) / 8.0 - 1.0)) for i in range(512)]
    return struct.pack("<512h", *samples)


def test_energy_gate_detects_tone_and_silence():
    vad = EnergyGateVadStream(threshold=400.0, start_frames=3, end_silence_ms=160)
    tone = _make_tone_frame(2000)

    events = [vad.process_frame(tone) for _ in range(5)]
    assert events.count("speech_start") == 1
    assert vad.is_speaking is True

    end_events = [vad.process_frame(SILENT_FRAME) for _ in range(10)]
    assert end_events.count("speech_end") == 1
    assert vad.is_speaking is False


def test_silero_silence_and_tone_produce_no_speech():
    engine = get_silero_engine()
    vad = SileroVadStream(engine=engine)
    tone = _make_tone_frame(2000)

    for _ in range(40):
        assert vad.process_frame(SILENT_FRAME) is None
    for _ in range(40):
        assert vad.process_frame(tone) is None
    assert vad.is_speaking is False


def test_silero_detects_real_speech_and_trailing_silence():
    engine = get_silero_engine()
    vad = SileroVadStream(engine=engine, end_silence_ms=500)
    frames = _load_wav_frames(FIXTURE_WAV) + [SILENT_FRAME] * 25

    events = []
    for idx, frame in enumerate(frames):
        ev = vad.process_frame(frame)
        if ev:
            events.append((idx, ev))

    assert any(ev == "speech_start" for _, ev in events)
    assert events[-1][1] == "speech_end"
    assert vad.is_speaking is False


def test_silero_interleaved_streams_have_zero_crosstalk():
    """Interleave real speech frames on stream A and silence on stream B frame-by-frame."""
    engine = get_silero_engine()
    stream_speech = SileroVadStream(engine=engine)
    stream_silence = SileroVadStream(engine=engine)

    speech_frames = _load_wav_frames(FIXTURE_WAV)
    speech_events = []
    silence_events = []

    for f in speech_frames:
        ev_a = stream_speech.process_frame(f)
        ev_b = stream_silence.process_frame(SILENT_FRAME)
        if ev_a:
            speech_events.append(ev_a)
        if ev_b:
            silence_events.append(ev_b)

    assert "speech_start" in speech_events
    assert silence_events == []
    assert stream_silence.is_speaking is False


def test_wrong_frame_sizes_ignored():
    engine = get_silero_engine()
    vad = SileroVadStream(engine=engine)
    assert vad.process_frame(b"short") is None
    assert vad.process_frame(b"\x00" * 2048) is None
    assert vad.is_speaking is False


def test_silero_20_streams_realtime_latency():
    """20 simultaneous streams must process 32ms worth of frames well under 32ms."""
    engine = get_silero_engine()
    streams = [SileroVadStream(engine=engine) for _ in range(20)]
    speech_frames = _load_wav_frames(FIXTURE_WAV)

    # Warm pass
    for s in streams:
        s.process_frame(speech_frames[0])

    n_rounds = 50
    t0 = time.perf_counter()
    for r in range(n_rounds):
        frame = speech_frames[r % len(speech_frames)]
        for s in streams:
            s.process_frame(frame)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    ms_per_32ms_tick_for_20 = elapsed_ms / n_rounds
    assert ms_per_32ms_tick_for_20 < 32.0, f"Too slow: {ms_per_32ms_tick_for_20:.2f}ms for 20 streams"
