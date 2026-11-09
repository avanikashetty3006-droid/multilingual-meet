import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from token_manager import TokenManager

def test_single_speaker_gets_token():
    tm = TokenManager("room1")
    changed = tm.on_speech_start("p-1", 1000)
    assert changed is True
    assert tm.holder == "p-1"
    assert tm.overlap == []

def test_second_speaker_goes_to_overlap():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", 1000)

    # Second speaker starts
    changed = tm.on_speech_start("p-2", 1200)
    assert changed is True
    assert tm.holder == "p-1"
    assert tm.overlap == ["p-2"]

def test_promotion_from_overlap_on_release():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", 1000)
    tm.on_speech_start("p-2", 1200)

    # Holder finishes speech after 1.5 seconds (respects 1s hold)
    changed = tm.on_speech_end("p-1", 2500)
    assert changed is True
    assert tm.holder == "p-2"
    assert tm.overlap == []

def test_flicker_under_200ms_ignored():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", 1000)
    tm.on_speech_start("p-2", 1200)

    # p-2 stops after 100ms (flicker)
    changed = tm.on_speech_end("p-2", 1300)
    assert tm.holder == "p-1"
    assert tm.overlap == []

def test_holder_disconnect():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", 1000)
    tm.on_speech_start("p-2", 1100)

    # p-1 leaves abruptly
    changed = tm.on_participant_leave("p-1", 1200)
    assert changed is True
    assert tm.holder == "p-2"
