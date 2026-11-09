"""Streaming Voice Activity Detection (VAD) module."""

import time
from typing import Optional, Tuple

class VadStream:
    """Processes 1024-byte PCM16 frames and detects speech boundaries.

    Rules:
    - speech_start after at least 200ms continuous speech.
    - speech_end after at least 700ms silence.
    """

    def __init__(self, participant_id: str, threshold: float = 0.5):
        self.participant_id = participant_id
        self.threshold = threshold
        self.is_speaking = False
        self.consecutive_speech_ms = 0
        self.consecutive_silence_ms = 0

    def process_frame(self, frame_bytes: bytes, ts_ms: int) -> Optional[str]:
        """Calculates energy/activity for 32ms frame.

        Returns 'speech_start', 'speech_end', or None.
        """
        # Calculate simple RMS energy for frame
        if len(frame_bytes) < 1024:
            return None

        # Check raw amplitude
        import struct
        samples = struct.unpack(f"<{len(frame_bytes)//2}h", frame_bytes)
        sum_sq = sum(s * s for s in samples)
        rms = (sum_sq / len(samples)) ** 0.5

        # Heuristic speech threshold
        has_speech = rms > 600

        frame_ms = 32

        if has_speech:
            self.consecutive_speech_ms += frame_ms
            self.consecutive_silence_ms = 0
            if not self.is_speaking and self.consecutive_speech_ms >= 200:
                self.is_speaking = True
                return "speech_start"
        else:
            self.consecutive_silence_ms += frame_ms
            self.consecutive_speech_ms = 0
            if self.is_speaking and self.consecutive_silence_ms >= 700:
                self.is_speaking = False
                return "speech_end"

        return None
