# VAAK – Multilingual Video Conferencing: Integration Guide & Checklist

This document tracks the end-to-end integration across all 4 roles of the **VAAK** (वाक्) college mini project (AI & ML Dept).

---

## 1. System Architecture Matrix

| Role | Component | Port | Interface | Primary Contract Section |
|---|---|---|---|---|
| **Role 1** | Frontend (React + Vite) | `5173` | UI, AudioWorklet (16 kHz PCM16), LiveKit client | Contract A4, B1 |
| **Role 2** | Call Server (FastAPI Hub) | `8000` | Token Issuer, WS Hub, Network Decision Engine, O(N) Fan-out | Contract A4, A5, A6, A7, B2 |
| **Role 3** | Speech Service | `8001` | `POST /v1/process-chunk` (ASR &rarr; MT &rarr; TTS) | Contract A6, B3 |
| **Role 4** | Speaker Service | `8002` | `WS /ws/vad`, `WS /ws/token` (Silero VAD + Token Passing) | Contract A5, B4 |

---

## 2. Integration Verification Checklist

### Phase 1: Mock Integration (Session 1 & 2)
- [x] Shared Contract committed (`shared/CONTRACT.md`)
- [x] Centralized thresholds committed (`shared/config.yaml`)
- [x] Call server runs with `MOCK=1` on port 8000
- [x] Frontend runs with `npm run dev` on port 5173
- [x] Frontend connects to Call Server event WebSocket (`/ws/room/{room_id}`)
- [x] Frontend streams 1024-byte PCM16 binary mic frames (`/ws/audio/{room_id}/{participant_id}`)
- [x] Simulated active speaker rotation and translation chunks verified in UI

### Phase 2: Role 1 & Role 2 Hardening (All Resolved)
- [ ] **WebRTC Real QoS Stats**: implemented in `netStats.js` (per-window RTT, loss, bitrate, jitter from the publisher and subscriber `getStats()`). Tick this only after you have opened the QoS panel in a real call and seen non-simulated numbers; if the panel says "Waiting for WebRTC statistics", fix `findStatsSources()` in `App.jsx`.
- [x] **Microphone Mute Synchronization**: Muting microphone in conference stops audio transmission so muted users are never translated.
- [x] **Ghost Reconnect Prevention**: Added `closedByUs` flag to `useRoomSocket` ensuring disconnect on leave never triggers reconnect loops.
- [x] **Decoupled Language Switching**: Switching listening language triggers `set_lang` WebSocket event without tearing down the connection.
- [x] **Audio Ducking**: Translated speech queues sequentially and automatically ducks room audio to 15% volume during playback.
- [ ] **Cross-Browser Audio Worklet**: `micWorklet.js` tries a 16 kHz AudioContext and falls back to the native rate with averaging resampler. Unit-checked with `node frontend/tests/resampler.check.mjs`; tick after a real test in Chrome AND Firefox (the server should receive 1024-byte frames).
- [x] **20+ Participant Scaling**: Large active-speaker spotlight tile + paginated thumbnail strip (6 per page) + LiveKit `adaptiveStream` & `dynacast`.
- [x] **Overlap Lane Limit**: latest line of each distinct talker, at most 2 talkers (Contract A4/B1).
- [x] **Chunk Latency**: Measured and displayed in real-time QoS Debug inspector.

---

## 3. Live Demo Script (Presentation Day)

### Step 1: Demo Sign-In
1. Open browser to `http://localhost:5173`.
2. Present the **VAAK Conference Access** screen.
3. Select a demo speaker profile (e.g. *Speaker 1 - English* or *Speaker 2 - Hindi*).
4. Click **"Continue as Demo Speaker"**.

