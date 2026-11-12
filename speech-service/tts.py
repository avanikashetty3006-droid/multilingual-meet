"""
Text-to-Speech Module (gTTS / Indic-TTS) - Role 3 Step 4
"""
import logging
import os
import uuid

logger = logging.getLogger("speech-service.tts")

class TTSEngine:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def synthesize(self, text: str, lang: str) -> str:
        """
        Synthesizes text into audio and saves under output_dir.
        Returns the filename (e.g. 'uuid.wav').
        Failures should be caught by caller to return audio_url: None.
        """
        raise NotImplementedError("Real TTS pipeline available in Step 4. Run with MOCK=1.")
