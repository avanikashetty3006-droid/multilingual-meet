"""
Text-to-Speech Module (gTTS / Indic-TTS) - Role 3 Step 4
Implements Section A6 of shared/CONTRACT.md:
- Generates speech audio for target languages (en, hi, kn)
- Saves audio files under audio/
- Catches failures gracefully and returns None (request still succeeds)
- Auto-cleans generated audio files older than 10 minutes
"""
import io
import logging
import os
import time
import uuid
from typing import Optional

logger = logging.getLogger("speech-service.tts")

# ISO 639-1 code mapping for gTTS
GTTS_LANG_MAP = {
    "en": "en",
    "hi": "hi",
    "kn": "kn",
    "ta": "ta",
    "te": "te",
    "ml": "ml",
    "mr": "mr",
}


class TTSEngine:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def synthesize(self, text: str, lang: str) -> Optional[str]:
        """
        Synthesizes text into audio and saves under output_dir.
        Returns the filename (e.g. 'abc.wav'), or None on failure.
        """
        if not text or not text.strip():
            return None

        # Clean old temporary audio files periodically
        self._cleanup_old_files()

        target_lang = GTTS_LANG_MAP.get(lang.lower(), "en")
        filename = f"{uuid.uuid4().hex[:12]}.wav"
        filepath = os.path.join(self.output_dir, filename)

        try:
            from gtts import gTTS

            tts = gTTS(text=text, lang=target_lang, slow=False)
            
            # Save audio
            # Note: gTTS outputs MP3 audio stream. To ensure browser compatibility,
            # we save the stream. Browsers can decode it directly.
            tts.save(filepath)
            logger.info(f"Generated TTS audio for '{lang}': {filename}")
            return filename

        except Exception as e:
            logger.warning(f"TTS synthesis failed for lang='{lang}', text='{text[:30]}...': {e}")
            # Failure must NOT crash the request; return None as required by Contract A6
            return None

    def _cleanup_old_files(self, max_age_seconds: int = 600):
        """Removes generated wav files older than max_age_seconds (default 10 mins)."""
        now = time.time()
        try:
            for fname in os.listdir(self.output_dir):
                # Preserve sample and mock files
                if fname.startswith("sample") or fname.startswith("mock_"):
                    continue
                fpath = os.path.join(self.output_dir, fname)
                if os.path.isfile(fpath) and fname.endswith(".wav"):
                    if now - os.path.getmtime(fpath) > max_age_seconds:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
        except Exception:
            pass
