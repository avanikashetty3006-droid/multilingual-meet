"""Pure Python speaking-token state machine (Contract A5).

No asyncio, no websockets, no wall-clock calls inside. All timestamps (`now_ms`)
are passed explicitly by the caller so unit tests are deterministic and fast.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


DEFAULT_TOKEN_CONFIG: Dict[str, int] = {
    "min_speech_ms": 200,
    "release_silence_ms": 700,
    "min_hold_ms": 1000,
    "max_overlap": 2,
}


def _extract_token_settings(config: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """Normalize flat or nested (shared/config.yaml) configuration dicts."""
    if config is None:
        shared_path = Path(__file__).resolve().parent.parent / "shared" / "config.yaml"
        if shared_path.exists():
            with open(shared_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config = loaded
        if config is None:
            config = {}

    token_section = config.get("token") if isinstance(config.get("token"), dict) else {}
    limits_section = config.get("limits") if isinstance(config.get("limits"), dict) else {}

    def _pick(key: str, section: Dict[str, Any]) -> int:
        if key in config:
            return int(config[key])
        if key in section:
            return int(section[key])
        return DEFAULT_TOKEN_CONFIG[key]

    return {
        "min_speech_ms": _pick("min_speech_ms", token_section),
        "release_silence_ms": _pick("release_silence_ms", token_section),
        "min_hold_ms": _pick("min_hold_ms", token_section),
        "max_overlap": _pick("max_overlap", limits_section),
    }


@dataclass
class _PendingSpeaker:
    participant_id: str
    start_ms: int
    seq: int


class TokenManager:
    """Deterministic per-room speaking token state machine.

    Policy (CONTRACT A5 + shared/config.yaml):
    1. If nobody holds the token, the first confirmed speaker becomes `holder`.
    2. Confirmed speakers who start while a token is held enter `overlap`,
       capped at `max_overlap` (extra talkers ignored; longest-waiting kept).
    3. When the holder goes quiet for >= `release_silence_ms` AND has held the
       token for >= `min_hold_ms`, the token is released. The longest-waiting
       active overlap speaker becomes the new `holder` (or None if none).
    4. Speakers must remain active for >= `min_speech_ms` before counting
       (short blips are ignored).
    5. Disconnecting removes a participant immediately from pending, overlap,
       or holder (releasing/promoting immediately).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        settings = _extract_token_settings(config)
        self.min_speech_ms: int = max(0, settings["min_speech_ms"])
        self.release_silence_ms: int = max(0, settings["release_silence_ms"])
        self.min_hold_ms: int = max(0, settings["min_hold_ms"])
        self.max_overlap: int = max(0, settings["max_overlap"])

        self._holder: Optional[str] = None
        self._holder_since_ms: Optional[int] = None
        self._holder_silence_since_ms: Optional[int] = None

        # Ordered FIFO list of active overlap participant IDs (longest-waiting first)
        self._overlap: List[str] = []
        # Speakers currently active < min_speech_ms waiting for confirmation
        self._pending: Dict[str, _PendingSpeaker] = {}
        self._arrival_seq: int = 0
        self._last_emitted: Tuple[Optional[str], Tuple[str, ...]] = (None, ())

    def state(self) -> Dict[str, Any]:
        """Return current snapshot {"holder": str|None, "overlap": [str, ...]}."""
        return {
            "holder": self._holder,
            "overlap": list(self._overlap),
        }

    def on_vad(self, participant_id: str, vad_state: str, now_ms: int) -> Optional[Dict[str, Any]]:
        """Process a VAD transition ("speech_start" or "speech_end") at `now_ms`.

        Returns new state dict if holder or overlap changed, else None.
        """
        self._advance(now_ms)

        if vad_state == "speech_start":
            if participant_id == self._holder:
                # Holder resumed speaking before release_silence_ms elapsed
                self._holder_silence_since_ms = None
            elif participant_id in self._overlap or participant_id in self._pending:
                # Duplicate speech_start while already active/pending
                pass
            else:
                self._arrival_seq += 1
                if self.min_speech_ms <= 0:
                    self._activate_speaker(participant_id, now_ms)
                else:
                    self._pending[participant_id] = _PendingSpeaker(
                        participant_id=participant_id,
                        start_ms=now_ms,
                        seq=self._arrival_seq,
                    )

        elif vad_state == "speech_end":
            # Discard pending speaker if blip lasted < min_speech_ms
            if participant_id in self._pending:
                del self._pending[participant_id]

            if participant_id == self._holder:
                if self._holder_silence_since_ms is None:
                    self._holder_silence_since_ms = now_ms
                self._advance(now_ms)
            elif participant_id in self._overlap:
                # Overlap speaker stopped speaking -> leaves overlap immediately
                self._overlap.remove(participant_id)

        else:
            raise ValueError(f"Unsupported VAD state: {vad_state!r}")

        return self._emit_if_changed()

    def on_speech_start(self, participant_id: str, now_ms: int) -> Optional[Dict[str, Any]]:
        """Convenience alias for `on_vad(participant_id, "speech_start", now_ms)`."""
        return self.on_vad(participant_id, "speech_start", now_ms)

    def on_speech_end(self, participant_id: str, now_ms: int) -> Optional[Dict[str, Any]]:
        """Convenience alias for `on_vad(participant_id, "speech_end", now_ms)`."""
        return self.on_vad(participant_id, "speech_end", now_ms)

    def on_disconnect(self, participant_id: str, now_ms: int) -> Optional[Dict[str, Any]]:
        """Remove a disconnected participant immediately and re-evaluate token."""
        self._advance(now_ms)

        self._pending.pop(participant_id, None)
        if participant_id in self._overlap:
            self._overlap.remove(participant_id)

        if participant_id == self._holder:
            self._holder = None
            self._holder_since_ms = None
            self._holder_silence_since_ms = None
            self._promote_next_holder(now_ms)

        return self._emit_if_changed()

    def tick(self, now_ms: int) -> Optional[Dict[str, Any]]:
        """Advance time-based hysteresis (min_speech_ms & release_silence_ms)."""
        self._advance(now_ms)
        return self._emit_if_changed()

    def _advance(self, now_ms: int) -> None:
        while True:
            next_confirm_ms: Optional[int] = None
            next_pending: Optional[_PendingSpeaker] = None
            for p in self._pending.values():
                c_ms = p.start_ms + self.min_speech_ms
                if c_ms <= now_ms:
                    if (
                        next_pending is None
                        or c_ms < next_confirm_ms  # type: ignore[operator]
                        or (c_ms == next_confirm_ms and p.seq < next_pending.seq)
                    ):
                        next_confirm_ms = c_ms
                        next_pending = p

            next_release_ms: Optional[int] = None
            if self._holder is not None and self._holder_silence_since_ms is not None:
                candidate_release = max(
                    self._holder_silence_since_ms + self.release_silence_ms,
                    (self._holder_since_ms if self._holder_since_ms is not None else now_ms) + self.min_hold_ms,
                )
                if candidate_release <= now_ms:
                    next_release_ms = candidate_release

            if next_pending is None and next_release_ms is None:
                break

            if next_pending is not None and (next_release_ms is None or next_confirm_ms <= next_release_ms):  # type: ignore[operator]
                self._pending.pop(next_pending.participant_id, None)
                self._activate_speaker(next_pending.participant_id, next_confirm_ms)  # type: ignore[arg-type]
            else:
                self._holder = None
                self._holder_since_ms = None
                self._holder_silence_since_ms = None
                self._promote_next_holder(next_release_ms)  # type: ignore[arg-type]

    def _activate_speaker(self, participant_id: str, active_since_ms: int) -> None:
        if self._holder is None:
            self._holder = participant_id
            self._holder_since_ms = active_since_ms
            self._holder_silence_since_ms = None
            return

        if participant_id == self._holder or participant_id in self._overlap:
            return

        # Overlap list keeps longest-waiting speakers up to max_overlap; extra talkers ignored.
        if len(self._overlap) < self.max_overlap:
            self._overlap.append(participant_id)

    def _promote_next_holder(self, now_ms: int) -> None:
        if self._holder is not None or not self._overlap:
            return
        next_holder = self._overlap.pop(0)
        self._holder = next_holder
        self._holder_since_ms = now_ms
        self._holder_silence_since_ms = None

    def _emit_if_changed(self) -> Optional[Dict[str, Any]]:
        current = (self._holder, tuple(self._overlap))
        if current != self._last_emitted:
            self._last_emitted = current
            return self.state()
        return None
