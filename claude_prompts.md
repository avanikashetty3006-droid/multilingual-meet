# Claude Prompts: GenAI Multilingual Video Conferencing (4 parallel roles)

## How to use this file

1. Create the GitHub repo first. Save PART A as `shared/CONTRACT.md` and commit it.
2. Each person opens their own Claude setup and pastes **PART A first, then their own role prompt (B1 / B2 / B3 / B4)**.
3. Every role builds a **MOCK of its service first** (a few hours of work). That way the other three can integrate on day 2 without waiting for the real AI models.
4. The contract is the only thing that connects the four roles. **Do not change it alone.** If a change is needed, ask Claude for a "CONTRACT CHANGE REQUEST", send it to the group chat, and update CONTRACT.md only after all four agree.

---

# PART A: SHARED CONTRACT (paste into every Claude setup)

## A1. Project

"Generative AI Based Multilingual Translation System for Real-Time Video Conferencing" (college mini project, AI & ML dept, 4 students). Participants speak different languages (English, Hindi, Kannada first; more Indian languages later). Each listener hears or reads the speech in their own language.

Core ideas of the project:
- **Automatic speaker detection:** Voice Activity Detection (VAD) drives a token-passing scheme. One active speaker (token holder) at a time. Overlapping talkers go to a subtitle lane.
- **Network-aware output:** good connection means translated audio (plus captions). Poor connection means subtitles only. The decision is automatic, per listener, from measured network and server conditions.
- **Low delay:** audio is processed in 3 to 5 second chunks, not waiting for pauses.
- **Scalable:** translate once per target language, not once per listener pair (O(N), not O(N²)).

## A2. Architecture (hub and spoke)

```
 Browser (Role 1)
   |-- video/audio call ------------------> LiveKit (WebRTC)
   |-- mic PCM frames (binary WS) --------> CALL SERVER (Role 2, port 8000) <--- HUB
   |<-- JSON events (WS) ----------------      |            |
                                               |            |
                        WS frames + events     |            | HTTP chunk (WAV)
                                               v            v
                                SPEAKER SERVICE        SPEECH SERVICE
                                (Role 4, port 8002)    (Role 3, port 8001)
                                VAD + token passing    ASR -> MT -> TTS
```

Repo layout (monorepo; each role edits ONLY its own folder):

```
multilingual-meet/
  frontend/          # Role 1  (React + Vite, port 5173)
  call-server/       # Role 2  (FastAPI, port 8000)
  speech-service/    # Role 3  (FastAPI, port 8001)
  speaker-service/   # Role 4  (FastAPI, port 8002)
  shared/
    CONTRACT.md      # this file
    config.yaml      # thresholds (owned by Role 2, read by all)
  .env.example
  docker-compose.yml (optional, later)
```

Branching: `main` is always runnable. Each role works on `role1-frontend`, `role2-callserver`, `role3-speech`, `role4-speaker` and opens a PR to merge. Never edit another role's folder.

## A3. Conventions

