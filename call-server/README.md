# Call Server Hub & Network Monitor (Role 2)

Central Hub connecting Frontend, Speaker Service, and Speech Service for `multilingual-meet`.
Implements Sections A4, A6, and A7 of `shared/CONTRACT.md`.

## Port & Interfaces
- **Port:** `8000`
- `POST /v1/rooms/{room_id}/join`: Issues LiveKit room connection tokens.
- `WS /ws/room/{room_id}?participant_id=...`: JSON room events, net stats, mode updates.
- `WS /ws/audio/{room_id}/{participant_id}`: Binary mic PCM frames input.

## Running in Mock Mode (`MOCK=1`)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Call Server
export MOCK=1
uvicorn main:app --port 8000
# On Windows PowerShell:
# $env:MOCK="1"; uvicorn main:app --port 8000
```

## Running Verification Tests

```bash
pytest tests/test_decision.py -v
```
