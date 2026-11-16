"""Engine selection / pivot / fallback logic with fakes. No ML libraries needed."""
import pytest

import engines
from engines import ChainTTS, IndicTrans2MT, build_mt, build_tts, parse_list


def test_parse_list():
    assert parse_list("mms, GTTS ,,") == ["mms", "gtts"]
    assert parse_list("") == []


class Ok:
    def __init__(self, tag): self.tag, self.calls = tag, 0
    def synthesize(self, text, lang):
        self.calls += 1
        return self.tag


class Bad:
    def __init__(self): self.calls = 0
    def synthesize(self, text, lang):
        self.calls += 1
        raise RuntimeError("down")


def test_chain_uses_first_working_engine_and_stops():
    a, b = Ok(b"A"), Ok(b"B")
    assert ChainTTS([a, b]).synthesize("x", "hi") == b"A" and b.calls == 0


def test_chain_falls_back_in_order():
    bad, ok = Bad(), Ok(b"B")
    assert ChainTTS([bad, ok]).synthesize("x", "hi") == b"B" and bad.calls == 1


def test_chain_raises_when_all_fail():
    with pytest.raises(RuntimeError, match="all TTS engines failed"):
        ChainTTS([Bad(), Bad()]).synthesize("x", "hi")
    with pytest.raises(ValueError):
        ChainTTS([])


def test_build_tts_skips_unavailable_engines(monkeypatch):
    class NoGtts:
        def __init__(self): raise ImportError("no gtts")
    monkeypatch.setattr(engines, "MmsTTS", lambda device: Ok(b"M"))
    monkeypatch.setattr(engines, "GttsTTS", NoGtts)
    t = build_tts("mms,gtts", "cpu")
    assert t.synthesize("x", "hi") == b"M"                 # single working engine is returned directly


def test_build_tts_chain_and_errors(monkeypatch):
    monkeypatch.setattr(engines, "MmsTTS", lambda device: Ok(b"M"))
    monkeypatch.setattr(engines, "GttsTTS", lambda: Ok(b"G"))
    assert isinstance(build_tts("mms,gtts", "cpu"), ChainTTS)
    with pytest.raises(RuntimeError, match="no TTS engine"):
        build_tts("bogus", "cpu")
    def boom(*a, **k): raise ImportError("x")
    monkeypatch.setattr(engines, "MmsTTS", boom)
    monkeypatch.setattr(engines, "GttsTTS", boom)
    with pytest.raises(RuntimeError, match="no TTS engine"):
        build_tts("mms,gtts", "cpu")


def test_build_mt_rejects_unknown_engine():
    with pytest.raises(ValueError, match="unknown MT_ENGINE"):
        build_mt("google-web", "cpu")


def _mt(monkeypatch):
    mt = IndicTrans2MT.__new__(IndicTrans2MT)   # skip the heavy __init__
    calls = []
    monkeypatch.setattr(mt, "_direct", lambda text, s, t: calls.append((s, t)) or f"<{t}:{text}>", raising=False)
    return mt, calls


def test_indictrans2_uses_direct_models_for_english(monkeypatch):
    mt, calls = _mt(monkeypatch)
    assert mt.translate("hello", "en", "hi") == "<hi:hello>" and calls == [("en", "hi")]
    mt, calls = _mt(monkeypatch)
    mt.translate("namaste", "hi", "en")
    assert calls == [("hi", "en")]


def test_indictrans2_pivots_indic_to_indic_through_english(monkeypatch):
    mt, calls = _mt(monkeypatch)
    assert mt.translate("namaste", "hi", "kn") == "<kn:<en:namaste>>"
    assert calls == [("hi", "en"), ("en", "kn")]


def test_same_language_is_returned_unchanged(monkeypatch):
    mt, calls = _mt(monkeypatch)
    assert mt.translate("hello", "kn", "kn") == "hello" and calls == []
