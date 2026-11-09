import asyncio
import io
import time
import wave
from pathlib import Path
from typing import Dict, Any, List, Optional

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

CANNED_TRANSLATIONS = {
    "hi": "सभी को नमस्कार, बैठक में आपका स्वागत है।",
    "kn": "ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ, ಸಭೆಗೆ ಸುಸ್ವಾಗತ.",
    "en": "Hello everyone, welcome to the meeting.",
    "ta": "அனைவருக்கும் வணக்கம், கூட்டத்திற்கு வரவேற்கிறோம்.",
    "te": "అందరికీ నమస్కారం, సమావేశానికి స్వాగతం.",
    "ml": "എല്ലാവർക്കും നമസ്കാരം, യോഗത്തിലേക്ക് സ്വാഗതം.",
    "mr": "सर्वांना नमस्कार, बैठकीत आपले स्वागत आहे.",
}

def create_dummy_wav(filepath: Path):
    """Generates a small valid 1-second 16kHz mono silent WAV file."""
    if filepath.exists():
        return
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00" * 32000)

async def mock_process_chunk(
    audio_bytes: bytes,
    room_id: str,
    participant_id: str,
    chunk_id: str,
    src_lang: str,
    tgt_langs: List[str],
    want_audio: bool,
    base_url: str = "http://localhost:8001",
) -> Dict[str, Any]:
    # Simulate processing delay (~800ms)
    t0 = time.time()
    await asyncio.sleep(0.8)
    now_ms = int(time.time() * 1000)

    detected_lang = "en" if src_lang == "auto" else src_lang
    source_text = "Hello everyone, welcome to the meeting."

    translations = {}
    for lang in tgt_langs:
        text = CANNED_TRANSLATIONS.get(lang, f"[{lang}] Translated text.")
        audio_url = None
        if want_audio:
            wav_filename = f"{chunk_id}_{lang}.wav"
            wav_path = AUDIO_DIR / wav_filename
            create_dummy_wav(wav_path)
            audio_url = f"{base_url}/audio/{wav_filename}"
        translations[lang] = {
            "text": text,
            "audio_url": audio_url,
        }

    elapsed_ms = int((time.time() - t0) * 1000)
    asr_time = 380
    mt_time = 170
    tts_time = 250 if want_audio else 0

    return {
        "chunk_id": chunk_id,
        "participant_id": participant_id,
        "detected_lang": detected_lang,
        "source_text": source_text,
        "translations": translations,
        "timings_ms": {
            "asr": asr_time,
            "mt": mt_time,
            "tts": tts_time,
            "total": elapsed_ms,
        },
    }
