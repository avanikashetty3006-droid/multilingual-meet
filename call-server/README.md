# Role 2: Call Server & Network Monitoring Hub

The Call Server is the central communication hub connecting the Frontend (Role 1), the Speech Translation Service (Role 3), and the Speaker Detection Service (Role 4).

## Responsibilities
1. **LiveKit Token Generation**: Issues join credentials for WebRTC audio/video with language validation (`en, hi, kn, ta, te, ml, mr`).
2. **Audio Chunker & VAD Forwarding**: Collects 512-sample (1024-byte, 16kHz mono) PCM frames, maintains a 300ms pre-roll, buffers frames during speech, and cuts chunks at speech boundaries or 4.0s continuous speech.
3. **Adaptive Network Decision Engine**: Implements Section A7 with 3-window hysteresis. Dynamically switches listeners between `audio` and `subtitle` mode based on fresh network stats (< 6s stale threshold) and speech service health.
4. **Translation Fan-out & Queue Protection**:
   - Dispatches speech chunks to Speech Service once per unique target language ($O(N)$ not $O(N^2)$).
   - Only token holders (`lane: "main"`) receive audio synthesis.
   - Overlap lanes are capped at `max_overlap` (default 2) and dropped first if queue depth exceeds `max_queue_depth` (default 8).
5. **Active Speaker Coordination**: Subscribes to Token Manager (`WS /ws/token/{room}`) and broadcasts active token holder and overlapping talkers.
6. **Detailed Metrics**: Outputs latency, chunk duration, and real listener network state breakdown to `metrics.csv`.

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run All Unit Tests
```bash
python -m pytest -q
```
Runs 21 unit tests covering:
- Network decision rules, hysteresis, stale stats, and unknown speech latency (`tests/test_decision.py`).
- Audio chunking, pre-roll, 8.6s continuous speech slicing, short chunk & silence drops (`tests/test_chunker.py`).
- Lane assignment, max overlap capping, queue overload protection, and audio gating (`tests/test_fanout_rules.py`).

---

## Testing Modes

### Testing with `MOCK=1` (Standalone Mock Gateway)
No external AI models or services are required. In this mode, two simulated participants (`Asha (mock)` and `Ravi (mock)`) automatically join the room:

1. **Start the server**:
   ```bash
   $env:MOCK="1"   # In PowerShell (or MOCK=1 on Linux/macOS)
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Connect with websocat** (or browser frontend):
   ```bash
   websocat "ws://localhost:8000/ws/room/room1?participant_id=p-1"
   ```
   Send `hello`:
   ```json
   {"type":"hello","participant_id":"p-1","name":"Asha","lang":"hi"}
   ```
   Send `net_stats` every 2 seconds:
   ```json
   {"type":"net_stats","rtt_ms":60,"packet_loss_pct":0.1,"bitrate_kbps":950,"jitter_ms":5}
   ```
   **Observation**: You will receive initial `mode` ("subtitle"), `participants` list including the mock participants, rotating `active_speaker` events every 3s, and periodic `translation` events.

---

### Testing with `MOCK=0` (Integration with External / Fake Services)
When integrating with real Role 3 and Role 4 services:

```bash
$env:MOCK="0"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- Audio frames received on `WS /ws/audio/{room}/{pid}` are forwarded to `SPEAKER_SERVICE_URL /ws/vad/{room}/{pid}` via an asynchronous queue with backoff reconnection.
- Subscribes once to `SPEAKER_SERVICE_URL /ws/token/{room}` per active room and updates participant lanes dynamically.
- Delivers translated speech and captures end-to-end timings in `metrics.csv`.
