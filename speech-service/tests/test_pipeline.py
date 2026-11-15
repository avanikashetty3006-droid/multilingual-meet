"""Pipeline tests with fake engines: fast, no ML libraries, no FastAPI needed.   pytest -q"""
import io
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from audio_io import decode_wav, encode_wav, resample, rms
from langs import MMS, NLLB, SUPPORTED, WHISPER
from pipeline import Pipeline, cleanup_old_audio

SR = 16000


def tone(seconds=1.0, amp=0.3, sr=SR):
    t = np.arange(int(sr * seconds)) / sr
    return encode_wav((amp * np.sin(2 * np.pi * 440 * t)).astype(np.float32), sr)


def silence(seconds=1.0):
    return encode_wav(np.zeros(int(SR * seconds), dtype=np.float32), SR)


def noise(seconds=1.0):
    rng = np.random.default_rng(1)
    return encode_wav((rng.standard_normal(int(SR * seconds)) * 0.001).astype(np.float32), SR)


class FakeASR:
    def __init__(self, segments=None, detected="en"):
        self.segments = segments if segments is not None else [{"text": " Hello everyone", "no_speech_prob": 0.01, "avg_logprob": -0.2}]
        self.detected = detected
        self.calls = []

    def transcribe(self, samples, language, prev_text):
        self.calls.append((len(samples), language, prev_text))
        return self.segments, self.detected


class FakeMT:
    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def translate(self, text, src, tgt):
        self.calls.append((text, src, tgt))
        if tgt in self.fail:
            raise RuntimeError("mt boom")
        return f"[{tgt}] {text}"


class FakeTTS:
    def __init__(self, fail=()):
        self.fail, self.calls = set(fail), []

    def synthesize(self, text, lang):
        self.calls.append((text, lang))
        if lang in self.fail:
            raise RuntimeError("tts boom")
        return tone(0.3)


@pytest.fixture
def mk(tmp_path):
    def make(asr=None, mt=None, tts=None):
        return Pipeline(asr or FakeASR(), mt or FakeMT(), tts or FakeTTS(), tmp_path / "audio", "http://x:8001")
    return make


def test_language_tables_cover_all_seven():
    assert set(NLLB) == set(MMS) == set(WHISPER) == set(SUPPORTED)
    assert NLLB["kn"] == "kan_Knda" and NLLB["hi"] == "hin_Deva" and NLLB["en"] == "eng_Latn"
    assert NLLB["ta"] == "tam_Taml" and NLLB["te"] == "tel_Telu" and NLLB["ml"] == "mal_Mlym" and NLLB["mr"] == "mar_Deva"


def test_happy_path_two_targets_with_audio(mk, tmp_path):
    p = mk()
    r = p.run(tone(), "en", ["hi", "kn"], True, "")
    assert r["detected_lang"] == "en" and r["source_text"] == "Hello everyone"
    assert set(r["translations"]) == {"hi", "kn"}
    assert r["translations"]["hi"]["text"] == "[hi] Hello everyone"
    for t in r["translations"].values():
        url = t["audio_url"]
        assert url.startswith("http://x:8001/audio/") and url.endswith(".wav")
        f = tmp_path / "audio" / url.rsplit("/", 1)[1]
        with wave.open(str(f)) as w:                       # a valid mono 16-bit wav
            assert (w.getnchannels(), w.getsampwidth()) == (1, 2)
    assert set(r["timings_ms"]) == {"asr", "mt", "tts"}


def test_want_audio_false_has_null_urls_and_zero_tts(mk):
    tts = FakeTTS()
    r = mk(tts=tts).run(tone(), "en", ["hi", "kn"], False)
    assert all(t["audio_url"] is None for t in r["translations"].values())
    assert r["timings_ms"]["tts"] == 0 and tts.calls == []


def test_target_equal_to_detected_language_skips_mt(mk):
    mt = FakeMT()
    r = mk(mt=mt).run(tone(), "en", ["en", "hi"], False)
    assert r["translations"]["en"]["text"] == "Hello everyone"
    assert [c[2] for c in mt.calls] == ["hi"]


def test_duplicate_targets_translated_once(mk):
    mt = FakeMT()
    r = mk(mt=mt).run(tone(), "en", ["hi", "hi", "kn", "hi"], False)
    assert list(r["translations"]) == ["hi", "kn"] and len(mt.calls) == 2


