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
- [x] **WebRTC Real QoS Stats**: LiveKit `getStats()` queries candidate-pair RTT, inbound-rtp packet loss %, bitrate kbps, and jitter ms.
- [x] **Microphone Mute Synchronization**: Muting microphone in conference stops audio transmission so muted users are never translated.
- [x] **Ghost Reconnect Prevention**: Added `closedByUs` flag to `useRoomSocket` ensuring disconnect on leave never triggers reconnect loops.
- [x] **Decoupled Language Switching**: Switching listening language triggers `set_lang` WebSocket event without tearing down the connection.
- [x] **Audio Ducking**: Translated speech queues sequentially and automatically ducks room audio to 15% volume during playback.
- [x] **Cross-Browser Audio Worklet**: Safe AudioContext instantiation across Chrome, Firefox, and Safari with automatic resampling to 16 kHz.
- [x] **20+ Participant Scaling**: Large active-speaker spotlight tile + paginated thumbnail strip (6 per page) + LiveKit `adaptiveStream` & `dynacast`.
- [x] **Overlap Lane Limit**: Restricted to 2 lines per Contract A4/B1.
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

### Step 5: Network Throttling Test (Main Project Idea)
1. Open Chrome DevTools &rarr; Network tab &rarr; Throttling &rarr; select **"Slow 3G"** (or simulated bad connection).
2. Within 3 consecutive windows (6 seconds), observe the Mode Badge at top:
   - Switches automatically from **Audio Mode** &rarr; **Subtitle Mode (Adaptive)**.
   - Reason displays: `poor_network_high_rtt` or `high_packet_loss`.
   - Audio playback is halted to save bandwidth; subtitles continue uninterrupted.
3. Restore connection to "No throttling":
   - After 3 consecutive good windows, mode automatically switches back to **Audio Mode**.

### Step 6: 20+ Participant Bot Scale Test
1. In terminal, run:
   ```bash
   cd load-test
   python bots.py --users 20 --languages en,hi,kn --speak-pattern overlap
   ```
2. Observe frontend:
   - Roster drawer shows 20 participants with active speaking and language badges.
   - Thumbnail strip is cleanly paginated (6 per page) without FPS drops.
   - Overlap lane shows at most 2 overlapping talkers; extraneous talkers are dropped per contract rules.

---

## 4. Report Screenshots Checklist

For the project report, capture the following 6 figures:
- **Figure 1**: VAAK Demo Access Screen (`GoogleAuth.jsx`) showing warm brand aesthetic.
- **Figure 2**: Canvas Particle Logo Reveal (`LogoReveal.jsx`) during the Stage 4 assembly & Stage 5 reveal.
- **Figure 3**: Pre-call Lobby (`JoinScreen.jsx`) with camera preview and language selection.
- **Figure 4**: 20+ Participant Conference Stage showing active speaker spotlight, paginated thumbnails, and participant roster.
- **Figure 5**: Translation Subtitle Panel showing main lane captions and overlap lane.
- **Figure 6**: Real-Time QoS Debug Inspector showing RTT, packet loss, bitrate, jitter, chunk delay, and mode transition.
