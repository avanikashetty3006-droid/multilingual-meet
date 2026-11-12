# Speaker Detection & Token Service (Role 4)

VAD & Active Speaker Arbitration Service for `multilingual-meet`.
Implements Section A5 of `shared/CONTRACT.md`.

## Port & Interfaces
- **Port:** `8002`
- `WS /ws/vad/{room_id}/{participant_id}`: Binary mic stream input, VAD speech events output.
- `WS /ws/token/{room_id}`: Active speaker token updates (`holder`, `overlap`).
- `GET /v1/health`: Service health check.

## Running in Mock Mode (`MOCK=1`)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run service with MOCK=1
export MOCK=1
uvicorn main:app --port 8002
# On Windows PowerShell:
# $env:MOCK="1"; uvicorn main:app --port 8002
```

## Running Verification Tests

```bash
pytest tests/test_token_manager.py -v
```
