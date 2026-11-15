"""
ASR Module (faster-whisper) - Role 3 Step 2
Implements Section A6 of shared/CONTRACT.md:
- Uses faster-whisper (int8 on CPU, float16 on CUDA)
- Transcribes 16kHz mono WAV chunks
- Language detection restricted to supported languages: en, hi, kn, ta, te, ml, mr
- VAD filter OFF (Speaker Service handles VAD), small beam size for low latency
"""
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger("speech-service.asr")

SUPPORTED_LANGUAGES = ["en", "hi", "kn", "ta", "te", "ml", "mr"]


class ASRModel:
    def __init__(
        self,
        model_size: str = "base",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
    ):
        self.model_size = model_size
        if device is None:
            # Check for CUDA availability
            import torch
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        if compute_type is None:
            self.compute_type = "float16" if self.device == "cuda" else "int8"
        else:
            self.compute_type = compute_type

        self.model = None

    def load(self):
        """Loads and warms up the faster-whisper model."""
        if self.model is not None:
            return

        logger.info(
            f"Loading faster-whisper model '{self.model_size}' on device '{self.device}' with '{self.compute_type}'..."
        )
        try:
            from faster_whisper import WhisperModel

            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load faster-whisper: {e}")
            raise

    def transcribe(
        self,
        audio_path_or_bytes: str,
        src_lang: str = "auto",
        prev_text: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Transcribes audio file to text.
        Returns: (transcript, detected_language)
        """
        if self.model is None:
            self.load()

        language_hint = None
        if src_lang and src_lang.lower() != "auto":
            clean_lang = src_lang.lower().strip()
            if clean_lang in SUPPORTED_LANGUAGES:
                language_hint = clean_lang

        try:
            # Beam size 1 or 2 for low latency, vad_filter=False because Role 4 already does VAD
            segments, info = self.model.transcribe(
                audio_path_or_bytes,
                language=language_hint,
                beam_size=1,
                vad_filter=False,
                initial_prompt=prev_text if prev_text else None,
            )

            detected_lang = info.language
            if detected_lang not in SUPPORTED_LANGUAGES:
                # Fallback to language hint or English if outside supported set
                detected_lang = language_hint if language_hint else "en"

            transcript_parts = [segment.text.strip() for segment in segments]
            transcript = " ".join([p for p in transcript_parts if p]).strip()

            return transcript, detected_lang

        except Exception as e:
            logger.warning(f"ASR transcription error: {e}")
            fallback_lang = language_hint if language_hint else "en"
            return "", fallback_lang