- Language codes: ISO 639-1 lowercase: `en`, `hi`, `kn` (later `ta`, `te`, `ml`, `mr`). `auto` means detect.
- Time: integer milliseconds since epoch (`ts_ms`).
- IDs: `room_id` and `participant_id` are short strings (e.g. `room1`, `p-3f9a`). `chunk_id` = `{participant_id}-{seq}` (seq starts at 0, per participant).
- Raw audio format everywhere: **PCM16 little-endian, 16 kHz, mono**.
- Mic frame size: **512 samples = 1024 bytes = 32 ms** per binary WebSocket message.
- Speech chunk sent for translation: a **WAV file (same PCM16/16k/mono)**, 3 to 5 seconds, or shorter if the speaker stops.
- All JSON messages have a `"type"` field.
- Python 3.11, Node 20. All services expose `GET /v1/health`.
- Config via env: `CALL_SERVER_URL=http://localhost:8000`, `SPEECH_SERVICE_URL=http://localhost:8001`, `SPEAKER_SERVICE_URL=http://localhost:8002`, `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.

## A4. Interface 1: Frontend <-> Call Server (Role 1 <-> Role 2)

**HTTP**
- `POST /v1/rooms/{room_id}/join` body `{ "participant_id": "...", "name": "...", "lang": "hi" }` returns `{ "livekit_token": "...", "livekit_url": "..." }`

**WebSocket (JSON): `WS /ws/room/{room_id}?participant_id=...`**

Client to server:
```json
{"type":"hello","participant_id":"p-1","name":"Asha","lang":"hi"}
{"type":"net_stats","rtt_ms":120,"packet_loss_pct":0.5,"bitrate_kbps":900,"jitter_ms":12}   // every 2 s
{"type":"set_lang","lang":"kn"}
```

Server to client:
```json
{"type":"participants","list":[{"participant_id":"p-1","name":"Asha","lang":"hi"}]}
{"type":"active_speaker","holder":"p-1","overlap":["p-2"],"ts_ms":1730000000000}
{"type":"mode","mode":"audio","reason":"good_network"}          // mode is "audio" or "subtitle"
{"type":"translation","chunk_id":"p-1-12","from":"p-1","from_name":"Asha",
 "lane":"main","mode":"audio","src_lang":"en","lang":"hi",
 "source_text":"Hello everyone","text":"सभी को नमस्कार",
 "audio_url":"http://localhost:8001/audio/abc.wav","ts_ms":1730000000500}
{"type":"error","message":"..."}
```
Rules: `lane` is `"main"` (token holder) or `"overlap"` (overlapping talker, always subtitle, `audio_url` is null). When `mode` is `"subtitle"`, `audio_url` is null.

**WebSocket (binary): `WS /ws/audio/{room_id}/{participant_id}`**: the frontend sends mic frames (A3 format) continuously while connected.

## A5. Interface 2: Call Server <-> Speaker Service (Role 2 <-> Role 4)

- `WS /ws/vad/{room_id}/{participant_id}`: the call server sends binary mic frames. The speaker service replies with JSON:
  `{"type":"vad","participant_id":"p-1","state":"speech_start"|"speech_end","ts_ms":...}`
- `WS /ws/token/{room_id}`: the call server subscribes and receives:
  `{"type":"token_update","room_id":"room1","holder":"p-1"|null,"overlap":["p-2"],"ts_ms":...}`

Token policy (Role 4 implements):
1. Nobody holds the token, so the first participant to start speaking becomes `holder`.
2. Anyone who starts speaking while the token is held goes into `overlap`.
3. When the holder stops (silence of at least 700 ms), the token is released. If someone in `overlap` is still speaking, the longest-waiting one becomes `holder`. Otherwise `holder` is null.
4. Hysteresis: a speaker must be active for at least 200 ms to count, and the holder cannot be switched away within 1 s of getting the token.

## A6. Interface 3: Call Server <-> Speech Service (Role 2 <-> Role 3)

`POST /v1/process-chunk` (multipart/form-data)
- `audio`: WAV file (A3 format)
- `room_id`, `participant_id`, `chunk_id`
- `src_lang`: `"auto"` or a language code
- `tgt_langs`: JSON list, e.g. `["hi","kn"]` (unique target languages in the room, never per listener)
- `want_audio`: `"true"` or `"false"`. If false, skip TTS to save time and GPU.
- `prev_text` (optional): the previous source text from this speaker, for continuity.

Response 200:
```json
{
  "chunk_id":"p-1-12","participant_id":"p-1",
  "detected_lang":"en","source_text":"Hello everyone",
  "translations":{
    "hi":{"text":"सभी को नमस्कार","audio_url":"http://localhost:8001/audio/abc.wav"},
    "kn":{"text":"ಎಲ್ಲರಿಗೂ ನಮಸ್ಕಾರ","audio_url":null}
  },
  "timings_ms":{"asr":420,"mt":180,"tts":350,"total":950}
}
```
`audio_url` is null when `want_audio` is false or TTS failed (text is still returned).

`GET /audio/{file}.wav`: serves generated speech.

`GET /v1/health` returns `{"status":"ok","queue_depth":0,"avg_latency_ms":950,"device":"cpu"|"cuda"}`

## A7. Network decision rule (Role 2 implements; thresholds live in `shared/config.yaml`)

Per listener, every 2 s window:
- GOOD if `rtt_ms < 150` AND `packet_loss_pct < 2` AND `bitrate_kbps > 500` AND speech-service `avg_latency_ms < 3000`
- Otherwise POOR.
- Switch only after **3 consecutive windows** in the new state (hysteresis). GOOD means `mode: audio`, POOR means `mode: subtitle`.
- The initial mode is `subtitle` until the first GOOD result.

## A8. Mock-first rule (the key to working in parallel)

Within your first working session, ship a **mock** of the interfaces you provide, then build the real thing behind the same API:
- Role 3 mock: `/v1/process-chunk` returns canned translations after a fake 800 ms delay.
- Role 4 mock: emits a fake `token_update` that rotates through participants every 5 s.
- Role 2 mock: a gateway that sends fake `participants`, `active_speaker`, `mode` and `translation` messages every few seconds.
- Role 1 mock: a small test page or script that sends `hello`, `net_stats` and PCM frames (or a WAV file played as frames).

Every service must start with `MOCK=1` for the mock behavior and `MOCK=0` for the real one.

## A9. Working rules for Claude (apply in every role)

- Stay inside your own folder. If you need something from another role, write it as a request and stop. Do not build it.
- Follow this contract exactly: same field names, ports, formats. Never silently change it.
- If you believe the contract must change, output a block titled `CONTRACT CHANGE REQUEST` with: what, why, the exact new wording. Then wait for the team.
- Keep the code simple and readable for a student mini project. Add a short README in your folder with run steps and a curl or websocat test for each endpoint.
- Make it run on a laptop without a GPU first (small models, CPU). GPU is optional.
- Write small tests for your acceptance criteria. After each step, tell me what to run to verify it.
- Work step by step. Finish and verify a step before starting the next.

---

# PART B1: ROLE 1, FRONTEND (Video Call + UI + Final Integration Lead)

```
You are my coding partner. I am Role 1 (Frontend) of a 4-person team. The shared contract (Part A) is above; follow it exactly. I own ONLY the `frontend/` folder.

