# Role 3: Speech Translation Pipeline (ASR -> MT -> TTS)

FastAPI service translating spoken audio chunks into target languages (English, Hindi, Kannada, etc.).

## Responsibilities
- **ASR**: Whisper / faster-whisper transcription and source language detection.
- **MT**: IndicTrans2 translation (pivoting through English when needed).
- **TTS**: gTTS / Indic-TTS synthesis to 16kHz mono WAV audio clips.
- **Mock Mode**: Implements mock translation and audio generation when `MOCK=1`.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run speech service (Port 8001)
MOCK=1 uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# 3. Run tests
pytest tests/test_contract.py -v
```

## Endpoints
- `POST /v1/process-chunk`: Process WAV audio chunk (multipart/form-data)
- `GET /audio/{file}.wav`: Serve synthesized audio
- `GET /v1/health`: Service health and metrics
