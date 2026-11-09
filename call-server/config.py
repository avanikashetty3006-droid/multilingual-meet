import os
from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "shared" / "config.yaml"

def load_yaml_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

yaml_cfg = load_yaml_config()
net_cfg = yaml_cfg.get("network", {})
audio_cfg = yaml_cfg.get("audio", {})
timeout_cfg = yaml_cfg.get("timeouts", {})
limit_cfg = yaml_cfg.get("limits", {})

# Service URLs and Ports
CALL_SERVER_URL = os.getenv("CALL_SERVER_URL", "http://localhost:8000")
SPEECH_SERVICE_URL = os.getenv("SPEECH_SERVICE_URL", "http://localhost:8001")
SPEAKER_SERVICE_URL = os.getenv("SPEAKER_SERVICE_URL", "http://localhost:8002")

# LiveKit Credentials
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "secret")

# Mock Mode flag
MOCK = os.getenv("MOCK", "1") == "1"

# Network thresholds (from shared/config.yaml with defaults)
GOOD_RTT_MAX_MS = float(net_cfg.get("good_rtt_max_ms", 150))
GOOD_PACKET_LOSS_MAX_PCT = float(net_cfg.get("good_packet_loss_max_pct", 2.0))
GOOD_BITRATE_MIN_KBPS = float(net_cfg.get("good_bitrate_min_kbps", 500))
SPEECH_SERVICE_LATENCY_MAX_MS = float(net_cfg.get("speech_service_latency_max_ms", 3000))
STALE_STATS_SECONDS = float(net_cfg.get("stale_stats_seconds", 6.0))
HYSTERESIS_WINDOWS = int(net_cfg.get("hysteresis_windows", 3))
INITIAL_MODE = net_cfg.get("initial_mode", "subtitle")

# Audio formatting
SAMPLE_RATE = int(audio_cfg.get("sample_rate", 16000))
CHANNELS = int(audio_cfg.get("channels", 1))
FRAME_SAMPLES = int(audio_cfg.get("frame_samples", 512))
FRAME_BYTES = int(audio_cfg.get("frame_bytes", 1024))
MIN_CHUNK_MS = int(audio_cfg.get("min_chunk_ms", 400))
MAX_CHUNK_SEC = float(audio_cfg.get("max_chunk_sec", 4.0))

# Timeouts
SPEECH_SERVICE_TIMEOUT_S = float(timeout_cfg.get("speech_service_s", 6.0))
HEALTH_POLL_INTERVAL_S = float(timeout_cfg.get("health_poll_interval_s", 2.0))

# Limits (from shared/config.yaml)
MAX_OVERLAP = int(limit_cfg.get("max_overlap", 2))
MAX_QUEUE_DEPTH = int(limit_cfg.get("max_queue_depth", 8))
