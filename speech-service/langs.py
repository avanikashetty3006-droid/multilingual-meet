"""Language code tables (the 7 languages of the project)."""

SUPPORTED = ("en", "hi", "kn", "ta", "te", "ml", "mr")

# NLLB-200 codes (verified against the NLLB language list)
NLLB = {
    "en": "eng_Latn", "hi": "hin_Deva", "kn": "kan_Knda", "ta": "tam_Taml",
    "te": "tel_Telu", "ml": "mal_Mlym", "mr": "mar_Deva",
}

# facebook/mms-tts-<code> model suffixes (ISO 639-3)
MMS = {
    "en": "eng", "hi": "hin", "kn": "kan", "ta": "tam",
    "te": "tel", "ml": "mal", "mr": "mar",
}

# Whisper uses the same two-letter codes as the contract for these languages.
WHISPER = {c: c for c in SUPPORTED}
