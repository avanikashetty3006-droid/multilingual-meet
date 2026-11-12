# Speaker Service (Role 4: VAD + Token Passing)

FastAPI WebSocket service on **port 8002** for **VAAK** (Multilingual Video Conferencing).
Listens to each participant's 16 kHz PCM16 mic stream, detects `speech_start` / `speech_end` via Voice Activity Detection (VAD), and runs a deterministic per-room speaking token state machine (`holder` + `overlap`).

---

## Interfaces

### Contract Endpoints (`shared/CONTRACT.md` Section A5)
- **`WS /ws/vad/{room_id}/{participant_id}`**
  - Receives binary frames: **PCM16 little-endian, 16 kHz, mono, 512 samples = 1024 bytes = 32 ms** each.
  - Wrong-sized frames are ignored and logged (up to 3 times per stream).
  - Emits JSON **only on state transitions**:
    ```json
    {"type":"vad","participant_id":"p-1","state":"speech_start","ts_ms":1730000000000}
    ```
  - Stalled/muted streams that stop sending frames while speaking auto-emit `speech_end` after `VAD_STALL_TIMEOUT_MS` (default `1000 ms`).
- **`WS /ws/token/{room_id}`**
  - Broadcasts room speaking token state immediately upon connection and thereafter only when `holder` or `overlap` changes:
    ```json
    {"type":"token_update","room_id":"room1","holder":"p-1","overlap":["p-2"],"ts_ms":1730000000000}
    ```

### Additive Endpoints (beyond `shared/CONTRACT.md`)
> Note: These convenience endpoints are additive to the core contract and do not alter any contract WebSocket schemas.
- **`GET /v1/health`** -> `{"status":"ok","mock":true,"rooms":0,"streams":0}`
- **`GET /v1/rooms/{room_id}/state`** -> `{"room_id":"room1","holder":"p-1","overlap":["p-2"],"streams":["p-1","p-2"],"subscribers":1}`

---

## Setup & Installation

Uses **ONNX Runtime + `silero_vad_16k_op15.onnx`** (bundled in `models/`), avoiding a multi-hundred-MB PyTorch install on Windows laptops while running **~0.18 ms per 32 ms frame** on CPU.

### Windows PowerShell
```powershell
cd speaker-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux / macOS
```bash
cd speaker-service
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running the Service

### 1. Mock Mode (`MOCK=1`, default — RMS Energy Gate + Real TokenManager)
```powershell
# Windows PowerShell
$env:MOCK="1"; $env:MOCK_ROTATE="0"; python -m uvicorn main:app --host 127.0.0.1 --port 8002
```
```bash
# Linux / macOS
MOCK=1 MOCK_ROTATE=0 uvicorn main:app --host 127.0.0.1 --port 8002
```

For standalone demos without speaking into a mic (`MOCK_ROTATE=1` rotates `holder` every 5 s across connected `/ws/vad` streams):
```powershell
$env:MOCK="1"; $env:MOCK_ROTATE="1"; python -m uvicorn main:app --host 127.0.0.1 --port 8002
```

### 2. Real Silero VAD Mode (`MOCK=0` — Silero ONNX + TokenManager)
```powershell
# Windows PowerShell
$env:MOCK="0"; python -m uvicorn main:app --host 127.0.0.1 --port 8002
```
```bash
# Linux / macOS
MOCK=0 uvicorn main:app --host 127.0.0.1 --port 8002
```

> **Windows tip:** On Windows, connecting to `localhost` can trigger a ~1–2 s IPv6 (`::1`) fallback delay if a server binds only IPv4 `127.0.0.1`. Use `127.0.0.1` in `SPEAKER_SERVICE_URL=http://127.0.0.1:8002` when testing locally with `call-server` and `load-test/bots.py`.

---

## Configuration & Latency Tuning

Token policy thresholds are loaded automatically from `../shared/config.yaml` (`token.min_speech_ms=200`, `token.release_silence_ms=700`, `token.min_hold_ms=1000`, `limits.max_overlap=2`).

