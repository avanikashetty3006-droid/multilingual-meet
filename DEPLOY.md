# VAAK Production Deployment Guide (DEPLOY.md)

This document provides complete instructions for deploying the **VAAK** (वाक्) real-time multilingual video-conferencing system to production for real users.

---

## 1. Prerequisites & System Requirements

- **Server**: Linux (Ubuntu 22.04 LTS recommended) with at least 4 CPU cores, 8 GB RAM (16 GB recommended if running local Whisper/TTS models).
- **Public Domain**: A domain name (e.g., `vaak.yourdomain.com`).
- **HTTPS Certificate**: Mandatory. Browsers block `navigator.mediaDevices.getUserMedia` (camera and microphone) on non-localhost origins unless served over HTTPS.
- **Docker & Docker Compose**: Docker Engine 24+ and Docker Compose v2+.

---

## 2. Google OAuth 2.0 Credentials Setup

VAAK uses Google Identity Services (GIS) for real user authentication.

1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or select your project (e.g., `vaak-conferencing`).
3. Configure the **OAuth Consent Screen**:
   - User Type: **External**
   - App Name: `VAAK Multilingual Meet`
   - User support email & Developer contact info
   - Scopes: `email`, `profile`, `openid`
4. Create **Credentials** &rarr; **OAuth 2.0 Client ID**:
   - Application Type: **Web application**
   - Name: `VAAK Web Client`
   - **Authorized JavaScript origins**:
     - `https://vaak.yourdomain.com` (and `http://localhost:5173` for development)
   - **Authorized redirect URIs**:
     - `https://vaak.yourdomain.com`
5. Copy your **Client ID** (e.g. `123456789-abcdef.apps.googleusercontent.com`).

---

## 3. Environment Configuration (`.env`)

Create a `.env` file in the repository root:

```env
# Domain & Protocol
DOMAIN=vaak.yourdomain.com

# Google Authentication
VITE_GOOGLE_CLIENT_ID=123456789-abcdef.apps.googleusercontent.com
SESSION_SECRET=generate-a-strong-random-32-character-secret-key

# PostgreSQL
POSTGRES_USER=vaak_prod_user
POSTGRES_PASSWORD=use-a-strong-random-password-here
POSTGRES_DB=vaak_prod_db

# LiveKit WebRTC SFU
LIVEKIT_URL=wss://livekit.yourdomain.com
LIVEKIT_API_KEY=prod_livekit_key_987
LIVEKIT_API_SECRET=prod_livekit_secret_abc123

# Frontend
VITE_API_BASE_URL=/api
VITE_LIVEKIT_URL=wss://livekit.yourdomain.com
```

---

## 4. Reverse Proxy & HTTPS (Caddy or Cloudflare)

### Option A: Using Caddy (Automatic HTTPS)

Caddy automatically provisions Let's Encrypt certificates and handles HTTP/2 and WebSocket upgrades. Place this `Caddyfile` on your server:

```caddy
vaak.yourdomain.com {
    # Reverse proxy to the frontend Nginx container (port 80)
    reverse_proxy localhost:80
}

livekit.yourdomain.com {
    # LiveKit WebRTC signaling
    reverse_proxy localhost:7880
}
```

### Option B: Cloudflare SSL / Nginx
If using Cloudflare, set SSL/TLS encryption mode to **Full (strict)** and point the DNS A records to your server IP.

---

## 5. LiveKit SFU Ports & Firewall Setup

LiveKit handles low-latency WebRTC audio and video streaming. Ensure your cloud firewall (AWS Security Group, GCP Firewall, or UFW) allows:

| Port | Protocol | Purpose |
|---|---|---|
| `80` | TCP | HTTP (ACME challenge & redirect) |
| `443` | TCP | HTTPS (Web app & API) |
| `7880` | TCP | LiveKit HTTP & WebSocket signaling |
| `7881` | TCP | LiveKit WebRTC TCP fallback |
| `50000-50200` | **UDP** | **WebRTC media (audio & video RTP/RTCP)** |

> **IMPORTANT**: Opening the UDP port range is mandatory for peer video and audio tracks to flow. If UDP is blocked, WebRTC will fall back to TCP with higher latency.

Alternatively, you can use [LiveKit Cloud](https://livekit.io/cloud) by setting `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` to your cloud credentials.

---

## 6. Launching the Stack

```bash
# 1. Build and start all services in detached mode
docker compose up -d --build

# 2. Verify all containers are healthy
docker compose ps

# 3. Inspect application logs
docker compose logs -f frontend call-server
```

---

## 7. Rollback Procedure

If a deployed version causes unexpected issues:

```bash
# 1. Revert Git repository to the previous stable release commit
git checkout <previous-commit-hash-or-tag>

# 2. Rebuild and restart the containers with zero downtime
docker compose up -d --build

# 3. Verify services are running
docker compose ps
```

---

## 8. Post-Deployment Verification Checklist

Execute these verification checks immediately after deployment:

1. **HTTPS & Certificate Check**:
   - Open `https://vaak.yourdomain.com`.
   - Verify the SSL padlock is valid.
2. **Google Sign-In**:
   - Click **"Sign in with Google"**.
   - Verify that your Google account logs in and redirects to the intro animation.
3. **Intro Animation**:
   - Confirm the cinematic world-map-to-VAAK logo sequence plays without lag.
   - Verify that clicking **"Skip Intro"** immediately lands on Home.
   - Verify that refreshing the page does **not** replay the intro (persists per session).
4. **Create a Meeting**:
   - On the Home screen, click **"Start New Meeting"**.
   - Verify that an unguessable meeting ID is generated (format `xxx-xxxx-xxx`).
   - Copy the shareable invite link.
5. **Pre-Join Lobby & Permissions**:
   - In the lobby, verify that your local camera preview is mirrored.
   - Speak into the mic and verify device selection.
   - Select your target listening language (e.g. Hindi or Kannada).
   - Click **"Join Meeting Now"**.
6. **Multi-Device Live Call**:
   - Open the copied link on a second device or separate browser profile.
   - Speak in English from Device 1; observe Device 2 receiving translated Hindi subtitles and translated audio playback.
7. **Adaptive Subtitle Mode**:
   - Open the **QoS Stats** panel and tick **"Simulate poor network"**.
   - Confirm the top mode badge transitions from **Audio Mode** &rarr; **Subtitle Mode (Adaptive)** within ~6 seconds.
