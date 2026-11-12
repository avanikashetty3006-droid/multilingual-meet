# multilingual-meet

"Generative AI Based Multilingual Translation System for Real-Time Video Conferencing" (College Mini Project, AI & ML Department).

Participants speak different languages (English, Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi). Each listener hears or reads the speech in their chosen language in real time.

## Architecture

Hub-and-spoke architecture:
- **Frontend (Role 1, port 5173)**: React + Vite + LiveKit WebRTC client + AudioWorklet mic capture.
- **Call Server (Role 2, port 8000 - Hub)**: Orchestrates rooms, network monitoring, adaptive switching (Audio vs Subtitle), and speech fan-out.
- **Speech Service (Role 3, port 8001)**: Speech translation pipeline (ASR -> MT -> TTS) with `/v1/process-chunk`.
- **Speaker Service (Role 4, port 8002)**: VAD + Token passing manager to arbitrate the active speaker.
- **Load Test**: Synthetic participant bot generator.

## Shared Contract
See [`shared/CONTRACT.md`](file:///shared/CONTRACT.md) for the exact schemas, ports, audio formats, and token-passing rules.

## Quick Start (Mock Mode)

Start all services with `MOCK=1` to test end-to-end without heavy GPU models:

1. **Call Server (Role 2)**:
   ```bash
   cd call-server
   pip install -r requirements.txt
   MOCK=1 uvicorn main:app --port 8000
   ```

2. **Speech Service (Role 3)**:
   ```bash
   cd speech-service
   pip install -r requirements.txt
   MOCK=1 uvicorn main:app --port 8001
   ```

3. **Speaker Service (Role 4)**:
   ```bash
   cd speaker-service
   pip install -r requirements.txt
   MOCK=1 uvicorn main:app --port 8002
   ```

4. **Frontend (Role 1)**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
