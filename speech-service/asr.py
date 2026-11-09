"""ASR module (Whisper / faster-whisper interface).

Role 3 implementation skeleton.
"""

from typing import Tuple

def transcribe_audio(audio_wav_path_or_bytes, src_lang: str = "auto") -> Tuple[str, str]:
    """Transcribes audio using Whisper / faster-whisper.

    Returns:
        (detected_language, transcript_text)
    """
    # Skeleton: default fallback if running without heavy neural model weights
    detected = "en" if src_lang == "auto" else src_lang
    transcript = "Hello everyone, speaking here."
    return detected, transcript
