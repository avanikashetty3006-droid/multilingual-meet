# Role 2: Call Server & Network Monitoring Hub

The Call Server is the central communication hub of the Generative AI Multilingual Video Conferencing System.

## Responsibilities
1. **LiveKit Token Generation**: Issues join credentials for WebRTC audio/video.
2. **Audio Chunker & VAD Forwarding**: Collects 512-sample (1024-byte, 16kHz mono) PCM frames, buffers them, and cuts chunks at speech boundaries or 4.0s max duration.
3. **Adaptive Network Decision Engine**: Implements section A7 of `CONTRACT.md` with 3-window hysteresis. Dynamically switches each listener between `audio` mode and `subtitle` mode.
4. **Translation Fan-out**: Queries Speech Service (Role 3) once per unique target language ($O(N)$ not $O(N^2)$), and dispatches translated captions and speech to listeners.
5. **Active Speaker Coordination**: Listens to Token Manager (Role 4) and broadcasts active token holder and overlapping talkers.

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Call Server
```bash
# In mock mode (no GPU/external models required)
MOCK=1 uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Run Tests
```bash
pytest tests/test_decision.py -v
```

## Endpoints

- `POST /v1/rooms/{room_id}/join`: Issues LiveKit token
- `WS /ws/room/{room_id}?participant_id=...`: JSON room control messages (`hello`, `net_stats`, `participants`, `active_speaker`, `mode`, `translation`)
- `WS /ws/audio/{room_id}/{participant_id}`: Binary PCM16 audio ingest
- `GET /v1/health`: Server status and connected room counts
