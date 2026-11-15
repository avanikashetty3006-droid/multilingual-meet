# Deploying VAAK

## What you need
- One Linux server (Ubuntu 22.04+, 4 vCPU / 8 GB RAM minimum; more if speech-service runs on CPU) with Docker + Docker Compose v2.
- Two DNS names pointing at the server's public IP: `meet.example.com` (the app) and `lk.example.com` (LiveKit).
- Firewall open: TCP 80, 443, 7881 and **UDP 50000-50200** (media). Everything else stays closed.
- A Google OAuth Web client (see README_FIRST section 4) with `https://meet.example.com` as an authorized JavaScript origin, and the consent screen published.

## Steps
```bash
git clone <repo> vaak && cd vaak
cp .env.example .env && nano .env        # fill every value; generate secrets with: openssl rand -hex 32
docker compose --profile tls up -d --build
docker compose ps                        # all "running/healthy"
docker compose logs -f call-server       # no "DISABLED" warning, no traceback
```
`.env` is never committed. Keep a copy of it in a password manager.

## Post-deploy checklist
1. `https://meet.example.com` loads; DevTools Console shows no CSP "Refused to ..." errors.
2. Sign in with Google; cookie `vaak_session` is HttpOnly + Secure.
3. Create a meeting on a laptop, join from a phone on mobile data (this tests UDP/TURN reachability). Video both ways.
4. Speak: subtitles appear; with a good network, audio mode.
5. `docker compose logs call-server | grep -i error` is quiet; the QoS panel shows real numbers.
6. Sign in with a second account, friend request, presence, invite.

## Operations
- Update: `git pull && docker compose --profile tls up -d --build`
- Roll back: `git checkout <previous-tag>` then the same command. Database tables are only ever added, so rolling back code is safe.
- Backup: `docker compose exec postgres pg_dump -U vaak vaak > backup.sql` (cron it daily).
- Logs: `docker compose logs --since 1h call-server`.
- Without Caddy (your own TLS proxy): set `PROXY_HOPS=1`, run `docker compose up -d --build`, proxy your domain to `127.0.0.1:${FRONTEND_PORT}` and `wss://lk...` to port 7880. WebSocket upgrade headers must be forwarded.

## If something fails
| Symptom | Likely cause |
|---|---|
| Google button missing / "origin not allowed" | the site URL is not in Authorized JavaScript origins |
| Sign-in works but you are signed out after refresh | `COOKIE_SECURE=1` but you are on plain http; use https |
| Video does not connect from phones | UDP 50000-50200 or TCP 7881 blocked; `LIVEKIT_URL` not the public `wss://` address |
| Console: "Refused to connect ... CSP" | `LIVEKIT_PUBLIC_HOST` in `.env` does not match the host in `LIVEKIT_URL` |
| compose stops with "set X" | a required value is missing in `.env` (intended) |
