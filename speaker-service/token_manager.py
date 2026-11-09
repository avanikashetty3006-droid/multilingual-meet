"""Token Manager state machine implementing A5 contract rules."""

from typing import Dict, List, Optional, Set, Tuple


class TokenManager:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.holder: Optional[str] = None
        self.holder_acquired_ts: int = 0
        self.overlap: List[str] = []
        self.active_speakers: Set[str] = set()
        self.speech_start_times: Dict[str, int] = {}
        self.overlap_enter_times: Dict[str, int] = {}

    def on_speech_start(self, pid: str, ts_ms: int) -> bool:
        """Called when VAD signals speech_start for participant.

        Returns True if state (holder or overlap) changed.
        """
        self.active_speakers.add(pid)
        self.speech_start_times[pid] = ts_ms

        changed = False
        if self.holder is None:
            self.holder = pid
            self.holder_acquired_ts = ts_ms
            changed = True
        elif pid != self.holder and pid not in self.overlap:
            self.overlap.append(pid)
            self.overlap_enter_times[pid] = ts_ms
            changed = True

        return changed

    def on_speech_end(self, pid: str, ts_ms: int) -> bool:
        """Called when VAD signals speech_end for participant.

        Returns True if state (holder or overlap) changed.
        """
        self.active_speakers.discard(pid)
        start_ts = self.speech_start_times.pop(pid, ts_ms)
        duration = ts_ms - start_ts

        # Hysteresis: ignore flickers < 200ms
        if duration < 200:
            if pid in self.overlap:
                self.overlap.remove(pid)
                self.overlap_enter_times.pop(pid, None)
                return True
            return False

        changed = False

        if pid == self.holder:
            # Respect 1.0s minimum hold duration
            time_held = ts_ms - self.holder_acquired_ts
            if time_held >= 1000 or not self.overlap:
                self._release_holder(ts_ms)
                changed = True
        elif pid in self.overlap:
            self.overlap.remove(pid)
            self.overlap_enter_times.pop(pid, None)
            changed = True

        return changed

    def on_participant_leave(self, pid: str, ts_ms: int) -> bool:
        """Handles disconnected participant releasing holder or overlap."""
        self.active_speakers.discard(pid)
        self.speech_start_times.pop(pid, None)
        self.overlap_enter_times.pop(pid, None)

        changed = False
        if pid in self.overlap:
            self.overlap.remove(pid)
            changed = True

        if pid == self.holder:
            self._release_holder(ts_ms)
            changed = True

        return changed

    def _release_holder(self, ts_ms: int):
        # Promote longest-waiting overlapped participant who is still speaking
        candidate = None
        for pid in list(self.overlap):
            if pid in self.active_speakers:
                candidate = pid
                break

        if candidate:
            self.overlap.remove(candidate)
            self.overlap_enter_times.pop(candidate, None)
            self.holder = candidate
            self.holder_acquired_ts = ts_ms
        else:
            self.holder = None
            self.holder_acquired_ts = 0

    def state(self, ts_ms: int = 0) -> Dict:
        return {
            "type": "token_update",
            "room_id": self.room_id,
            "holder": self.holder,
            "overlap": list(self.overlap),
            "ts_ms": ts_ms,
        }
