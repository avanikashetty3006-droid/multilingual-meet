"""Canned responses for MOCK=1 so Role 2 can integrate before the real models exist."""
import asyncio
import math
import struct
import wave
from array import array
from pathlib import Path

SAMPLE_RATE = 16000

# Different beep pitch per language so you can hear which file played.
BEEPS = {"sample": 440, "mock_en": 523, "mock_hi": 659, "mock_kn": 784}

TEXT = {
    "en": "Hello everyone, can you hear me?",
    "hi": "सभी को नमस्कार, क्या आप मुझे सुन सकते हैं?",
    "kn": "ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ, ನಿಮಗೆ ನನ್ನ ಮಾತು ಕೇಳಿಸುತ್ತಿದೆಯೇ?",
}


def write_beep(path: Path, freq: int, seconds: float = 0.6) -> None:
    n = int(SAMPLE_RATE * seconds)
    frames = b"".join(
        struct.pack("<h", int(9000 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)))
        for i in range(n)
    )
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(frames)


def ensure_audio_files(audio_dir: Path) -> None:
    audio_dir.mkdir(exist_ok=True)
    for name, freq in BEEPS.items():
        path = audio_dir / f"{name}.wav"
        if not path.exists():
            write_beep(path, freq)


def is_silent(wav_bytes: bytes, threshold: int = 300) -> bool:
    """True for silence, very quiet noise, or an unreadable WAV (never crash)."""
    try:
        import io

        with wave.open(io.BytesIO(wav_bytes)) as w:
            samples = array("h", w.readframes(w.getnframes()))
    except Exception:
        return True
    if not samples:
        return True
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    return rms < threshold


async def process(wav_bytes, src_lang, tgt_langs, want_audio, public_url):
    """Pretend to run ASR -> MT -> TTS (about 800 ms) and return the response body."""
    if is_silent(wav_bytes):
        return {
            "detected_lang": src_lang if src_lang != "auto" else "en",
            "source_text": "",
            "translations": {},
            "timings_ms": {"asr": 0, "mt": 0, "tts": 0},
        }

    detected = src_lang if src_lang in TEXT else "en"
    await asyncio.sleep(0.3)  # fake ASR
    await asyncio.sleep(0.3)  # fake MT
    tts_ms = 0
    if want_audio:
        await asyncio.sleep(0.2)  # fake TTS
        tts_ms = 200

    translations = {}
    for lang in tgt_langs:
        text = TEXT.get(lang, f"[mock {lang}] {TEXT['en']}")
        audio_url = None
        if want_audio:
            file = f"mock_{lang}.wav" if lang in ("en", "hi", "kn") else "sample.wav"
            audio_url = f"{public_url}/audio/{file}"
        translations[lang] = {"text": text, "audio_url": audio_url}

    return {
        "detected_lang": detected,
        "source_text": TEXT[detected],
        "translations": translations,
        "timings_ms": {"asr": 300, "mt": 300, "tts": tts_ms},
    }
