"""In-memory room and participant state registry."""

import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from starlette.websockets import WebSocket
from network_monitor import ListenerNetworkState
from chunker import ParticipantAudioChunker
from config import INITIAL_MODE, MAX_OVERLAP


def compute_lane_for_participant(
    pid: str,
    holder: Optional[str],
    overlap: List[str],
    last_lane: Optional[str] = None,
    max_overlap: int = MAX_OVERLAP,
) -> Optional[str]:
    """Pure function determining participant's lane from token state.

    - holder => "main"
    - in overlap (index < max_overlap) => "overlap"
    - beyond max_overlap => None (ignored)
    - absent from update => keep last_lane
    """
    if pid == holder:
        return "main"
    if pid in overlap:
        idx = overlap.index(pid)
        if idx < max_overlap:
            return "overlap"
        return None
    return last_lane


@dataclass
class Participant:
    participant_id: str
    name: str
    lang: str
    room_id: str
    ws: Optional[WebSocket] = None
    mode: str = INITIAL_MODE
    lane: Optional[str] = None
    net_state: ListenerNetworkState = field(init=False)
    chunker: ParticipantAudioChunker = field(init=False)
    latest_net_stats: Optional[Dict[str, Any]] = None
    latest_net_stats_ts: float = 0.0

    def __post_init__(self):
        self.net_state = ListenerNetworkState(
            participant_id=self.participant_id,
            current_mode=self.mode
        )
        self.chunker = ParticipantAudioChunker(participant_id=self.participant_id)


class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: Dict[str, Participant] = {}
        self.token_holder: Optional[str] = None
        self.overlap: List[str] = []
        self.token_task: Optional[asyncio.Task] = None
        self.in_flight_speech_calls: int = 0
        self.lock = asyncio.Lock()

    def update_token_state(self, holder: Optional[str], overlap: List[str], max_overlap: int = MAX_OVERLAP):
        self.token_holder = holder
        self.overlap = overlap
        for pid, p in self.participants.items():
            p.lane = compute_lane_for_participant(
                pid=pid,
                holder=holder,
                overlap=overlap,
                last_lane=p.lane,
                max_overlap=max_overlap,
            )

    def get_participant_list(self) -> List[Dict[str, str]]:
        return [
            {"participant_id": p.participant_id, "name": p.name, "lang": p.lang}
            for p in self.participants.values()
        ]

    def get_unique_target_languages(self, speaker_id: str) -> List[str]:
        """Returns unique languages spoken by participants other than the speaker."""
        langs = set()
        for pid, p in self.participants.items():
            if pid != speaker_id and p.lang:
                langs.add(p.lang)
        return list(langs)

    def is_any_listener_in_audio_mode(self, speaker_id: str) -> bool:
        """Returns True if at least one listener in the room has mode == 'audio'."""
        for pid, p in self.participants.items():
            if pid != speaker_id and p.mode == "audio":
                return True
        return False

    async def broadcast_json(self, message: Dict[str, Any], exclude_id: Optional[str] = None):
        """Sends a JSON message to all connected participants in the room."""
        for pid, p in list(self.participants.items()):
            if exclude_id and pid == exclude_id:
                continue
            if p.ws:
                try:
                    await p.ws.send_json(message)
                except Exception:
                    pass


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self._lock = asyncio.Lock()

    async def get_or_create_room(self, room_id: str) -> Room:
        async with self._lock:
            if room_id not in self.rooms:
                self.rooms[room_id] = Room(room_id)
            return self.rooms[room_id]

    async def get_room(self, room_id: str) -> Optional[Room]:
        async with self._lock:
            return self.rooms.get(room_id)

    async def remove_participant(self, room_id: str, participant_id: str):
        async with self._lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            if participant_id in room.participants:
                del room.participants[participant_id]
            if room.token_holder == participant_id:
                room.token_holder = None
            if participant_id in room.overlap:
                room.overlap.remove(participant_id)
            if not room.participants:
                if room.token_task:
                    room.token_task.cancel()
                del self.rooms[room_id]
