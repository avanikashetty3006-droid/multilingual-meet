"""
VAD Stream Processor (Role 4 Step 2/3)
Takes 1024-byte PCM frames (16kHz mono) and detects speech_start / speech_end.
"""
from typing import Optional

class VadStream:
    def __init__(self, room_id: str, participant_id: str):
        self.room_id = room_id
        self.participant_id = participant_id
        self.is_speaking = False
        self.speech_frames = 0
        self.silence_frames = 0

    def process_frame(self, frame_bytes: bytes) -> Optional[str]:
        """
        Processes 1024 bytes (512 samples = 32 ms).
        Returns 'speech_start', 'speech_end', or None.
        Real implementation uses Silero VAD.
        """
        if len(frame_bytes) != 1024:
            return None
        # Stub for offline/real VAD
        return None
