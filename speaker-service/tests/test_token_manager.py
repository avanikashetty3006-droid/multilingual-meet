import pytest
from token_manager import TokenManager

def test_single_speaker_claims_token():
    tm = TokenManager("room1")
    changed = tm.on_speech_start("p-1", ts_ms=1000)
    assert changed is True
    state = tm.get_state()
    assert state["holder"] == "p-1"
    assert state["overlap"] == []

def test_second_speaker_goes_to_overlap():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", ts_ms=1000)
    changed = tm.on_speech_start("p-2", ts_ms=1200)
    assert changed is True
    state = tm.get_state()
    assert state["holder"] == "p-1"
    assert state["overlap"] == ["p-2"]

def test_holder_releases_and_promotes_overlap():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", ts_ms=1000)
    tm.on_speech_start("p-2", ts_ms=1200)
    
    # p-1 releases speech after 1500 ms (hold >= 1000ms satisfied)
    changed = tm.on_speech_end("p-1", ts_ms=2500)
    assert changed is True
    state = tm.get_state()
    assert state["holder"] == "p-2"
    assert state["overlap"] == []

def test_overlap_speaker_stops_before_promotion():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", ts_ms=1000)
    tm.on_speech_start("p-2", ts_ms=1200)
    # p-2 stops before p-1
    tm.on_speech_end("p-2", ts_ms=1400)
    assert "p-2" not in tm.overlap

    # p-1 stops: nobody in overlap, holder becomes None
    tm.on_speech_end("p-1", ts_ms=2200)
    state = tm.get_state()
    assert state["holder"] is None

def test_holder_disconnect_promotes_overlap():
    tm = TokenManager("room1")
    tm.on_speech_start("p-1", ts_ms=1000)
    tm.on_speech_start("p-2", ts_ms=1100)
    changed = tm.on_disconnect("p-1", ts_ms=1200)
    assert changed is True
    assert tm.holder == "p-2"