GOAL
Build a React web app where 2 to 4 people join a video call, and each person sees translated subtitles or hears translated audio in their own language, with the app switching automatically based on the mode sent by the call server.

TECH
React + Vite, Tailwind CSS, LiveKit client SDK (livekit-client + @livekit/components-react), AudioWorklet for mic capture, native WebSocket.

BUILD IN THIS ORDER
Step 1 (basic call): Join screen (name, room, my language: English/Hindi/Kannada). Call `POST /v1/rooms/{room}/join`, connect to LiveKit, show a video grid with mute/camera buttons. If the call server is not ready, use a LiveKit dev token from a temporary local script.
Step 2 (mic capture): AudioWorklet that converts the mic to PCM16, 16 kHz, mono, in 512-sample frames and sends them as binary messages to `WS /ws/audio/{room}/{participant}`. Verify frame size is exactly 1024 bytes.
Step 3 (event socket): Connect `WS /ws/room/{room}?participant_id=...`. Send `hello` on open, `set_lang` on change, and `net_stats` every 2 s using LiveKit/WebRTC `getStats()` (rtt, packet loss %, bitrate kbps, jitter). Auto-reconnect.
Step 4 (UI features from server events):
  - Subtitle panel: show `translation` messages as captions, with speaker name and a small label for the source language. Show `lane: "overlap"` messages in a separate "also speaking" lane.
  - Audio playback: when a `translation` has `audio_url` and `mode` is `audio`, queue and play it (one at a time, in order, no overlap). Duck or lower the original call audio of the speaker while the translated audio plays.
  - Active speaker indicator on the video tile from `active_speaker` (holder highlighted, overlap marked).
  - Mode badge from `mode` ("Audio mode" / "Subtitle mode (weak network)"). No manual toggle is needed because switching is automatic; add a small debug panel (hidden by default) showing last net_stats, current mode, and chunk delay.
