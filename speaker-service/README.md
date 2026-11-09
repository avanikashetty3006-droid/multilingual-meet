# Role 4: Speaker Detection (VAD + Token Passing)

Voice Activity Detection (VAD) and speaking token coordinator service.

## Responsibilities
- **VAD Processing**: Receives 512-sample (1024-byte) raw PCM16 frames on `WS /ws/vad/{room}/{pid}` and detects `speech_start` (>= 200ms) and `speech_end` (>= 700ms silence).
- **Token Manager**: Manages active speaker token:
  - First speaker gets the token (`holder`).
  - Concurrent speakers enter the `overlap` lane.
  - On release, the longest-waiting overlapping speaker is promoted.
  - Enforces minimum 1s hold duration and ignores flickers < 200ms.
- **Token Broadcast**: Streams `token_update` events on `WS /ws/token/{room}`.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run speaker service (Port 8002)
MOCK=1 uvicorn main:app --host 0.0.0.0 --port 8002 --reload

# 3. Run tests
pytest tests/test_token_manager.py -v
```
