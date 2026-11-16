# Role 3 Deliverables: Speech Translation Pipeline Evaluation & Report Notes

**Project:** Generative AI Based Multilingual Translation System for Real-Time Video Conferencing  
**Team Role:** Role 3 (Backend: Speech Translation Pipeline)  
**Repository:** [avanikashetty3006-droid/multilingual-meet](https://github.com/avanikashetty3006-droid/multilingual-meet)

---

## 1. Model Choices & Technical Justification

### A. Automatic Speech Recognition (ASR): `faster-whisper`
- **Model Size:** `base` (74M parameters) quantized to `int8` on CPU, `float16` on CUDA GPU.
- **Why Chosen:** 
  - Vanilla OpenAI Whisper is too heavy and slow for real-time video conferencing chunks (often 4–8 seconds of inference on CPU).
  - `faster-whisper` is built on CTranslate2, delivering up to **4× faster inference** and **70% less memory usage**.
  - Supports English, Hindi, and Kannada out of the box with built-in language identification.
- **Optimizations Applied:**
  - `beam_size = 1` for ultra-low latency.
  - `vad_filter = False` because Role 4 (Speaker Service) already performs voice activity detection and only forwards speech chunks.

### B. Machine Translation (MT): AI4Bharat `IndicTrans2` (Distilled 200M)
- **Model Weights:** `ai4bharat/indictrans2-en-indic-dist-200M` and `ai4bharat/indictrans2-indic-en-dist-200M`.
- **Why Chosen:**
  - Developed by IIT Madras / AI4Bharat specifically for Indian linguistic nuances, outperforming general multilingual models (like mBART or NLLB) on Indian benchmarks.
  - The distilled 200M parameter model fits in consumer laptop RAM and runs efficiently on Google Colab T4 GPU.
- **Architecture Pattern:**
  - **English Pivoting:** Direct translation models are maintained for `en -> indic` and `indic -> en`. Any Indic-to-Indic translation (e.g., Hindi to Kannada) pivots through English (`hi -> en -> kn`). This eliminates the need for 400+ pairwise translation models.

### C. Text-to-Speech (TTS): `gTTS` / `Indic-TTS`
- **Why Chosen:**
  - Produces natural, human-like pronunciation for Indian accents (Hindi, Kannada, Indian English).
  - Lightweight network API requiring 0 MB of local GPU memory on constrained devices.
  - Implements fail-soft resilience: if TTS times out or fails, the pipeline still returns the translated text subtitle (`audio_url: null`), ensuring call participants always receive live captions.

### D. Architectural Scaling: $O(N)$ Fan-Out
- In a video call with 4 participants speaking 3 different languages, translation is performed **once per unique target language in the room**, rather than once per participant pair.
- This cuts compute load from $O(N^2)$ to $O(N)$.

---

## 2. Latency & Performance Evaluation Table

**TO FILL from real runs. Do not copy numbers from anywhere else.** Run on the demo laptop:
`python scripts/benchmark.py tests/data/hello_en.wav --runs 5 --targets hi --audio` (once with `WHISPER_MODEL=base`, once with `small`).
Report your own device, model versions and the date you measured.

| Pipeline stage | Device: _fill in_ (CPU) | Device: _fill in_ (GPU, optional) | Target |
| :--- | :--- | :--- | :--- |
| ASR (faster-whisper, model: __) | __ ms | __ ms | < 1200 ms |
| MT (engine: __) | __ ms | __ ms | < 600 ms |
| TTS (engine: __) | __ ms | __ ms | < 1500 ms |
| **Total (4 s chunk, 1 language, audio)** | **__ ms** | **__ ms** | **< 3000 ms (contract A7)** |

---

## 3. Translation Quality & ASR Accuracy Metrics

**TO FILL, only if you actually run an evaluation.** Method to state in the report: how many test sentences, who recorded
them, the reference translations (who wrote them), the tools (`jiwer` for WER, `sacrebleu` for BLEU). Keep the input files
and the outputs in the repo (for example `speech-service/eval/`) so the numbers can be reproduced.

| Language | Test sentences | WER (ASR) |
| :--- | :--- | :--- |
| English (en) | __ | __ % |
| Hindi (hi) | __ | __ % |
| Kannada (kn) | __ | __ % |

| Direction | Engine | BLEU | Notes |
| :--- | :--- | :--- | :--- |
| en to hi | __ | __ | |
| en to kn | __ | __ | |
| hi to en | __ | __ | |
| kn to en | __ | __ | |
| hi to kn (via English) | __ | __ | |

---

## 4. Contract A6 Acceptance Test Checklist

Tick each only after running it (`pytest -q`, `pytest -m slow -q -s`):

- [ ] Schema: `POST /v1/process-chunk` returns the exact JSON of `shared/CONTRACT.md` (`tests/test_real_mode.py`).
- [ ] Silent and noisy audio return HTTP 200 with `source_text: ""` and empty `translations`.
- [ ] `want_audio=false` gives `tts: 0` and `audio_url: null`.
- [ ] Requests beyond `MAX_QUEUE_DEPTH` get HTTP 429.
- [ ] `GET /v1/health` reports queue depth, rolling average latency, `device`, `models_loaded`.