| Variable | Default | Meaning |
|---|---|---|
| `MOCK` | `1` | `1` = RMS energy gate, `0` = Silero ONNX VAD |
| `MOCK_ROTATE` | `0` | `1` (with `MOCK=1`) = rotate holder every 5 s across streams |
| `VAD_THRESHOLD` | `0.5` | Silero speech probability threshold to trigger onset |
| `VAD_NEG_THRESHOLD` | `0.35` | Lower Schmitt hysteresis threshold (`threshold - 0.15`) to stay active |
| `VAD_START_FRAMES` | `2` | Consecutive speech frames (`2 * 32 ms = 64 ms`) before emitting `speech_start` |
| `VAD_END_SILENCE_MS` | `500` | Trailing silence before emitting `speech_end` (prevents mid-word chunk splits while keeping pause release snappy) |
| `VAD_STALL_TIMEOUT_MS` | `1000` | Emit `speech_end` if a speaking stream stops sending frames |
| `TICK_INTERVAL_MS` | `50` | Background timer cadence for token hysteresis and stall checks |
| `MAX_FRAME_QUEUE` | `16` | Bounded per-stream queue (drops oldest frames on CPU overload) |
| `ENERGY_THRESHOLD` | `400.0` | RMS threshold used when `MOCK=1` |

**Why `VAD_END_SILENCE_MS=500`?** The Call Server (`call-server/chunker.py`) cuts audio chunks when `speech_end` arrives. A `500 ms` silence window ignores short intra-sentence breaths/pauses (`150–350 ms`) so words are not split prematurely, while still releasing sentences cleanly without adding excessive tail delay. Meanwhile, `VAD_START_FRAMES=2` (`64 ms`) gives fast onset and pairs with `call-server`'s `480 ms` pre-roll buffer so initial syllables are never clipped.

---

## Verification & Test Commands

### 1. Run Unit & WebSocket Tests (`23` tests)
```powershell
python -m pytest tests -v
```

### 2. HTTP Health & Room Debug Checks
```powershell
curl http://127.0.0.1:8002/v1/health
curl http://127.0.0.1:8002/v1/rooms/demo-room/state
```

### 3. WebSocket Test (`websocat` + Python Two-Speaker Demo)
```bash
# Subscribe to room token updates
websocat "ws://127.0.0.1:8002/ws/token/demo-room"
```
In another terminal, stream the 16 kHz speech fixture across two overlapping participants:
```powershell
python scripts/demo_two_speakers.py --wav tests/fixtures/speech_sample.wav
```

### 4. Offline WAV Inspector
```powershell
python scripts/offline_vad.py tests/fixtures/speech_sample.wav
```

### 5. Load-Test Integration with Call Server (`MOCK=0`)
Start `speech-service` (`MOCK=1`, port `8001`), `speaker-service` (`MOCK=0`, port `8002`), and `call-server` (`MOCK=0`, port `8000`), then run:
```powershell
cd ..\load-test
python bots.py --num-bots 4  --server ws://127.0.0.1:8000 --speak-pattern round-robin --wav ..\speaker-service\tests\fixtures\speech_sample.wav
python bots.py --num-bots 6  --server ws://127.0.0.1:8000 --speak-pattern overlap --overlap-count 3 --wav ..\speaker-service\tests\fixtures\speech_sample.wav
python bots.py --num-bots 20 --server ws://127.0.0.1:8000 --speak-pattern overlap --overlap-count 6 --wav ..\speaker-service\tests\fixtures\speech_sample.wav
```

---

## Performance & Evaluation Results

Measured on Windows 11 laptop CPU (`onnxruntime`, `silero_vad_16k_op15.onnx`, single-threaded ONNX session with pre-allocated per-stream buffers) via `python scripts/benchmark_vad.py`:

### Real-Time Scaling (32 ms frame budget)

| Simultaneous Streams | Avg ms / frame | Avg ms / 32 ms tick | P95 ms / tick | 1-Core CPU Usage |
|---:|---:|---:|---:|---:|
| 1 | 0.190 ms | 0.190 ms | 0.410 ms | 0.6% |
| 4 | 0.189 ms | 0.755 ms | 1.456 ms | 2.4% |
| 10 | 0.173 ms | 1.731 ms | 2.631 ms | 5.4% |
| 20 | 0.176 ms | 3.521 ms | 4.965 ms | 11.0% |
| 30 | 0.177 ms | 5.300 ms | 6.720 ms | 16.6% |

### VAD Accuracy & Token Switching Evaluation

| Metric | Measured Result | Notes |
|---|---|---|
| Silence false triggers / min | `0` | 60 s pure silence (1875 frames) |
| White noise (`-35 dBFS`) triggers / min | `0` | 60 s Gaussian noise (1875 frames) |
| Speech onset detection delay | `64 ms` | Matches `VAD_START_FRAMES=2` (2 × 32 ms) |
| Speech end detection delay | `544 ms` | Includes `VAD_END_SILENCE_MS=500 ms` hold |
| Overlap token switching (`bots.py` 6 & 20 bots) | `100%` valid | `holder` never in `overlap`, `len(overlap) <= 2`, `0` late frames |