Step 5 (mock testing): Build against a mock gateway (a tiny Node or Python script that replays the server JSON messages from the contract) so I can develop before Role 2 is ready.
Step 6 (integration lead): When the other services exist, run the full flow with 3 to 4 browser tabs, collect bugs by owner (Role 2/3/4) as a list, and keep a `INTEGRATION.md` checklist in the repo root PR description.

ACCEPTANCE TESTS
- 3 tabs join the same room, video works.
- Frames sent are 1024 bytes each, about 31 per second.
- With the mock gateway, subtitles, overlap lane, audio queue, active-speaker highlight and mode badge all update correctly.
- Translated audio never plays two clips at once.

DELIVERABLES
Working frontend, README (how to run, env vars), a short demo script for the final presentation, and a screenshot set for the report.

Start with Step 1. Ask me at most 2 questions if anything is unclear, otherwise begin.
```

---

# PART B2: ROLE 2, CALL SERVER + NETWORK MONITORING (the Hub)

```
You are my coding partner. I am Role 2 (Backend: Call Server + Network Monitoring) of a 4-person team. The shared contract (Part A) is above; follow it exactly. I own ONLY the `call-server/` folder and `shared/config.yaml`. My service is the HUB: it connects the frontend, the speaker service and the speech service.

GOAL
Build a FastAPI server that (1) issues LiveKit tokens, (2) receives each participant's mic audio, (3) forwards it to the speaker service for VAD and token passing, (4) cuts speech into chunks and sends them to the speech service, (5) decides audio vs subtitle per listener from network and server conditions, and (6) delivers `translation` events to each listener.

TECH
Python 3.11, FastAPI, uvicorn, websockets/httpx, livekit-api (token generation), asyncio, PyYAML. LiveKit server in dev mode (`livekit-server --dev`) or LiveKit Cloud free tier.

BUILD IN THIS ORDER
Step 1 (skeleton + mock gateway): FastAPI app with `POST /v1/rooms/{room}/join` (LiveKit token), `WS /ws/room/{room}` and `WS /ws/audio/{room}/{pid}`. With `MOCK=1`, the room socket sends fake `participants`, `active_speaker`, `mode` and `translation` messages every few seconds so Role 1 can build the UI. SHIP THIS FIRST.
Step 2 (room state): In-memory registry of rooms and participants (name, lang, current mode, latest net stats). Broadcast `participants` on join/leave/set_lang.
Step 3 (network monitor + decision engine): Read `net_stats` every 2 s per listener. Also poll the speech service `GET /v1/health` every 2 s for `avg_latency_ms` and `queue_depth`. Apply the rule in A7 with hysteresis (3 windows), load thresholds from `shared/config.yaml`, and send `mode` events only when the mode changes. Log every decision with the reason. Make the decision function pure (input stats, output mode) so it is easy to unit test.
Step 4 (VAD forwarding): For each participant, open `WS /ws/vad/{room}/{pid}` to the speaker service and forward the mic frames. Subscribe to `WS /ws/token/{room}` and broadcast `active_speaker` to all clients. Handle reconnects.
Step 5 (chunking): Per participant, buffer PCM frames. Cut a chunk when VAD says `speech_end` OR when 4 s of continuous speech has accumulated (do not wait for pauses). Drop chunks shorter than 400 ms or containing no speech. Wrap each chunk as a WAV and assign `chunk_id`.
Step 6 (translation fan-out): For each chunk call the speech service once with the set of unique target languages in the room (never per listener). `want_audio` is true if at least one listener of any target language is in audio mode. Then for each listener build a `translation` event in their language: `mode` = their current mode, `audio_url` only if mode is audio, `lane` = `main` for the token holder, `overlap` for overlapping talkers (overlap is always subtitle). Do not send a listener their own speech. Skip listeners whose language equals the speaker's.
Step 7 (resilience + metrics): Timeouts on the speech service (6 s), drop and log if exceeded, queue limit to avoid pile-up. Record per-chunk latency (capture to delivery) to `metrics.csv` for the final report (columns: ts, chunk_id, mode, asr/mt/tts ms, total ms, network state).

