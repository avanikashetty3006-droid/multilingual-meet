import pytest
import sys
from pathlib import Path

# Ensure call-server root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_monitor import evaluate_window_quality, ListenerNetworkState


def test_pure_quality_evaluation():
    # Good network
    good, reason = evaluate_window_quality(
        rtt_ms=100, packet_loss_pct=0.5, bitrate_kbps=800, speech_latency_ms=1200
    )
    assert good is True
    assert reason == "good_network"

    # High RTT
    good, reason = evaluate_window_quality(
        rtt_ms=200, packet_loss_pct=0.5, bitrate_kbps=800, speech_latency_ms=1200
    )
    assert good is False
    assert "high_rtt" in reason

    # High packet loss
    good, reason = evaluate_window_quality(
        rtt_ms=80, packet_loss_pct=3.5, bitrate_kbps=800, speech_latency_ms=1200
    )
    assert good is False
    assert "high_packet_loss" in reason

    # Low bitrate
    good, reason = evaluate_window_quality(
        rtt_ms=80, packet_loss_pct=0.5, bitrate_kbps=300, speech_latency_ms=1200
    )
    assert good is False
    assert "low_bitrate" in reason

    # High speech latency
    good, reason = evaluate_window_quality(
        rtt_ms=80, packet_loss_pct=0.5, bitrate_kbps=800, speech_latency_ms=3500
    )
    assert good is False
    assert "high_speech_latency" in reason


def test_initial_mode_is_subtitle():
    state = ListenerNetworkState(participant_id="p-1")
    assert state.current_mode == "subtitle"


def test_hysteresis_poor_to_good():
    state = ListenerNetworkState(participant_id="p-1", current_mode="subtitle")

    # 1st good window -> still subtitle
    mode, changed, _ = state.record_window(80, 0.2, 1000, 1000)
    assert mode == "subtitle"
    assert changed is False

    # 2nd good window -> still subtitle
    mode, changed, _ = state.record_window(80, 0.2, 1000, 1000)
    assert mode == "subtitle"
    assert changed is False

    # 3rd consecutive good window -> switches to audio
    mode, changed, reason = state.record_window(80, 0.2, 1000, 1000)
    assert mode == "audio"
    assert changed is True
    assert reason == "good_network"


def test_hysteresis_good_to_poor():
    state = ListenerNetworkState(participant_id="p-1", current_mode="audio")

    # 1st poor window -> still audio
    mode, changed, _ = state.record_window(300, 5.0, 200, 4000)
    assert mode == "audio"
    assert changed is False

    # 2nd poor window -> still audio
    mode, changed, _ = state.record_window(300, 5.0, 200, 4000)
    assert mode == "audio"
    assert changed is False

    # 3rd consecutive poor window -> switches to subtitle
    mode, changed, reason = state.record_window(300, 5.0, 200, 4000)
    assert mode == "subtitle"
    assert changed is True
    assert "high_rtt" in reason or "high_packet_loss" in reason


def test_intermittent_flapping_prevented_by_hysteresis():
    state = ListenerNetworkState(participant_id="p-1", current_mode="subtitle")

    # Good, Good, Poor, Good -> Never reaches 3 consecutive good
    state.record_window(80, 0.2, 1000, 1000)
    state.record_window(80, 0.2, 1000, 1000)
    state.record_window(300, 5.0, 200, 4000)  # reset
    mode, changed, _ = state.record_window(80, 0.2, 1000, 1000)
    assert mode == "subtitle"
    assert changed is False
