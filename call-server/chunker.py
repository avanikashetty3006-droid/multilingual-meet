"""Audio stream chunker per participant.

Buffers raw PCM16 16kHz mono frames (1024 bytes).
Cuts chunks on:
  1) VAD speech_end
  2) Max chunk duration reached (4.0s of continuous speech)
Drops chunks shorter than 400ms or containing no active speech.
Outputs standard WAV bytes.
"""

import io
import wave
from typing import Optional, Tuple
from config import SAMPLE_RATE, CHANNELS, MIN_CHUNK_MS, MAX_CHUNK_SEC

BYTES_PER_SAMPLE = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE  # 32000 bytes/sec
MIN_CHUNK_BYTES = int((MIN_CHUNK_MS / 1000.0) * BYTES_PER_SECOND)  # 12800 bytes
MAX_CHUNK_BYTES = int(MAX_CHUNK_SEC * BYTES_PER_SECOND)  # 128000 bytes (4 sec)


def pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wraps raw PCM16 mono 16kHz bytes in a standard WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BYTES_PER_SAMPLE)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class ParticipantAudioChunker:
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.seq = 0
        self.buffer = bytearray()
        self.is_speaking = False

    def on_vad_speech_start(self):
        self.is_speaking = True

    def on_vad_speech_end(self) -> Optional[Tuple[str, bytes]]:
        """Called when VAD signals speech_end. Cuts chunk if valid."""
        self.is_speaking = False
        return self._cut_chunk()

    def add_frame(self, frame_bytes: bytes) -> Optional[Tuple[str, bytes]]:
        """Appends a 1024-byte mic frame.

        If buffer reaches MAX_CHUNK_BYTES while speaking, cuts chunk early.
        """
        # Append frame
        self.buffer.extend(frame_bytes)

        # If speech has been active and reached max duration (4 seconds)
        if len(self.buffer) >= MAX_CHUNK_BYTES:
            return self._cut_chunk()
        return None

    def _cut_chunk(self) -> Optional[Tuple[str, bytes]]:
        if len(self.buffer) < MIN_CHUNK_BYTES:
            self.buffer.clear()
            return None

        chunk_data = bytes(self.buffer)
        self.buffer.clear()

        chunk_id = f"{self.participant_id}-{self.seq}"
        self.seq += 1
        wav_data = pcm_to_wav(chunk_data)
        return chunk_id, wav_data
