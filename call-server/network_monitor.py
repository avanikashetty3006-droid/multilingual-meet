"""
Network Decision Engine (Role 2 Step 3)
Implements Section A7 of shared/CONTRACT.md:
- Pure decision functions with hysteresis.
- Evaluates per listener every 2 seconds.
"""
from typing import Dict, Optional
from config import CONFIG

net_cfg = CONFIG.get("network", {})
RTT_MAX = net_cfg.get("rtt_ms_threshold", 150)
LOSS_MAX = net_cfg.get("packet_loss_pct_threshold", 2.0)
BITRATE_MIN = net_cfg.get("bitrate_kbps_threshold", 500)
SPEECH_LATENCY_MAX = net_cfg.get("speech_avg_latency_ms_max", 3000)
HYSTERESIS_WINDOWS = net_cfg.get("hysteresis_windows", 3)
INITIAL_MODE = net_cfg.get("initial_mode", "subtitle")

def is_window_good(rtt_ms: float, packet_loss_pct: float, bitrate_kbps: float, speech_latency_ms: float) -> bool:
    """
    Returns True if current network window meets GOOD criteria.
    """
    return (
        rtt_ms < RTT_MAX
        and packet_loss_pct < LOSS_MAX
        and bitrate_kbps > BITRATE_MIN
        and speech_latency_ms < SPEECH_LATENCY_MAX
    )

class ListenerNetworkState:
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.current_mode = INITIAL_MODE
        self.consecutive_good_windows = 0
        self.consecutive_poor_windows = 0

    def update(self, rtt_ms: float, packet_loss_pct: float, bitrate_kbps: float, speech_latency_ms: float) -> Optional[str]:
        """
        Updates state and returns new mode if a switch occurred, else None.
        """
        window_good = is_window_good(rtt_ms, packet_loss_pct, bitrate_kbps, speech_latency_ms)

        if window_good:
            self.consecutive_good_windows += 1
            self.consecutive_poor_windows = 0
            if self.consecutive_good_windows >= HYSTERESIS_WINDOWS and self.current_mode != "audio":
                self.current_mode = "audio"
                return "audio"
        else:
            self.consecutive_poor_windows += 1
            self.consecutive_good_windows = 0
            if self.consecutive_poor_windows >= HYSTERESIS_WINDOWS and self.current_mode != "subtitle":
                self.current_mode = "subtitle"
                return "subtitle"

        return None
