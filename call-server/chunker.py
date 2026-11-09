"""Audio stream chunker per participant.

Buffers raw PCM16 16kHz mono frames (1024 bytes / 32 ms).
- Rolling pre-roll buffer of last 300ms (10 frames) prepended on speech_start.
- Only buffers frames while speaking.
- Cuts chunks on:
  1) 4.0s of continuous speech (then keeps collecting)
  2) VAD speech_end
- Drops chunks shorter than 400ms or containing pure silence.
- Wrong-sized frames (not 1024 bytes) are ignored.
- Outputs standard WAV bytes with sequential IDs: {participant_id}-{seq}.
"""

import collections
import io
import wave
from typing import Optional, Tuple
from config import SAMPLE_RATE, CHANNELS, MIN_CHUNK_MS, MAX_CHUNK_SEC

BYTES_PER_SAMPLE = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE  # 32000 bytes/sec
FRAME_BYTES = 1024
MIN_CHUNK_BYTES = int((MIN_CHUNK_MS / 1000.0) * BYTES_PER_SECOND)  # 12800 bytes
MAX_CHUNK_BYTES = int(MAX_CHUNK_SEC * BYTES_PER_SECOND)  # 128000 bytes (4 sec)
PRE_ROLL_FRAMES = 10  # ~320ms


def pcm_to_wav(pcm_bytes: bytes) -> bytes:
    """Wraps raw PCM16 mono 16kHz bytes in a standard WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(BYTES_PER_SAMPLE)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def is_pure_silence(pcm_bytes: bytes) -> bool:
    """Returns True if the audio buffer consists entirely of zero bytes or silent samples."""
    if not pcm_bytes:
        return True
    # Fast check: all zeros
    if pcm_bytes == b"\x00" * len(pcm_bytes):
        return True
    # Check max absolute amplitude
    import struct
    count = len(pcm_bytes) // 2
    samples = struct.unpack(f"<{count}h", pcm_bytes)
    max_amp = max(abs(s) for s in samples)
    return max_amp < 150  # Noise floor threshold


class ParticipantAudioChunker:
    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.seq = 0
        self.buffer = bytearray()
        self.is_speaking = False
        self.pre_roll = collections.deque(maxlen=PRE_ROLL_FRAMES)

    def on_vad_speech_start(self):
        """Called when VAD signals speech_start.

        Enters speaking state and prepends the rolling pre-roll.
        """
        self.is_speaking = True
        self.buffer.clear()
        for frame in self.pre_roll:
            self.buffer.extend(frame)

    def on_vad_speech_end(self) -> Optional[Tuple[str, bytes]]:
        """Called when VAD signals speech_end. Cuts chunk if valid."""
        if not self.is_speaking:
            return None
        self.is_speaking = False
        return self._cut_chunk()

    def add_frame(self, frame_bytes: bytes) -> Optional[Tuple[str, bytes]]:
        """Adds a mic frame.

        - If frame length != 1024, ignores frame.
        - Updates rolling pre-roll buffer.
        - If speaking, buffers frame and cuts chunk at 4s continuous speech.
        """
        if len(frame_bytes) != FRAME_BYTES:
            return None

        # Always maintain rolling pre-roll
        self.pre_roll.append(frame_bytes)

        if not self.is_speaking:
            return None

        self.buffer.extend(frame_bytes)

        # If speech reaches 4.0 seconds, cut a chunk and continue collecting
        if len(self.buffer) >= MAX_CHUNK_BYTES:
            return self._cut_chunk()
        return None

    def _cut_chunk(self) -> Optional[Tuple[str, bytes]]:
        if len(self.buffer) < MIN_CHUNK_BYTES:
            self.buffer.clear()
            return None

        chunk_data = bytes(self.buffer)
        self.buffer.clear()

        # Reject pure silence
        if is_pure_silence(chunk_data):
            return None

        chunk_id = f"{self.participant_id}-{self.seq}"
        self.seq += 1
        wav_data = pcm_to_wav(chunk_data)
        return chunk_id, wav_data
