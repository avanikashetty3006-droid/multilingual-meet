# SHARED CONTRACT

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
