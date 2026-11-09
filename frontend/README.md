# Role 1: Frontend (React + Vite + LiveKit)

Real-time video conferencing web client with adaptive multilingual translation and speech playback.

## Features
- **LiveKit Video Grid**: High-performance WebRTC conferencing with participant camera & screen sharing.
- **Microphone AudioWorklet**: Streams 16 kHz mono PCM16 audio in exactly 512-sample (1024-byte) frames via WebSockets to the Call Server.
- **Dual-Lane Captions**: Displays main speaker captions in the primary lane and simultaneous overlapping talkers in the "Also Speaking" lane.
- **Adaptive Mode Display**: Dynamically displays and reflects the server's network decision (`Audio Mode` vs `Subtitle Mode`).
- **Sequential Audio Queue**: Ensures translated speech clips play back sequentially without overlapping.

## Setup & Running

```bash
# 1. Install dependencies
npm install

# 2. Start development server (Port 5173)
npm run dev
```

## Environment Variables
Create a `.env` file in `frontend/` if needed:
```env
VITE_CALL_SERVER_URL=http://localhost:8000
```
