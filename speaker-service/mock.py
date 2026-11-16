"""Mock helpers for speaker-service (Role 4).

Step 1 / Contract A8 support:
- EnergyGateVadStream factory for `MOCK=1`
- Optional 5-second holder rotation (`MOCK_ROTATE=1`) for standalone frontend/call-server demos
  without live speech input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from vad import EnergyGateVadStream


def create_mock_vad_stream() -> EnergyGateVadStream:
    """Create a lightweight energy-gate VAD stream for MOCK=1 mode."""
    return EnergyGateVadStream()


@dataclass
class MockRoomRotator:
    """Rotates token holder through connected participants every `interval_ms`."""

    interval_ms: int = 5000
    _cursor: int = 0
    _last_rotate_ms: int = 0
    _last_state: Optional[tuple[Optional[str], tuple[str, ...]]] = field(default=(None, ()))

    def current_or_rotate(self, participant_ids: List[str], now_ms: int, force: bool = False) -> Optional[Dict[str, Any]]:
        if not participant_ids:
            state = (None, ())
            if self._last_state != state:
                self._last_state = state
                return {"holder": None, "overlap": []}
            return None

        if not force and self._last_rotate_ms != 0 and (now_ms - self._last_rotate_ms) < self.interval_ms:
            return None

        self._last_rotate_ms = now_ms
        ordered = sorted(participant_ids)
        holder = ordered[self._cursor % len(ordered)]
        self._cursor = (self._cursor + 1) % len(ordered)
        state = (holder, ())
        if self._last_state != state or force:
            self._last_state = state
            return {"holder": holder, "overlap": []}
        return None

    def snapshot(self, participant_ids: List[str]) -> Dict[str, Any]:
        if self._last_state is not None and self._last_state[0] in participant_ids:
            return {"holder": self._last_state[0], "overlap": list(self._last_state[1])}
        if not participant_ids:
            return {"holder": None, "overlap": []}
        holder = sorted(participant_ids)[0]
        self._last_state = (holder, ())
        return {"holder": holder, "overlap": []}
