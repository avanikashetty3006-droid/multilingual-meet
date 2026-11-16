# speech-service (Role 3)

FastAPI service on port 8001: one audio chunk in, transcript + translations (+ optional speech) out (contract A6).

**Status:** mock (`MOCK=1`) done earlier. Real pipeline (`MOCK=0`) is in this version: faster-whisper (ASR) ->
NLLB-200 600M via CTranslate2 (MT) -> facebook/mms-tts-* (TTS). The model code has NOT yet been run on real models by the author
of this pack (see "Status of testing" at the bottom): do the first-run steps below and record your numbers.

## 1. Install (Windows PowerShell, Python 3.10 to 3.12; 3.13 may lack wheels for some packages)
```powershell
cd speech-service
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt                                   # light set (mock + fast tests)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-real.txt                              # faster-whisper, ctranslate2, transformers, sentencepiece
.\scripts\convert_nllb.ps1                                        # ONE time, a few minutes, creates models\nllb-600m-ct2
```
Whisper (`base` about 150 MB) and the MMS voices (about 140 MB each) download automatically on first start into the
default Hugging Face cache (outside the repo). `models/` is in `.gitignore`.

## 2. Run
```powershell
$env:MOCK = "0"
$env:WHISPER_MODEL = "base"          # or "small" (better for Hindi/Kannada, slower), see section 5
uvicorn main:app --port 8001
```
The first start loads models for a while: `GET /v1/health` shows `"status":"loading"`, then `"ok"` with `"models_loaded":true`.
If a model is missing, the service still starts, health shows `"status":"error"` plus the reason, and chunks get HTTP 503.
Mock mode is unchanged: `$env:MOCK="1"; uvicorn main:app --port 8001`.

## 3. Try it
```powershell
curl.exe http://localhost:8001/v1/health
python scripts/try_chunk.py tests/data/hello_en.wav --src en --targets hi kn --audio
python scripts/try_chunk.py tests/data/hello_en.wav --src auto --targets en        # language detection
```
(`tests/data/hello_en.wav`: record yourself saying "Hello everyone, can you hear me?" for 3 s; save as 16 kHz mono 16-bit WAV, e.g. with Audacity: Project Rate 16000, Mono, Export WAV 16-bit PCM.)
Plain curl equivalent (bash): `curl -X POST localhost:8001/v1/process-chunk -F audio=@tests/data/hello_en.wav -F room_id=r1 -F participant_id=p1 -F chunk_id=c1 -F src_lang=en -F 'tgt_langs=["hi","kn"]' -F want_audio=true`

## 4. Tests
```powershell
pytest -q                          # fast: pipeline tests with fake engines (16) + mock/contract tests + real-mode endpoint tests
pytest -m slow -q -s               # real models (needs section 1 done and tests/data/hello_en.wav)
```

## 5. Measure and pick the default model (do this once, put the numbers here)
```powershell
python scripts/benchmark.py tests/data/hello_en.wav --runs 5 --targets hi --audio
$env:WHISPER_MODEL="small"; python scripts/benchmark.py tests/data/hello_en.wav --runs 5 --targets hi --audio
```
The call server only switches listeners to audio when the **average total is under 3000 ms** (and its request timeout is 6 s).
Choose the model whose `total` for one language with audio is under about 2500 ms on the demo laptop.

| model | device | asr ms | mt ms | tts ms | total ms (4 s chunk, 1 language, audio) |
|---|---|---|---|---|---|
| base | _fill in_ | | | | |
| small | _fill in_ | | | | |

## 6. Env vars
| Var | Default | Meaning |
|---|---|---|
| MOCK | 1 | 1 = canned replies, 0 = real models |
| SPEECH_PUBLIC_URL | http://localhost:8001 | base of `audio_url` (in production: your site URL; nginx proxies `/audio/`) |
| MAX_QUEUE_DEPTH | 8 | more requests than this get HTTP 429 |
| WHISPER_MODEL | base | `base`, `small`, ... |
| NLLB_CT2_DIR | models/nllb-600m-ct2 | converted NLLB folder |
| MT_BEAM | 2 | translation beam size (1 = fastest) |
| CPU_THREADS | 0 | 0 = library default |
| WORKERS | 1 | model threads (keep 1 on CPU) |
| AUDIO_DIR | audio/ | where generated WAVs are written |
| AUDIO_MAX_AGE_S | 600 | generated WAVs older than this are deleted every minute (`sample.wav`, `mock_*.wav` are kept) |

## 7. Behaviour (matches the Role 3 prompt)
- ASR: `faster-whisper` int8, `beam_size=1`, `vad_filter=False`, `prev_text` as `initial_prompt`; known `src_lang` skips detection, `"auto"` detects and returns `detected_lang`.
- Hallucination guard: segments with `no_speech_prob > 0.6` or `avg_logprob < -1.0` are dropped; if nothing is left, HTTP 200 with `source_text: ""`, `translations: {}`. Very quiet audio (below RMS 0.009) never reaches Whisper.
- MT once per unique target language; target equal to the detected language returns the source text; a failed language is left out.
- TTS only when `want_audio=true`; a TTS failure gives the text with `audio_url: null`. Voices are loaded on first use (hi and kn are preloaded).
- Models load once at startup in a background thread; chunks run in a worker thread so `/v1/health` stays responsive.

## 8. Docker
`Dockerfile` is included (CPU). Convert NLLB once into a volume, then run (merge into the repo's `docker-compose.yml`):
```yaml
  speech-service:
    build: ./speech-service
    environment:
      PORT: "8001"
      MOCK: "0"
      SPEECH_PUBLIC_URL: ${PUBLIC_URL}
      WHISPER_MODEL: base
    volumes:
      - models:/models         # add "models:" under the top-level volumes:
```
One-time conversion in the container: `docker compose run --rm speech-service ct2-transformers-converter --model facebook/nllb-200-distilled-600M --output_dir /models/nllb-600m-ct2 --quantization int8`

## 9. Known limits
- Whisper `base` is weak for Kannada/Tamil/Telugu/Malayalam/Marathi; try `small` and compare with real recordings. NLLB-600M quality is "good enough for subtitles", not perfect.
- MMS voices are robotic but intelligible; no emotion or speaker voice.
- One worker thread: chunks are processed one after another, so latency grows with simultaneous speakers (the call server's overlap cap keeps this bounded).
- Sentences are translated per chunk (about 4 s), so context across chunks is limited to `prev_text` for ASR only.