def test_one_failed_translation_is_left_out_not_fatal(mk):
    r = mk(mt=FakeMT(fail={"kn"})).run(tone(), "en", ["hi", "kn"], False)
    assert set(r["translations"]) == {"hi"} and r["source_text"] == "Hello everyone"


def test_tts_failure_keeps_text_and_nulls_audio(mk):
    r = mk(tts=FakeTTS(fail={"hi"})).run(tone(), "en", ["hi", "kn"], True)
    assert r["translations"]["hi"]["text"] == "[hi] Hello everyone" and r["translations"]["hi"]["audio_url"] is None
    assert r["translations"]["kn"]["audio_url"] is not None


def test_silence_noise_and_garbage_return_empty_without_calling_asr(mk):
    asr = FakeASR()
    p = mk(asr=asr)
    for wav in (silence(), noise(), b"not a wav", b""):
        r = p.run(wav, "en", ["hi"], True)
        assert r["source_text"] == "" and r["translations"] == {} and r["timings_ms"] == {"asr": 0, "mt": 0, "tts": 0}
    assert asr.calls == []


def test_hallucination_guard_drops_noisy_segments(mk):
    segs = [
        {"text": " Thank you.", "no_speech_prob": 0.9, "avg_logprob": -0.3},     # no-speech
        {"text": " Subtitles by", "no_speech_prob": 0.1, "avg_logprob": -1.4},   # low confidence
        {"text": " real words", "no_speech_prob": 0.1, "avg_logprob": -0.4},
    ]
    r = mk(asr=FakeASR(segs)).run(tone(), "en", ["hi"], False)
    assert r["source_text"] == "real words"


def test_all_segments_dropped_gives_empty_result_http200_shape(mk):
    segs = [{"text": " Thank you.", "no_speech_prob": 0.95, "avg_logprob": -0.2}]
    mt = FakeMT()
    r = mk(asr=FakeASR(segs), mt=mt).run(tone(), "en", ["hi"], True)
    assert r["source_text"] == "" and r["translations"] == {} and mt.calls == []


def test_auto_language_passes_none_and_uses_detected(mk):
    asr = FakeASR(detected="hi")
    r = mk(asr=asr).run(tone(), "auto", ["en"], False)
    assert asr.calls[0][1] is None and r["detected_lang"] == "hi"


def test_known_language_is_passed_to_asr_and_prev_text_forwarded(mk):
    asr = FakeASR()
    mk(asr=asr).run(tone(), "kn", ["en"], False, prev_text="earlier words")
    assert asr.calls[0][1:] == ("kn", "earlier words")


def test_unsupported_src_lang_is_treated_as_auto(mk):
    asr = FakeASR()
    mk(asr=asr).run(tone(), "fr", ["hi"], False)
    assert asr.calls[0][1] is None


def test_other_sample_rates_are_resampled_to_16k(mk):
    asr = FakeASR()
    mk(asr=asr).run(tone(1.0, sr=8000), "en", ["hi"], False)
    assert asr.calls[0][0] == 16000
    asr2 = FakeASR()
    mk(asr=asr2).run(tone(1.0, sr=44100), "en", ["hi"], False)
    assert asr2.calls[0][0] == 16000


def test_wav_helpers_roundtrip_and_stereo():
    x = (0.5 * np.sin(np.linspace(0, 100, 8000))).astype(np.float32)
    y, sr = decode_wav(encode_wav(x, 16000))
    assert sr == 16000 and np.abs(x - y).max() < 1e-3
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(np.stack([(x * 32767).astype("<i2")] * 2, axis=1).tobytes())
    z, _ = decode_wav(buf.getvalue())
    assert len(z) == len(x)
    assert decode_wav(b"junk") is None
    assert rms(np.zeros(10, dtype=np.float32)) == 0.0 and len(resample(x, 16000, 16000)) == len(x)


def test_cleanup_deletes_only_old_generated_files(tmp_path):
    d = tmp_path
    for n in ("old.wav", "new.wav", "sample.wav", "mock_hi.wav"):
        (d / n).write_bytes(b"x")
    now = time.time()
    import os
    os.utime(d / "old.wav", (now - 700, now - 700))
    os.utime(d / "sample.wav", (now - 9999, now - 9999))
    os.utime(d / "mock_hi.wav", (now - 9999, now - 9999))
    assert cleanup_old_audio(d, 600, now=now) == 1
    assert sorted(p.name for p in d.glob("*.wav")) == ["mock_hi.wav", "new.wav", "sample.wav"]