### Step 2: Cinematic Logo Reveal Animation
1. Show the 5-stage canvas particle animation:
   - **Stage 1 (Opening)**: The centered world map appears on the warm Vaak background (`#FFF2DF`, `#3E2522`).
   - **Stage 2 (Dotted Transformation)**: Continents dissolve into shimmering dots with animated communication arcs between international hubs.
   - **Stage 3 (Gathering)**: Magnetic swirling convergence toward center.
   - **Stage 4 (Assembly)**: Particles assemble into the video camera glyph and `A`/`अ` speech bubbles.
   - **Stage 5 (Final Reveal)**: Official VAAK logo appears with the tagline: *"Multilingual Video Translation"*.
2. Click **"Enter Video Conference"** (or allow auto-transition).

### Step 3: Pre-Meeting Lobby & Camera Test
1. Set Room ID (e.g., `room1`).
2. Test camera and microphone.
3. Choose listening language (e.g., *Hindi* or *Kannada*).
4. Click **"Join Meeting"**.

### Step 4: Live Translation & Automatic Audio/Subtitle Switching
1. Open a second browser tab as another participant (e.g., *Speaker 2 - English*).
2. Speak in English into tab 2.
3. Observe tab 1:
   - **Main Subtitle Lane**: Instant translated Hindi/Kannada subtitles appear.
   - **Audio Mode**: Translated speech audio plays smoothly; original voice is ducked.
   - **Token Holder Halo**: Active speaker tile glows with a gold border and token badge.

### Step 5: Poor Network Test (Main Project Idea)
> Chrome DevTools "Slow 3G" does NOT affect WebRTC media, so it cannot be used for this test.

1. Open the **QoS Stats** panel and tick **Simulate poor network** (sends RTT 450 ms, loss 6 %, bitrate 200 kbps). For a real degraded link use an OS tool instead: Linux `tc netem`, Windows Clumsy, macOS Network Link Conditioner.
2. Within 3 consecutive windows (about 6 seconds), observe the Mode Badge at top:
   - Switches from **Audio Mode** &rarr; **Subtitle Mode (Adaptive)**.
   - Reason displays one of: `high_rtt_450ms`, `high_packet_loss_6.0%`, `low_bitrate_200kbps`.
   - Translated audio stops to save bandwidth; subtitles continue uninterrupted.
3. Untick the box (or remove the OS throttle):
   - After 3 consecutive good windows, the mode switches back to **Audio Mode** (reason `good_network`).
4. Without a browser: `python bots.py --num-bots 10 --network mixed --wav speech16k.wav` makes half the bots report a poor network; they must receive subtitles only.

### Step 6: 20+ Participant Bot Scale Test
1. In terminal, run:
   ```bash
   cd load-test
   python bots.py --num-bots 20 --languages en,hi,kn --speak-pattern overlap --overlap-count 6 --wav speech16k.wav
   ```
   (`--users` also works. The WAV must be 16 kHz mono PCM16: `ffmpeg -i input.mp3 -ar 16000 -ac 1 -sample_fmt s16 speech16k.wav`.)
2. Observe frontend:
   - Roster drawer shows 20 participants with language badges.
   - Overlap lane shows at most 2 overlapping talkers; extraneous talkers are dropped per contract rules.
   - The bot run prints a summary at the end (messages by type, translations by lane and mode).

> **Known limit:** bots join the call server only, not the LiveKit video call. They fill the roster and exercise translation, but there are no video tiles for them, so thumbnail pagination needs real browser tabs or LiveKit's own load-test tooling.

---

## 4. Report Screenshots Checklist

For the project report, capture the following 6 figures:
- **Figure 1**: VAAK Demo Access Screen (`GoogleAuth.jsx`) showing warm brand aesthetic.
- **Figure 2**: Canvas Particle Logo Reveal (`LogoReveal.jsx`) during the Stage 4 assembly & Stage 5 reveal.
- **Figure 3**: Pre-call Lobby (`JoinScreen.jsx`) with camera preview and language selection.
- **Figure 4**: 20+ Participant Conference Stage showing active speaker spotlight, paginated thumbnails, and participant roster.
- **Figure 5**: Translation Subtitle Panel showing main lane captions and overlap lane.
- **Figure 6**: Real-Time QoS Debug Inspector showing RTT, packet loss, bitrate, jitter, chunk delay, and mode transition.
