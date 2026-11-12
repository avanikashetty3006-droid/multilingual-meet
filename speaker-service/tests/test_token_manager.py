"""Unit tests for TokenManager (Role 4, Step 2).

Covers all required token-passing and hysteresis rules from CONTRACT A5
and shared/config.yaml without any sleeping or network I/O.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from token_manager import TokenManager


DEFAULT_CFG = {
    "min_speech_ms": 200,
    "release_silence_ms": 700,
    "min_hold_ms": 1000,
    "max_overlap": 2,
}


def test_loads_shared_config_yaml():
    tm = TokenManager()
    assert tm.min_speech_ms == 200
    assert tm.release_silence_ms == 700
    assert tm.min_hold_ms == 1000
    assert tm.max_overlap == 2
    assert tm.state() == {"holder": None, "overlap": []}


def test_first_speaker_gets_token():
    tm = TokenManager(DEFAULT_CFG)
    assert tm.on_vad("p1", "speech_start", 1000) is None
    assert tm.tick(1199) is None
    assert tm.tick(1200) == {"holder": "p1", "overlap": []}
    assert tm.tick(1500) is None  # no duplicate emit when unchanged


def test_second_speaker_goes_to_overlap():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 1000)
    assert tm.tick(1200) == {"holder": "p1", "overlap": []}

    assert tm.on_vad("p2", "speech_start", 1300) is None
    assert tm.tick(1499) is None
    assert tm.tick(1500) == {"holder": "p1", "overlap": ["p2"]}


def test_release_after_700ms_silence():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    assert tm.tick(200) == {"holder": "p1", "overlap": []}

    assert tm.on_vad("p1", "speech_end", 1500) is None
    assert tm.tick(2199) is None
    assert tm.tick(2200) == {"holder": None, "overlap": []}


def test_longest_waiting_overlap_promoted_on_release():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    tm.tick(200)

    tm.on_vad("p2", "speech_start", 300)
    tm.on_vad("p3", "speech_start", 400)
    assert tm.tick(600) == {"holder": "p1", "overlap": ["p2", "p3"]}

    assert tm.on_vad("p1", "speech_end", 1500) is None
    assert tm.tick(2200) == {"holder": "p2", "overlap": ["p3"]}


def test_150ms_blip_is_ignored():
    tm = TokenManager(DEFAULT_CFG)
    assert tm.on_vad("p1", "speech_start", 1000) is None
    assert tm.on_vad("p1", "speech_end", 1150) is None
    assert tm.tick(2000) is None
    assert tm.state() == {"holder": None, "overlap": []}

    # Blip while another participant holds token should also not enter overlap
    tm.on_vad("p1", "speech_start", 3000)
    assert tm.tick(3200) == {"holder": "p1", "overlap": []}
    assert tm.on_vad("p2", "speech_start", 3300) is None
    assert tm.on_vad("p2", "speech_end", 3450) is None
    assert tm.tick(4000) is None
    assert tm.state() == {"holder": "p1", "overlap": []}


def test_holder_not_displaced_within_1s_min_hold():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    # p1 becomes holder at t=200 -> min_hold_ms=1000 means held at least until t=1200
    assert tm.tick(200) == {"holder": "p1", "overlap": []}

    tm.on_vad("p2", "speech_start", 250)
    assert tm.tick(450) == {"holder": "p1", "overlap": ["p2"]}

    # p1 stops at t=400 -> 700ms silence completes at t=1100, still inside 1000ms hold window!
    assert tm.on_vad("p1", "speech_end", 400) is None
    assert tm.tick(1100) is None
    assert tm.state() == {"holder": "p1", "overlap": ["p2"]}

    # At t=1200 (1000ms after t=200), p1 releases and p2 is promoted
    assert tm.tick(1200) == {"holder": "p2", "overlap": []}


def test_holder_disconnect_releases_and_promotes_immediately():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    tm.tick(200)
    tm.on_vad("p2", "speech_start", 250)
    assert tm.tick(450) == {"holder": "p1", "overlap": ["p2"]}

    # Even within min_hold_ms, disconnecting removes p1 immediately
    assert tm.on_disconnect("p1", 500) == {"holder": "p2", "overlap": []}

    # Disconnecting last speaker empties state
    assert tm.on_disconnect("p2", 600) == {"holder": None, "overlap": []}


def test_same_millisecond_start_deterministic_arrival_tiebreak():
    tm = TokenManager(DEFAULT_CFG)
    assert tm.on_vad("p2", "speech_start", 1000) is None
    assert tm.on_vad("p1", "speech_start", 1000) is None
    # p2 arrived first at t=1000 -> deterministic holder is p2, overlap is p1
    assert tm.tick(1200) == {"holder": "p2", "overlap": ["p1"]}


def test_overlap_speaker_going_quiet_leaves_overlap():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    tm.on_vad("p2", "speech_start", 100)
    tm.on_vad("p3", "speech_start", 150)
    tm.tick(400)
    assert tm.state() == {"holder": "p1", "overlap": ["p2", "p3"]}

    assert tm.on_vad("p2", "speech_end", 600) == {"holder": "p1", "overlap": ["p3"]}
    assert tm.on_vad("p3", "speech_end", 700) == {"holder": "p1", "overlap": []}


def test_six_speakers_overlap_never_exceeds_max_overlap():
    tm = TokenManager(DEFAULT_CFG)
    for i in range(1, 7):
        tm.on_vad(f"p{i}", "speech_start", i * 10)
    state = tm.tick(1000)
    assert state == {"holder": "p1", "overlap": ["p2", "p3"]}
    assert len(state["overlap"]) == 2
    assert state["holder"] not in state["overlap"]


def test_holder_resumes_before_release_silence_keeps_token():
    tm = TokenManager(DEFAULT_CFG)
    tm.on_vad("p1", "speech_start", 0)
    tm.tick(200)
    tm.on_vad("p2", "speech_start", 300)
    tm.tick(500)

    # p1 pauses for 400ms (< 700ms), then speaks again -> keeps token
    assert tm.on_vad("p1", "speech_end", 1500) is None
    assert tm.tick(1900) is None
    assert tm.on_vad("p1", "speech_start", 1900) is None
    assert tm.tick(2600) is None
    assert tm.state() == {"holder": "p1", "overlap": ["p2"]}