ACCEPTANCE TESTS
- Unit tests for the decision function: good-to-poor needs 3 bad windows, poor-to-good needs 3 good windows, initial mode is subtitle, thresholds read from config.
- With the Role 3 and 4 mocks running, a fake client gets correct events end to end.
- Throttle one client with Chrome DevTools (Slow 3G): only that listener switches to subtitle, others stay on audio.
- Translating for 4 users in 3 languages makes 1 speech-service call per chunk, not 4.

DELIVERABLES
Working call server, `shared/config.yaml`, README with curl/websocat tests, `metrics.csv` generator, and a latency chart script (matplotlib) for the report.

Start with Step 1 (mock gateway). Ask me at most 2 questions if anything is unclear, otherwise begin.
```

---

# PART B3: ROLE 3, SPEECH TRANSLATION PIPELINE (ASR -> MT -> TTS)

```
You are my coding partner. I am Role 3 (Backend: Speech Translation Pipeline) of a 4-person team. The shared contract (Part A) is above; follow it exactly. I own ONLY the `speech-service/` folder.

GOAL
Build a FastAPI service that takes a short audio chunk and returns the transcript, the translation into one or more target languages, and optionally translated speech, quickly and accurately for English, Hindi and Kannada (extendable to other Indian languages).

TECH
Python 3.11, FastAPI, uvicorn. ASR: faster-whisper (start with `small` or `base`, int8 on CPU; larger on GPU). Translation: AI4Bharat IndicTrans2 (distilled 200M models for en-indic and indic-en; pivot through English for indic-to-indic). TTS: gTTS first (simple, supports hi and kn); optionally AI4Bharat Indic-TTS or Piper later. Language detection from Whisper's detected language. soundfile/numpy for audio.

BUILD IN THIS ORDER
Step 1 (mock service): `POST /v1/process-chunk` and `GET /v1/health` exactly as in A6, returning canned output after about 800 ms when `MOCK=1`. Serve a sample WAV at `/audio/*.wav`. SHIP THIS FIRST.
Step 2 (offline notebook/script): `audio.wav -> faster-whisper -> text`. Measure speed on CPU. Test with English, Hindi and Kannada samples. Handle `src_lang="auto"` using Whisper's language detection, and restrict to the supported language set (fall back to the most likely supported one).
Step 3 (translation): Wrap IndicTrans2 behind a function `translate(text, src, tgt)`. Cache loaded models. If src or tgt is not English, pivot via English. Skip translation when src == tgt. Test with a small set of sentences per language pair.
Step 4 (TTS): `synthesize(text, lang) -> wav file` saved under `audio/` with a unique name, returned as `audio_url`. Skip when `want_audio` is false. Failures in TTS must not fail the request (return text with `audio_url: null`).
Step 5 (real endpoint): Wire ASR, then MT for each language in `tgt_langs`, then TTS per language (only if `want_audio`). Run the independent translations concurrently. Use `prev_text` as context if it helps. Return `timings_ms` per stage. Add a request queue with a concurrency limit and report `queue_depth` and rolling `avg_latency_ms` in `GET /v1/health`.
Step 6 (speed): Measure per-stage time for 3 s and 5 s chunks. Optimize: model warm-up at startup, int8 quantization, VAD filter off (the speaker service already does VAD), beam size small for ASR, batch translation, cleanup of old audio files.
Step 7 (quality evaluation): Make a small test set (20 to 30 sentences per language pair, with reference translations from a native speaker on the team). Compute BLEU (sacrebleu) and word error rate for ASR (jiwer). Produce a results table for the report.

ACCEPTANCE TESTS
- `MOCK=1` and `MOCK=0` both pass the same contract test script (a pytest that validates the response JSON schema).
- A 4 s English chunk to Hindi and Kannada returns text for both within a target of about 3 s on CPU, or about 1 s on GPU (report the actual numbers).
- Wrong or noisy audio returns an empty `source_text` with HTTP 200 and no crash.
- `want_audio=false` skips TTS and `tts` timing is 0.

DELIVERABLES
Working service, README with a curl example, the evaluation table (BLEU/WER and latency per stage), and a short note on model choices for the report.

