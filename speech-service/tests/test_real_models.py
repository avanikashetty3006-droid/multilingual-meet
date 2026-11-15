"""SLOW tests with the REAL models. Run:  pytest -m slow -q
Needs: pip install -r requirements-real.txt, the converted NLLB folder (scripts/convert_nllb.ps1), and a real
3-second English speech recording saved as tests/data/hello_en.wav (16 kHz mono 16-bit; e.g. say "Hello everyone,
can you hear me?"). Models download on first run (about 1.5 GB)."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow
FIXTURE = Path(__file__).parent / "data" / "hello_en.wav"


@pytest.fixture(scope="module")
def pipe(tmp_path_factory):
    engines = pytest.importorskip("engines")
    from pipeline import Pipeline
    pytest.importorskip("faster_whisper")
    asr, mt, tts, _ = engines.load_real_pipeline_parts(preload_voices=())
    return Pipeline(asr, mt, tts, tmp_path_factory.mktemp("audio"), "http://localhost:8001")


def test_real_english_speech_is_transcribed_and_translated(pipe):
    if not FIXTURE.exists():
        pytest.skip("record tests/data/hello_en.wav first")
    r = pipe.run(FIXTURE.read_bytes(), "en", ["hi", "kn"], True)
    assert r["detected_lang"] == "en" and len(r["source_text"]) > 3
    assert set(r["translations"]) == {"hi", "kn"}
    assert all(t["text"] and t["audio_url"] for t in r["translations"].values())
    print(r)


def test_auto_detects_english(pipe):
    if not FIXTURE.exists():
        pytest.skip("record tests/data/hello_en.wav first")
    assert pipe.run(FIXTURE.read_bytes(), "auto", ["hi"], False)["detected_lang"] == "en"


def test_real_silence_and_quiet_noise_give_empty_text(pipe):
    import numpy as np
    from audio_io import encode_wav
    quiet = (np.random.default_rng(0).standard_normal(48000) * 0.02).astype(np.float32)  # above the silence gate
    for wav in (encode_wav(np.zeros(48000, dtype=np.float32), 16000), encode_wav(quiet, 16000)):
        assert pipe.run(wav, "en", ["hi"], False)["source_text"] == ""


def test_every_language_has_a_working_voice_and_translation(pipe):
    for lang in ("hi", "kn", "ta", "te", "ml", "mr"):
        text = pipe.mt.translate("Hello everyone, can you hear me?", "en", lang)
        wav = pipe.tts.synthesize(text, lang)
        assert text and len(wav) > 2000, lang
