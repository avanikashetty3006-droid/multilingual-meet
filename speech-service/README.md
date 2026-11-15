# Speech Translation Service (Role 3)

Backend Speech Translation Pipeline (ASR -> MT -> TTS) for `multilingual-meet`.
Implements Section A6 of `shared/CONTRACT.md`.

## Port & Interfaces
- **Port:** `8001`
- `POST /v1/process-chunk`: Multipart/form-data audio processing (WAV chunk -> transcript + translations + audio).
- `GET /v1/health`: Rolling average latency, queue depth, health status.
- `GET /audio/{file}.wav`: Serves generated speech audio files.

## Running in Mock Mode (`MOCK=1`)

Used for fast local development and testing with other services (Roles 1, 2, 4) without downloading AI models:

```bash
# 1. Install base requirements
pip install -r requirements.txt

# 2. Run service with MOCK=1
# Linux / macOS:
export MOCK=1
uvicorn main:app --port 8001

# Windows PowerShell:
$env:MOCK="1"; uvicorn main:app --port 8001
```

## Running with Real Models (`MOCK=0`)

Runs the full AI pipeline:
1. **ASR**: `faster-whisper` (`base` model, int8 on CPU, float16 on CUDA).
2. **MT**: `ai4bharat/indictrans2-dist-200M` (English <-> Indic with English pivoting).
3. **TTS**: `gTTS` for speech synthesis (English, Hindi, Kannada).

```bash
# 1. Install AI dependencies
pip install gTTS faster-whisper transformers torch sentencepiece sacremoses sacrebleu jiwer

# 2. Run service with MOCK=0
# Linux / macOS:
export MOCK=0
uvicorn main:app --port 8001

# Windows PowerShell:
$env:MOCK="0"; uvicorn main:app --port 8001
```

### Model Access & Download Notes:
- **IndicTrans2**:
  - Accept terms on Hugging Face:
    - [indictrans2-en-indic-dist-200M](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M)
    - [indictrans2-indic-en-dist-200M](https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M)
  - Models take ~1.2 GB disk space.
- **Faster-Whisper (`base`)**:
  - Downloads automatically on first run (~145 MB).

## Running Contract Verification Tests

```bash
pytest tests/test_contract.py -v
```

## cURL Verification Test

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
