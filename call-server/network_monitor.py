"""Network monitoring and mode decision engine.

Implements the contract rule from section A7:
- Evaluates RTT, packet loss %, bitrate, stats freshness, and speech service latency.
- Uses hysteresis (default 3 consecutive windows) before flipping between "audio" and "subtitle".
- Initial mode is "subtitle" until qualified.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple
from config import (
    GOOD_RTT_MAX_MS,
    GOOD_PACKET_LOSS_MAX_PCT,
    GOOD_BITRATE_MIN_KBPS,
    SPEECH_SERVICE_LATENCY_MAX_MS,
    STALE_STATS_SECONDS,
    HYSTERESIS_WINDOWS,
    INITIAL_MODE,
)


def evaluate_window_quality(
    rtt_ms: float,
    packet_loss_pct: float,
    bitrate_kbps: float,
    speech_latency_ms: Optional[float] = None,
    stats_age_s: Optional[float] = None,
    rtt_max: float = GOOD_RTT_MAX_MS,
    loss_max: float = GOOD_PACKET_LOSS_MAX_PCT,
    bitrate_min: float = GOOD_BITRATE_MIN_KBPS,
    speech_latency_max: float = SPEECH_SERVICE_LATENCY_MAX_MS,
    stale_stats_max_s: float = STALE_STATS_SECONDS,
) -> Tuple[bool, str]:
    """Pure function evaluating whether a single 2s window is GOOD or POOR.

    Returns:
        (is_good, reason)
    """
    if stats_age_s is not None and stats_age_s > stale_stats_max_s:
        return False, "stale_stats"
    if rtt_ms >= rtt_max:
        return False, f"high_rtt_{rtt_ms:.0f}ms"
    if packet_loss_pct >= loss_max:
        return False, f"high_packet_loss_{packet_loss_pct:.1f}%"
    if bitrate_kbps <= bitrate_min:
        return False, f"low_bitrate_{bitrate_kbps:.0f}kbps"
    if speech_latency_ms is not None and speech_latency_ms >= speech_latency_max:
        return False, f"high_speech_latency_{speech_latency_ms:.0f}ms"
    return True, "good_network"


@dataclass
class ListenerNetworkState:
    participant_id: str
    current_mode: str = INITIAL_MODE
    consecutive_good: int = 0
    consecutive_poor: int = 0
    last_reason: str = "initial_state"
    has_evaluated: bool = False

    def record_window(
        self,
        rtt_ms: float,
        packet_loss_pct: float,
        bitrate_kbps: float,
        speech_latency_ms: Optional[float] = None,
        stats_age_s: Optional[float] = None,
        hysteresis_windows: int = HYSTERESIS_WINDOWS,
    ) -> Tuple[str, bool, str]:
        """Updates window stats and returns (current_mode, mode_changed, reason)."""
        self.has_evaluated = True

        is_good, reason = evaluate_window_quality(
            rtt_ms=rtt_ms,
            packet_loss_pct=packet_loss_pct,
            bitrate_kbps=bitrate_kbps,
            speech_latency_ms=speech_latency_ms,
            stats_age_s=stats_age_s,
        )

        old_mode = self.current_mode
        changed = False

        if is_good:
            self.consecutive_good += 1
            self.consecutive_poor = 0
            if self.current_mode == "subtitle" and self.consecutive_good >= hysteresis_windows:
                self.current_mode = "audio"
                changed = True
                self.last_reason = "good_network"
        else:
            self.consecutive_poor += 1
            self.consecutive_good = 0
            if self.current_mode == "audio" and self.consecutive_poor >= hysteresis_windows:
                self.current_mode = "subtitle"
                changed = True
                self.last_reason = reason

        effective_reason = self.last_reason if changed else reason
        return self.current_mode, changed, effective_reason
