"""Machine Translation module (IndicTrans2 wrapper interface).

Role 3 implementation skeleton.
"""

from typing import Dict

def translate_text(text: str, src_lang: str, tgt_lang: str) -> str:
    """Translates text from src_lang to tgt_lang.

    If src_lang == tgt_lang, returns text unchanged.
    """
    if src_lang == tgt_lang:
        return text

    # Placeholder / fallback translation dictionary
    fallbacks = {
        ("en", "hi"): "सभी को नमस्कार, बैठक में आपका स्वागत है।",
        ("en", "kn"): "ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ, ಸಭೆಗೆ ಸುಸ್ವಾಗತ.",
        ("hi", "en"): "Hello everyone, welcome to the meeting.",
        ("kn", "en"): "Hello everyone, welcome to the meeting.",
    }
    return fallbacks.get((src_lang, tgt_lang), f"[{tgt_lang}] {text}")
