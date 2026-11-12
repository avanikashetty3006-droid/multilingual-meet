"""
Mock Speaker Service - Role 4 Step 1
Simulates VAD events and token passing rotation every 5 seconds.
"""
import asyncio
import time
from typing import List, Optional

async def mock_token_rotator(room_id: str, participants: List[str]):
    """
    Rotates the active speaker token among participants every 5 seconds (Contract A8).
    """
    idx = 0
    while True:
        ts_ms = int(time.time() * 1000)
        if not participants:
            holder = None
            overlap = []
        else:
            holder = participants[idx % len(participants)]
            overlap = [p for p in participants if p != holder][:2]
            idx += 1

        yield {
            "type": "token_update",
            "room_id": room_id,
            "holder": holder,
            "overlap": overlap,
            "ts_ms": ts_ms
        }
        await asyncio.sleep(5.0)
