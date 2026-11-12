import asyncio
import os
from typing import Dict, List, Optional

SPEECH_PUBLIC_URL = os.getenv("SPEECH_PUBLIC_URL", "http://localhost:8001").rstrip("/")

CANNED_TEXTS = {
    "en": "Hello everyone, welcome to the multilingual meeting.",
    "hi": "नमस्ते आप सभी का बहुभाषी बैठक में स्वागत है।",
    "kn": "ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ, ಬಹುಭಾಷಾ ಸಭೆಗೆ ಸುಸ್ವಾಗತ.",
    "ta": "அனைவருக்கும் வணக்கம், பன்மொழி சந்திப்பிற்கு வரவேற்கிறோம்.",
    "te": "అందరికీ నమస్కారం, బహుభాషా సమావేశానికి స్వాగతం.",
    "ml": "എല്ലാവർക്കും സ്വാഗതം, ബഹുഭാഷാ യോഗത്തിലേക്ക് സ്വാഗതം.",
    "mr": "सर्वांना नमस्कार, बहुभाषिक बैठकीत आपले स्वागत आहे.",
}

MOCK_AUDIO_FILES = {
    "en": "mock_en.wav",
    "hi": "mock_hi.wav",
    "kn": "mock_kn.wav",
}

async def process_chunk_mock(
    chunk_id: str,
    participant_id: str,
    src_lang: str,
    tgt_langs: List[str],
    want_audio: bool,
    is_silence: bool = False,
    prev_text: Optional[str] = None
) -> dict:
    """
    Mock processor matching Section A6 of CONTRACT.md.
    Emulates ~800 ms processing latency and returns canned translations.
    """
    if is_silence:
        # A6: Silence or noise returns HTTP 200 with source_text "" and empty translations
        return {
            "chunk_id": chunk_id,
            "participant_id": participant_id,
            "detected_lang": src_lang if src_lang != "auto" else "en",
            "source_text": "",
            "translations": {},
            "timings_ms": {
                "asr": 100,
                "mt": 0,
                "tts": 0,
                "total": 100
            }
        }

    # Simulate realistic pipeline latency (~800 ms total)
    await asyncio.sleep(0.8)

    detected_lang = "en" if src_lang in ("auto", "", None) else src_lang
    source_text = CANNED_TEXTS.get(detected_lang, f"Speaking in {detected_lang}")

    translations: Dict[str, dict] = {}
    for lang in tgt_langs:
        trans_text = CANNED_TEXTS.get(lang, f"[Translated to {lang}]: {source_text}")
        audio_url = None
        if want_audio:
            mock_file = MOCK_AUDIO_FILES.get(lang, "sample.wav")
            audio_url = f"{SPEECH_PUBLIC_URL}/audio/{mock_file}"

        translations[lang] = {
            "text": trans_text,
            "audio_url": audio_url
        }

    tts_time = 220 if want_audio else 0
    total_time = 380 + 200 + tts_time

    return {
        "chunk_id": chunk_id,
        "participant_id": participant_id,
        "detected_lang": detected_lang,
        "source_text": source_text,
        "translations": translations,
        "timings_ms": {
            "asr": 380,
            "mt": 200,
            "tts": tts_time,
            "total": total_time
        }
    }
