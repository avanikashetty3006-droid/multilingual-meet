import asyncio
import time
from typing import Dict, List, Set

class MockSpeakerService:
    def __init__(self):
        self.rooms: Dict[str, Set[str]] = {}
        self.active_holders: Dict[str, str] = {}

    def register_participant(self, room_id: str, participant_id: str):
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add(participant_id)

    def unregister_participant(self, room_id: str, participant_id: str):
        if room_id in self.rooms:
            self.rooms[room_id].discard(participant_id)

    async def run_token_rotator(self, room_id: str, callback):
        """Periodically emits token_update rotating between known participants every 5s."""
        step = 0
        while True:
            await asyncio.sleep(5.0)
            participants = list(self.rooms.get(room_id, []))
            if not participants:
                continue
            step += 1
            holder = participants[step % len(participants)]
            overlap = [p for p in participants if p != holder][:1]
            now_ms = int(time.time() * 1000)

            await callback({
                "type": "token_update",
                "room_id": room_id,
                "holder": holder,
                "overlap": overlap,
                "ts_ms": now_ms,
            })
