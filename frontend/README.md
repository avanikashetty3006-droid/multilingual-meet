# VAAK Frontend (Role 1)

Generative AI Based Multilingual Translation System for Real-Time Video Conferencing.

Frontend built with React + Vite, WebRTC / LiveKit client SDK, AudioWorklet for low-latency PCM16 mic streaming, and native WebSocket event channels.

---

## Features
- **VAAK Identity**: Premium brand aesthetic based on the Sanskrit concept of speech (*वाक्*), styled in warm earthy tones (`#3E2522`, `#8C6E63`, `#D3A376`, `#FFE0B2`, `#FFF2DF`).
- **Demo Access (Google Workspace Ready)**: Simulated one-tap demo speaker sign-in without hardcoding sensitive personal emails, architected for quick drop-in of Google Identity Services (`@react-oauth/google`).
- **Cinematic Logo Reveal Animation**: 5-stage canvas particle reveal:
  1. Opening centered World Map
  2. Dotted transformation & global language network arcs
  3. Magnetic particle gathering motion
  4. VAAK logo assembly (camera glyph, bilingual `A`/`अ` bubbles, ribbon `V`)
  5. Final crisp reveal with tagline: *"Multilingual Video Translation"*
- **20+ Participant Scale Video Grid**:
  - Main active speaker spotlight (tracking token holder).
  - Paginated thumbnail strip (6 per page) preventing DOM/WebGL overload.
  - LiveKit `adaptiveStream` and `dynacast` enabled.
  - Collapsible Participant Roster drawer showing languages and speaking indicators.
- **Audio Ducking**: Automatically ducks call audio to 15% volume while translated speech plays.
- **Mute Synchronization**: Muting microphone stops translation audio transmission, preserving privacy and preventing ghost speech chunks.
- **Real-Time WebRTC QoS & Debug Inspector**: Reads RTT, packet loss, bitrate, and jitter directly from WebRTC peer connection `getStats()`, and displays chunk delay.

---

## Getting Started

### Prerequisites
- Node.js 18+ (tested on Node 20 & 24)
- npm or pnpm

### Installation
```bash
cd frontend
npm install
```

### Running Locally
```bash
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### Building for Production
```bash
npm run build
```

---

## Environment Variables
Create `.env` inside `frontend/` if connecting to a remote or non-default Call Server:
```env
VITE_CALL_SERVER_URL=http://localhost:8000
```

---

## Test Verification Checklist
1. **Audio Frame Size**: Emits exactly 512 samples Int16 = 1024 bytes per binary frame to `/ws/audio/{roomId}/{participantId}` (~31.25 frames/second).
2. **Audio Ducking**: While translated audio plays, all conference audio elements are ducked to 15% volume and restored to 100% on completion.
3. **Mute Privacy**: When microphone is muted via LiveKit controls, PCM audio streaming halts immediately.
4. **Network Switching**: Under network throttling (Slow 3G), listener switches from Audio mode to Subtitle mode within 3 consecutive windows (6 seconds).
5. **20+ Participant Scale**: Tested using `load-test/bots.py` with 20 bots; UI stays smooth with paginated thumbnails and active speaker spotlight.
