"""Configuration loader for speaker-service (Role 4).

Reads token and audio defaults from ../shared/config.yaml and allows
environment variable overrides for VAD tuning and runtime mode.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

SERVICE_DIR = Path(__file__).resolve().parent
SHARED_CONFIG_PATH = SERVICE_DIR.parent / "shared" / "config.yaml"
DEFAULT_MODEL_PATH = SERVICE_DIR / "models" / "silero_vad_16k_op15.onnx"


def load_shared_config(path: Path = SHARED_CONFIG_PATH) -> Dict[str, Any]:
    """Load shared/config.yaml if present; return empty dict on absence."""
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict):
                return data
    return {}


_yaml = load_shared_config()
_audio_cfg = _yaml.get("audio", {}) or {}
_limits_cfg = _yaml.get("limits", {}) or {}
_token_cfg = _yaml.get("token", {}) or {}

# Runtime mode (CONTRACT A8: MOCK=1 for mock/energy-gate, MOCK=0 for Silero VAD)
MOCK: bool = os.getenv("MOCK", "1") == "1"
MOCK_ROTATE: bool = os.getenv("MOCK_ROTATE", "0") == "1"
MOCK_ROTATE_INTERVAL_S: float = float(os.getenv("MOCK_ROTATE_INTERVAL_S", "5.0"))

# Server binding
HOST: str = os.getenv("SPEAKER_HOST", "0.0.0.0")
PORT: int = int(os.getenv("SPEAKER_PORT", "8002"))

# Audio format invariants (CONTRACT A3 & shared/config.yaml)
SAMPLE_RATE: int = int(_audio_cfg.get("sample_rate", 16000))
CHANNELS: int = int(_audio_cfg.get("channels", 1))
FRAME_SAMPLES: int = int(_audio_cfg.get("frame_samples", 512))
FRAME_BYTES: int = int(_audio_cfg.get("frame_bytes", 1024))
FRAME_MS: int = (FRAME_SAMPLES * 1000) // SAMPLE_RATE  # 32 ms

# Token policy (shared/config.yaml)
MAX_OVERLAP: int = int(os.getenv("MAX_OVERLAP", str(_limits_cfg.get("max_overlap", 2))))
MIN_SPEECH_MS: int = int(os.getenv("TOKEN_MIN_SPEECH_MS", str(_token_cfg.get("min_speech_ms", 200))))
RELEASE_SILENCE_MS: int = int(os.getenv("TOKEN_RELEASE_SILENCE_MS", str(_token_cfg.get("release_silence_ms", 700))))
MIN_HOLD_MS: int = int(os.getenv("TOKEN_MIN_HOLD_MS", str(_token_cfg.get("min_hold_ms", 1000))))

# Silero VAD tunables (MOCK=0)
VAD_THRESHOLD: float = float(os.getenv("VAD_THRESHOLD", "0.5"))
VAD_NEG_THRESHOLD: float = float(os.getenv("VAD_NEG_THRESHOLD", str(max(VAD_THRESHOLD - 0.15, 0.01))))
VAD_START_FRAMES: int = int(os.getenv("VAD_START_FRAMES", "2"))  # 2 * 32ms = 64ms fast onset
VAD_END_SILENCE_MS: int = int(os.getenv("VAD_END_SILENCE_MS", "500"))
VAD_MODEL_PATH: Path = Path(os.getenv("VAD_MODEL_PATH", str(DEFAULT_MODEL_PATH)))

# Energy gate tunables (MOCK=1)
ENERGY_THRESHOLD: float = float(os.getenv("ENERGY_THRESHOLD", "400.0"))
ENERGY_START_FRAMES: int = int(os.getenv("ENERGY_START_FRAMES", "3"))
ENERGY_END_SILENCE_MS: int = int(os.getenv("ENERGY_END_SILENCE_MS", "500"))

# Stream robustness & tick scheduler
VAD_STALL_TIMEOUT_MS: int = int(os.getenv("VAD_STALL_TIMEOUT_MS", "1000"))
TICK_INTERVAL_MS: int = int(os.getenv("TICK_INTERVAL_MS", "50"))
MAX_FRAME_QUEUE: int = int(os.getenv("MAX_FRAME_QUEUE", "16"))


def get_token_config() -> Dict[str, int]:
    """Return normalized token policy config dict for TokenManager."""
    return {
        "max_overlap": MAX_OVERLAP,
        "min_speech_ms": MIN_SPEECH_MS,
        "release_silence_ms": RELEASE_SILENCE_MS,
        "min_hold_ms": MIN_HOLD_MS,
    }
