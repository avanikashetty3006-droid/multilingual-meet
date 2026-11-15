"""WAV helpers using only the standard library + numpy."""
import io
import wave
from typing import Optional, Tuple

import numpy as np

TARGET_SR = 16000


def decode_wav(data: bytes) -> Optional[Tuple[np.ndarray, int]]:
    """Return (float32 mono samples in -1..1, sample_rate) or None if the bytes are not a readable 16-bit WAV."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            ch, width, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
    except Exception:
        return None
    if width != 2 or not raw:
        return None
    x = np.frombuffer(raw[: len(raw) - (len(raw) % 2)], dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x[: len(x) - (len(x) % ch)].reshape(-1, ch).mean(axis=1)
    return x, sr


def resample(x: np.ndarray, sr: int, target: int = TARGET_SR) -> np.ndarray:
    """Linear resampling (good enough for speech going into Whisper)."""
    if sr == target or len(x) == 0:
        return x
    n_out = int(round(len(x) * target / sr))
    return np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def encode_wav(x: np.ndarray, sr: int) -> bytes:
    """float32 mono -> 16-bit PCM WAV bytes."""
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()
