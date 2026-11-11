# speech-service (Role 3)

FastAPI service on port 8001: audio chunk in, transcript + translations (+ optional speech) out.
Status: **Step 1 (MOCK) done.** Real ASR/MT/TTS come in Steps 2 to 5.

## Run
```bash
cd speech-service
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
MOCK=1 uvicorn main:app --port 8001      # Windows PowerShell: $env:MOCK=1; uvicorn main:app --port 8001
```

## Try it
```bash
curl http://localhost:8001/v1/health

curl -X POST http://localhost:8001/v1/process-chunk \
  -F audio=@audio/sample.wav \
  -F room_id=r1 -F participant_id=p1 -F chunk_id=c1 \
  -F src_lang=en -F 'tgt_langs=["hi","kn"]' -F want_audio=true
```
(`audio/sample.wav` is created automatically the first time the server starts.)

## Test
```bash
MOCK=1 pytest -q
```

## Env vars
| Var | Default | Meaning |
|---|---|---|
| MOCK | 1 | 1 = canned replies after about 800 ms |
| SPEECH_PUBLIC_URL | http://localhost:8001 | base of audio_url |
| MAX_QUEUE_DEPTH | 8 | more requests than this get HTTP 429 |
