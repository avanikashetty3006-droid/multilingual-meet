"""Text-to-Speech module (gTTS / Indic-TTS / Piper interface).

Role 3 implementation skeleton.
"""

from pathlib import Path
from typing import Optional
import wave

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

def synthesize_speech(text: str, lang: str, chunk_id: str) -> Optional[str]:
    """Synthesizes text to a 16kHz mono WAV file.

    Returns the filename of the generated audio file.
    """
    filename = f"{chunk_id}_{lang}.wav"
    output_path = AUDIO_DIR / filename

    try:
        # Generate dummy 1s PCM16 16kHz silent audio if TTS engine not installed
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        return filename
    except Exception as e:
        return None
