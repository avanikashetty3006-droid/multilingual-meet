# Speech Translation Service (Role 3)

Backend Speech Translation Pipeline (ASR -> MT -> TTS) for `multilingual-meet`.
Implements Section A6 of `shared/CONTRACT.md`.

## Port & Interfaces
- **Port:** `8001`
- `POST /v1/process-chunk`: Multipart/form-data audio processing.
- `GET /v1/health`: Rolling average latency, queue depth, health status.
- `GET /audio/{file}.wav`: Serves generated audio.

## Running in Mock Mode (`MOCK=1`)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run service with MOCK=1
export MOCK=1
uvicorn main:app --port 8001
# On Windows PowerShell:
# $env:MOCK="1"; uvicorn main:app --port 8001
```

## Running Verification Tests

```bash
pytest tests/test_contract.py -v
```

## Manual cURL Test

```bash
curl -X POST http://localhost:8001/v1/process-chunk \
  -F "audio=@audio/sample.wav" \
  -F "room_id=room1" \
  -F "participant_id=p-1" \
  -F "chunk_id=p-1-0" \
  -F "src_lang=en" \
  -F "tgt_langs=[\"hi\",\"kn\"]" \
  -F "want_audio=true"
```
