"""Voice Activity Detection streams for speaker-service (Role 4).

Provides two interchangeable stream classes with the same interface:
- `EnergyGateVadStream`: lightweight RMS energy gate for `MOCK=1` (no ML deps).
- `SileroVadStream`: low-latency Silero VAD v5/v6 ONNX stream for `MOCK=0`
  using a shared stateless `onnxruntime.InferenceSession` and isolated
  per-participant recurrent state (`_x_buf`, `_state`).

Audio format invariant (CONTRACT A3):
  PCM16 little-endian, 16 kHz, mono, 512 samples = 1024 bytes = 32 ms/frame.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional, Protocol

import numpy as np

from config import (
    ENERGY_END_SILENCE_MS,
    ENERGY_START_FRAMES,
    ENERGY_THRESHOLD,
    FRAME_BYTES,
    FRAME_MS,
    FRAME_SAMPLES,
    SAMPLE_RATE,
    VAD_END_SILENCE_MS,
    VAD_MODEL_PATH,
    VAD_NEG_THRESHOLD,
    VAD_START_FRAMES,
    VAD_THRESHOLD,
)

logger = logging.getLogger("speaker-service.vad")

_PCM_SCALE = np.float32(1.0 / 32768.0)
_CONTEXT_SAMPLES = 64  # Silero v5/v6 16 kHz context window


class BaseVadStream(Protocol):
    is_speaking: bool

    def process_frame(self, frame_bytes: bytes) -> Optional[str]:
        ...

    def force_end(self) -> Optional[str]:
        ...

    def reset(self) -> None:
        ...


class EnergyGateVadStream:
    """Fast RMS energy-gate VAD for MOCK=1 mode (no ML runtime required)."""

    def __init__(
        self,
        threshold: float = ENERGY_THRESHOLD,
        start_frames: int = ENERGY_START_FRAMES,
        end_silence_ms: int = ENERGY_END_SILENCE_MS,
    ) -> None:
        self.threshold = float(threshold)
        self.start_frames = max(1, int(start_frames))
        self.end_silence_frames = max(1, math.ceil(end_silence_ms / FRAME_MS))

        self.is_speaking: bool = False
        self._speech_streak: int = 0
        self._silence_streak: int = 0
        self.last_rms: float = 0.0

    def reset(self) -> None:
        self.is_speaking = False
        self._speech_streak = 0
        self._silence_streak = 0
        self.last_rms = 0.0

    def force_end(self) -> Optional[str]:
        if self.is_speaking:
            self.reset()
            return "speech_end"
        self._speech_streak = 0
        return None

    def process_frame(self, frame_bytes: bytes) -> Optional[str]:
        if len(frame_bytes) != FRAME_BYTES:
            return None

        samples = np.frombuffer(frame_bytes, dtype="<i2").astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        self.last_rms = rms
        is_speech = rms >= self.threshold

        if not self.is_speaking:
            if is_speech:
                self._speech_streak += 1
                if self._speech_streak >= self.start_frames:
                    self.is_speaking = True
                    self._silence_streak = 0
                    return "speech_start"
            else:
                self._speech_streak = 0
            return None

        if is_speech:
            self._silence_streak = 0
        else:
            self._silence_streak += 1
            if self._silence_streak >= self.end_silence_frames:
                self.is_speaking = False
                self._speech_streak = 0
                self._silence_streak = 0
                return "speech_end"
        return None


class SileroOnnxEngine:
    """Shared thread-safe ONNX Runtime inference engine for Silero VAD (16 kHz).

    The ONNX session itself holds only model weights and graph execution state.
    All recurrent LSTM states (`state` and `context`) live inside each
    `SileroVadStream` instance so participants remain 100% isolated.
    """

    def __init__(self, model_path: Path = VAD_MODEL_PATH) -> None:
        import onnxruntime as ort

        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"Silero ONNX model not found at {self.model_path}. "
                "Ensure speaker-service/models/silero_vad_16k_op15.onnx exists or set VAD_MODEL_PATH."
            )

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = ["CPUExecutionProvider"]
        avail = ort.get_available_providers()
        if "CPUExecutionProvider" not in avail:
            providers = avail

        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=providers,
            sess_options=opts,
        )
        self._sr = np.array(SAMPLE_RATE, dtype=np.int64)
        self._input_names = {i.name for i in self.session.get_inputs()}

    def warmup(self, iterations: int = 5) -> None:
        """Run dummy frames at startup to eliminate first-frame JIT/allocator latency."""
        x_buf = np.zeros((1, _CONTEXT_SAMPLES + FRAME_SAMPLES), dtype=np.float32)
        state = np.zeros((2, 1, 128), dtype=np.float32)
        for _ in range(iterations):
            _, state = self.infer(x_buf, state)

    def infer(self, x_buf: np.ndarray, state: np.ndarray) -> tuple[float, np.ndarray]:
        feed = {"input": x_buf, "state": state}
        if "sr" in self._input_names:
            feed["sr"] = self._sr
        out, next_state = self.session.run(None, feed)
        return float(out[0][0]), next_state


_shared_engine: Optional[SileroOnnxEngine] = None


def get_silero_engine(model_path: Path = VAD_MODEL_PATH, warmup: bool = True) -> SileroOnnxEngine:
    """Return process-wide cached SileroOnnxEngine singleton."""
    global _shared_engine
    if _shared_engine is None:
        engine = SileroOnnxEngine(model_path=model_path)
        if warmup:
            engine.warmup()
        _shared_engine = engine
    return _shared_engine


class SileroVadStream:
    """Per-participant streaming Silero VAD with isolated state and zero per-frame allocations."""

    def __init__(
        self,
        engine: Optional[SileroOnnxEngine] = None,
        threshold: float = VAD_THRESHOLD,
        neg_threshold: Optional[float] = None,
        start_frames: int = VAD_START_FRAMES,
        end_silence_ms: int = VAD_END_SILENCE_MS,
    ) -> None:
        self.engine = engine or get_silero_engine()
        self.threshold = float(threshold)
        self.neg_threshold = (
            float(neg_threshold)
            if neg_threshold is not None
            else max(self.threshold - 0.15, 0.01)
        )
        self.start_frames = max(1, int(start_frames))
        self.end_silence_frames = max(1, math.ceil(end_silence_ms / FRAME_MS))

        # Isolated recurrent state per participant stream (never shared across streams)
        self._x_buf = np.zeros((1, _CONTEXT_SAMPLES + FRAME_SAMPLES), dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

        self.is_speaking: bool = False
        self._speech_streak: int = 0
        self._silence_streak: int = 0
        self.last_prob: float = 0.0

    def reset(self) -> None:
        self._x_buf.fill(0.0)
        self._state.fill(0.0)
        self.is_speaking = False
        self._speech_streak = 0
        self._silence_streak = 0
        self.last_prob = 0.0

    def force_end(self) -> Optional[str]:
        if self.is_speaking:
            self.is_speaking = False
            self._speech_streak = 0
            self._silence_streak = 0
            return "speech_end"
        self._speech_streak = 0
        return None

    def score_frame(self, frame_bytes: bytes) -> float:
        """Compute speech probability [0, 1] for one 1024-byte PCM16 frame."""
        # Shift last 64 samples into context slot, then scale new 512 int16 samples in-place
        self._x_buf[0, :_CONTEXT_SAMPLES] = self._x_buf[0, -_CONTEXT_SAMPLES:]
        pcm_i16 = np.frombuffer(frame_bytes, dtype="<i2")
        np.multiply(pcm_i16, _PCM_SCALE, out=self._x_buf[0, _CONTEXT_SAMPLES:], casting="unsafe")
        prob, self._state = self.engine.infer(self._x_buf, self._state)
        self.last_prob = prob
        return prob

    def process_frame(self, frame_bytes: bytes) -> Optional[str]:
        """Process one 1024-byte PCM16 frame; return 'speech_start', 'speech_end', or None."""
        if len(frame_bytes) != FRAME_BYTES:
            return None

        prob = self.score_frame(frame_bytes)

        if not self.is_speaking:
            if prob >= self.threshold:
                self._speech_streak += 1
                if self._speech_streak >= self.start_frames:
                    self.is_speaking = True
                    self._silence_streak = 0
                    return "speech_start"
            else:
                self._speech_streak = 0
            return None

        # Schmitt-trigger hysteresis: keep speaking until probability falls below neg_threshold
        if prob >= self.neg_threshold:
            self._silence_streak = 0
        else:
            self._silence_streak += 1
            if self._silence_streak >= self.end_silence_frames:
                self.is_speaking = False
                self._speech_streak = 0
                self._silence_streak = 0
                return "speech_end"
        return None
