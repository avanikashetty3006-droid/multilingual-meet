import pytest
from network_monitor import ListenerNetworkState, is_window_good

def test_initial_mode_is_subtitle():
    state = ListenerNetworkState("p-1")
    assert state.current_mode == "subtitle"

def test_window_good_criteria():
    # Good condition: rtt < 150, loss < 2, bitrate > 500, speech_lat < 3000
    assert is_window_good(100, 0.5, 800, 1000) is True
    # RTT too high
    assert is_window_good(160, 0.5, 800, 1000) is False
    # Packet loss too high
    assert is_window_good(100, 2.5, 800, 1000) is False
    # Bitrate too low
    assert is_window_good(100, 0.5, 400, 1000) is False
    # Speech latency too high
    assert is_window_good(100, 0.5, 800, 3200) is False

def test_poor_to_good_requires_3_consecutive_windows():
    state = ListenerNetworkState("p-1")
    assert state.current_mode == "subtitle"

    # Window 1: Good
    mode = state.update(rtt_ms=100, packet_loss_pct=0.1, bitrate_kbps=900, speech_latency_ms=800)
    assert mode is None
    assert state.current_mode == "subtitle"

    # Window 2: Good
    mode = state.update(rtt_ms=100, packet_loss_pct=0.1, bitrate_kbps=900, speech_latency_ms=800)
    assert mode is None
    assert state.current_mode == "subtitle"

    # Window 3: Good -> Triggers switch to audio
    mode = state.update(rtt_ms=100, packet_loss_pct=0.1, bitrate_kbps=900, speech_latency_ms=800)
    assert mode == "audio"
    assert state.current_mode == "audio"

def test_good_to_poor_requires_3_consecutive_windows():
    state = ListenerNetworkState("p-1")
    # First promote to audio
    for _ in range(3):
        state.update(100, 0.1, 900, 800)
    assert state.current_mode == "audio"

    # Bad window 1
    mode = state.update(300, 5.0, 200, 4000)
    assert mode is None
    assert state.current_mode == "audio"

    # Bad window 2
    mode = state.update(300, 5.0, 200, 4000)
    assert mode is None
    assert state.current_mode == "audio"

    # Bad window 3 -> Triggers switch to subtitle
    mode = state.update(300, 5.0, 200, 4000)
    assert mode == "subtitle"
    assert state.current_mode == "subtitle"

def test_intermittent_flapping_does_not_switch():
    state = ListenerNetworkState("p-1")
    # 2 good, 1 bad, 2 good -> should stay subtitle
    state.update(100, 0.1, 900, 800)
    state.update(100, 0.1, 900, 800)
    state.update(300, 5.0, 200, 4000) # Reset
    assert state.consecutive_good_windows == 0
    state.update(100, 0.1, 900, 800)
    state.update(100, 0.1, 900, 800)
    assert state.current_mode == "subtitle"
