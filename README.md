# Multilingual Meet: Generative AI Real-Time Video Conferencing

"Generative AI Based Multilingual Translation System for Real-Time Video Conferencing" (AI & ML department mini project). Participants speak different languages (English, Hindi, Kannada, etc.), and each listener hears or reads speech translated into their preferred language in real time.

## Architecture

```
 Browser (Role 1: Frontend, :5173)
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

## Repository Structure

```
multilingual-meet/
  ├── shared/
  │   ├── CONTRACT.md             # Shared interface contract (Part A)
  │   └── config.yaml             # Network thresholds and engine settings
  ├── frontend/                   # Role 1 (React + Vite + LiveKit)
  │   ├── package.json
  │   ├── vite.config.js
  │   ├── index.html
  │   ├── README.md
  │   └── src/
  │       ├── main.jsx
  │       ├── App.jsx
  │       ├── JoinScreen.jsx
  │       ├── VideoGrid.jsx
  │       ├── SubtitlePanel.jsx
  │       ├── useRoomSocket.js
  │       ├── audioQueue.js
  │       └── micWorklet.js
  ├── call-server/                # Role 2 (FastAPI Hub & Network Decision Engine)
  │   ├── main.py
  │   ├── config.py
  │   ├── rooms.py
  │   ├── network_monitor.py
  │   ├── chunker.py
  │   ├── clients.py
  │   ├── requirements.txt
  │   ├── README.md
  │   └── tests/
  │       └── test_decision.py
  ├── speech-service/             # Role 3 (ASR -> MT -> TTS Pipeline)
  │   ├── main.py
  │   ├── asr.py
  │   ├── translate.py
  │   ├── tts.py
  │   ├── mock.py
  │   ├── requirements.txt
  │   ├── README.md
  │   └── tests/
  │       └── test_contract.py
  ├── speaker-service/            # Role 4 (VAD & Token Passing)
  │   ├── main.py
  │   ├── vad.py
  │   ├── token_manager.py
  │   ├── mock.py
  │   ├── requirements.txt
  │   ├── README.md
  │   └── tests/
  │       └── test_token_manager.py
  ├── load-test/                  # Load testing & simulation
  │   ├── bots.py
  │   └── README.md
  ├── .env.example
  ├── .gitignore
  └── README.md
```

## Quick Start (Mock Mode)

To run the entire system locally without requiring heavy AI model downloads or GPUs:

### 1. Call Server (Role 2 - Port 8000)
```bash
cd call-server
pip install -r requirements.txt
MOCK=1 uvicorn main:app --port 8000 --reload
```

### 2. Speech Service (Role 3 - Port 8001)
```bash
cd speech-service
pip install -r requirements.txt
MOCK=1 uvicorn main:app --port 8001 --reload
```

### 3. Speaker Service (Role 4 - Port 8002)
```bash
cd speaker-service
pip install -r requirements.txt
MOCK=1 uvicorn main:app --port 8002 --reload
```

### 4. Frontend (Role 1 - Port 5173)
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to join a call.