Start with Step 1 (mock service). Ask me at most 2 questions if anything is unclear, otherwise begin.
```

---

# PART B4: ROLE 4, SPEAKER DETECTION (VAD + TOKEN PASSING)

```
You are my coding partner. I am Role 4 (Backend: Speaker Detection with VAD and Token Passing) of a 4-person team. The shared contract (Part A) is above; follow it exactly. I own ONLY the `speaker-service/` folder.

GOAL
Build a FastAPI service that listens to each participant's mic stream, detects automatically when they start and stop speaking (VAD), and manages a per-room speaking "token" so only one person is the active speaker at a time, while overlapping talkers are flagged for the subtitle lane.

TECH
Python 3.11, FastAPI, uvicorn, WebSockets, Silero VAD (torch, via `silero-vad`) or py-webrtcvad as a lightweight fallback, numpy, asyncio.

BUILD IN THIS ORDER
Step 1 (mock service): `WS /ws/vad/{room}/{pid}` (accepts binary frames, replies with fake `vad` events) and `WS /ws/token/{room}` (emits a fake `token_update` that rotates through known participants every 5 s) when `MOCK=1`. Also `GET /v1/health`. SHIP THIS FIRST.
Step 2 (offline VAD): Script that reads a WAV, runs it in 512-sample frames (16 kHz) through Silero VAD, and prints speech segments with start/end times. Tune the threshold (start around 0.5) and test with clean speech, background noise, and silence.
Step 3 (streaming VAD per participant): A `VadStream` class that takes one 1024-byte frame at a time and emits `speech_start` / `speech_end` with these rules: start after at least 200 ms of speech, end after at least 700 ms of silence. One VAD state per (room, participant). Emit the `vad` JSON events from A5 on the WebSocket.
Step 4 (token manager): A `TokenManager` per room, implementing the token policy in A5 exactly (first speaker gets the token, others go to `overlap`, longest-waiting overlapped speaker who is still speaking is promoted on release, 1 s minimum hold). Keep it a pure state machine (`on_speech_start(pid, t)`, `on_speech_end(pid, t)`, `state()`), so it can be unit tested without audio. Broadcast `token_update` on `WS /ws/token/{room}` only when state changes.
Step 5 (real integration): Connect Steps 3 and 4: VAD events from every participant of a room feed that room's TokenManager. Clean up state when a socket closes (a disconnected holder must release the token).
Step 6 (robustness + stats): Handle frames of wrong size (log and skip), late joiners, rooms with 1 person, and very fast start/stop (flicker). Add an optional debug endpoint `GET /v1/rooms/{room}/state`. Measure CPU use for 4 simultaneous streams.
Step 7 (evaluation): Make test recordings (two people talking separately, then overlapping, plus noise). Report VAD accuracy (start/end timing error vs manual labels, false triggers per minute), and token-switch correctness in overlap scenarios. Put the results in a table for the report.

ACCEPTANCE TESTS
- Unit tests for the TokenManager covering: single speaker; second speaker overlaps then is promoted after release; holder disconnects; flicker under 200 ms ignored; 1 s minimum hold respected.
- Silence and background noise produce no `speech_start`.
- 4 simultaneous streams run in real time on a laptop CPU.
- `MOCK=1` and `MOCK=0` emit messages that match A5 exactly.

DELIVERABLES
Working service, README with a websocat/python test client, a unit-test suite, a demo script that plays two WAV files into two participants and prints token changes, and the evaluation table for the report.

Start with Step 1 (mock service). Ask me at most 2 questions if anything is unclear, otherwise begin.
```

---

# Quick integration timeline (for the whole team)

| Session | What should exist |
|---|---|
| 1 | Repo + CONTRACT.md committed. All four mocks running (`MOCK=1`). |
| 2 | Frontend connected to mock gateway. Call server connected to both mock services. Full fake flow visible in the browser. |
| 3 to 5 | Each role replaces its mock with the real implementation (`MOCK=0`), one service at a time, testing with the rest still on mocks. |
| 6 | All real: 3 to 4 browser tabs, test on slow and fast internet. |
| 7 | Evaluation tables and `metrics.csv`, report sections, slides, demo rehearsal. |
