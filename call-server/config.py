import os
import yaml

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shared", "config.yaml")

DEFAULT_CONFIG = {
    "network": {
        "rtt_ms_threshold": 150,
        "packet_loss_pct_threshold": 2.0,
        "bitrate_kbps_threshold": 500,
        "speech_avg_latency_ms_max": 3000,
        "hysteresis_windows": 3,
        "window_interval_sec": 2.0,
        "initial_mode": "subtitle",
        "max_queue_depth": 8
    },
    "services": {
        "call_server_port": 8000,
        "speech_service_port": 8001,
        "speaker_service_port": 8002,
        "frontend_port": 5173
    }
}

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or DEFAULT_CONFIG
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

CONFIG = load_config()
MOCK_MODE = os.getenv("MOCK", "1") == "1"
SPEECH_SERVICE_URL = os.getenv("SPEECH_SERVICE_URL", "http://localhost:8001").rstrip("/")
SPEAKER_SERVICE_URL = os.getenv("SPEAKER_SERVICE_URL", "http://localhost:8002").rstrip("/")
