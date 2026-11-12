from typing import Dict, List, Optional
from network_monitor import ListenerNetworkState

class Participant:
    def __init__(self, participant_id: str, name: str, lang: str):
        self.participant_id = participant_id
        self.name = name
        self.lang = lang
        self.net_state = ListenerNetworkState(participant_id)
        self.room_socket = None

class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: Dict[str, Participant] = {}
        self.token_holder: Optional[str] = None
        self.overlap: List[str] = []

    def add_participant(self, p: Participant):
        self.participants[p.participant_id] = p

    def remove_participant(self, pid: str):
        self.participants.pop(pid, None)

    def get_participants_list(self) -> List[dict]:
        return [
            {"participant_id": p.participant_id, "name": p.name, "lang": p.lang}
            for p in self.participants.values()
        ]

    def get_unique_target_languages(self, speaker_id: str) -> List[str]:
        speaker = self.participants.get(speaker_id)
        speaker_lang = speaker.lang if speaker else None
        langs = set()
        for p in self.participants.values():
            if p.participant_id != speaker_id and p.lang != speaker_lang:
                langs.add(p.lang)
        return list(langs)

    def any_listener_wants_audio(self, speaker_id: str) -> bool:
        speaker = self.participants.get(speaker_id)
        speaker_lang = speaker.lang if speaker else None
        for p in self.participants.values():
            if p.participant_id != speaker_id and p.lang != speaker_lang:
                if p.net_state.current_mode == "audio":
                    return True
        return False
