import io
import wave
from typing import Optional

SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
MIN_CHUNK_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 0.4)  # 0.4s
MAX_CHUNK_BYTES = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 4.0)  # 4.0s

class AudioChunker:
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.buffer = bytearray()
        self.seq = 0

    def add_frame(self, frame_bytes: bytes) -> Optional[bytes]:
        """
        Adds 1024-byte frame. If buffer reaches 4.0s, cuts and returns WAV bytes.
        """
        self.buffer.extend(frame_bytes)
        if len(self.buffer) >= MAX_CHUNK_BYTES:
            return self.flush()
        return None

    def flush(self) -> Optional[bytes]:
        """
        Flushes buffer if longer than min duration (0.4s).
        Returns PCM16 16kHz mono WAV bytes.
        """
        if len(self.buffer) < MIN_CHUNK_BYTES:
            self.buffer.clear()
            return None

        pcm_data = bytes(self.buffer)
        self.buffer.clear()

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav:
            wav.setnchannels(CHANNELS)
            wav.setsampwidth(BYTES_PER_SAMPLE)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm_data)

        return wav_io.getvalue()

    def next_chunk_id(self) -> str:
        cid = f"{self.participant_id}-{self.seq}"
        self.seq += 1
        return cid
