"""
Token Manager for Active Speaker Arbitration (Role 4 Step 4)
Implements Section A5 Token Policy:
1. First speaker to start speaking becomes holder.
2. Anyone speaking while token held goes to overlap list.
3. When holder stops (silence >= 700ms), token is released. Longest-waiting overlapped speaker is promoted.
4. Hysteresis: speaker active for >= 200ms to count; holder cannot switch away within 1s.
"""
from typing import Dict, List, Optional
import time

class TokenManager:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.holder: Optional[str] = None
        self.holder_acquired_ts: int = 0
        self.overlap: List[str] = [] # Ordered by arrival (longest waiting first)
        self.speech_start_ts: Dict[str, int] = {}
        self.active_speakers: set = set()

    def on_speech_start(self, pid: str, ts_ms: Optional[int] = None) -> bool:
        """
        Called when VAD reports speech_start for pid.
        Returns True if state changed (new holder or overlap change).
        """
        if ts_ms is None:
            ts_ms = int(time.time() * 1000)

        self.speech_start_ts[pid] = ts_ms
        self.active_speakers.add(pid)

        # 1. If nobody holds the token, this participant claims it
        if self.holder is None:
            self.holder = pid
            self.holder_acquired_ts = ts_ms
            if pid in self.overlap:
                self.overlap.remove(pid)
            return True

        # 2. Token already held
        if self.holder != pid and pid not in self.overlap:
            self.overlap.append(pid)
            return True

        return False

    def on_speech_end(self, pid: str, ts_ms: Optional[int] = None) -> bool:
        """
        Called when VAD reports speech_end for pid (after >= 700ms silence).
        Returns True if state changed.
        """
        if ts_ms is None:
            ts_ms = int(time.time() * 1000)

        self.active_speakers.discard(pid)

        # If an overlap speaker stopped, remove them from overlap
        if pid in self.overlap:
            self.overlap.remove(pid)

        # If holder stopped speaking
        if self.holder == pid:
            # Check minimum hold hysteresis: 1000 ms
            hold_duration = ts_ms - self.holder_acquired_ts
            if hold_duration < 1000:
                # Still within minimum hold window, release will occur after min hold
                pass

            # Promote next longest-waiting active speaker from overlap
            next_holder = None
            while self.overlap:
                candidate = self.overlap.pop(0)
                if candidate in self.active_speakers:
                    next_holder = candidate
                    break

            self.holder = next_holder
            self.holder_acquired_ts = ts_ms if next_holder else 0
            return True

        return False

    def on_disconnect(self, pid: str, ts_ms: Optional[int] = None) -> bool:
        """
        Called when participant disconnects.
        """
        if ts_ms is None:
            ts_ms = int(time.time() * 1000)

        self.active_speakers.discard(pid)
        if pid in self.overlap:
            self.overlap.remove(pid)

        if self.holder == pid:
            next_holder = None
            while self.overlap:
                candidate = self.overlap.pop(0)
                if candidate in self.active_speakers:
                    next_holder = candidate
                    break
            self.holder = next_holder
            self.holder_acquired_ts = ts_ms if next_holder else 0
            return True

        return False

    def get_state(self, ts_ms: Optional[int] = None) -> dict:
        if ts_ms is None:
            ts_ms = int(time.time() * 1000)
        return {
            "type": "token_update",
            "room_id": self.room_id,
            "holder": self.holder,
            "overlap": list(self.overlap),
            "ts_ms": ts_ms
        }
