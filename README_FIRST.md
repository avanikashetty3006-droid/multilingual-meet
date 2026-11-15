# VAAK update pack (Role 1 + Role 2): read this first

This zip contains **finished code**, not prompts. It adds the backend that the new frontend was missing (sign-in,
meetings, history, friends, invites, live presence), fixes the frontend/deploy problems found in the review, and
tells you exactly what to run. Based on repo commit `df8fb12`.

## 0. The 5-minute version

1. `git pull` in your repo, then copy this zip's contents over it (section 2).
2. Delete 3 dead files (section 3).
3. Create a Google OAuth client ID (section 4).
4. Run LiveKit + call-server + frontend (section 5) and tick the checklist (section 6).
5. Run the tests (section 7), commit, push (section 8).

## 1. What changed, by role

### Role 2 (call-server), you
| File | What it is |
|---|---|
| `call-server/a10/` (new package) | The whole A10 API: Google sign-in + signed cookie sessions, meetings (ID `abc-defg-hij`), history, friends, invites, `WS /ws/user` presence, rate limits, SQLite or Postgres. |
| `call-server/main.py` (replaced) | Mounts A10 at `/api/v1` and `/ws/user`; refuses `/ws/room` and `/ws/audio` for ended meetings (close code 4410); `meeting_ended` broadcast; marks people as left; CORS no longer "wildcard + cookies". **A10 only turns on when `SESSION_SECRET` is set**, so your old mock/load-test flow still works without it. Exact changes: `patches/call-server_main.py.diff`. |
| `call-server/requirements.txt` | adds `google-auth`, `requests`, `psycopg[binary]` |
| `call-server/Dockerfile` (new) | production image (build context = repo root) |
| `call-server/tests/test_a10.py`, `asgi_client.py`, `__init__.py` | 22 new tests |
| `call-server/plot_latency.py` | now also makes **latency vs users**: `python plot_latency.py 2=run2.csv 5=run5.csv 10=run10.csv 20=run20.csv` |
| `shared/CONTRACT_A10_ADDENDUM.md` | The implemented API. Paste it into `shared/CONTRACT.md` as section A10. |

### Role 1 (frontend)
| File | Fix |
|---|---|
| `frontend/src/views/ConferenceView.jsx` | no more `http://localhost:8000` (works only on your PC); URLs derived from the page address; "host ended the meeting" handling |
| `frontend/src/useRoomSocket.js` | same URL fix + `meeting_ended` / close-code 4410 stops reconnecting |
| `frontend/src/utils/wsUrl.js` + `frontend/tests/wsUrl.check.mjs` (new) | the URL builder and its test |
| `frontend/src/views/LobbyView.jsx` | uses the server's `participant_id` (so history and presence match the call) |
| `frontend/Dockerfile` | `VITE_*` are **build args** now (before, the Google client ID never reached the built site, so sign-in would be broken in Docker) |
| `frontend/nginx.conf.template` (replaces `nginx.conf`) | CSP without `unsafe-inline` scripts, LiveKit host from env, `/api`, `/ws`, `/audio` proxies, cache headers |
| `frontend/.env.example` | corrected |

### Both / deployment
`docker-compose.yml` (required secrets, no default passwords, LiveKit pinned and not `--dev`, only needed ports open, optional Caddy HTTPS),
`Caddyfile`, `.env.example`, `.github/workflows/ci.yml` (adds the call-server tests and the wsUrl check), `scripts/run-local.ps1`, `DEPLOY.md`.

## 2. Where to put the files

Unzip so that `C:\Users\AKSHAYA\Desktop\vaak-update\README_FIRST.md` exists (Windows "Extract All" may add one extra `vaak-update` folder level: use the inner one), then in PowerShell:

```powershell
cd C:\Users\AKSHAYA\Desktop\multilingual-meet
git checkout main
git pull
git checkout -b role2-a10-and-deploy
Copy-Item -Recurse -Force C:\Users\AKSHAYA\Desktop\vaak-update\* .
git status
```
The folder layout inside the zip is the repo layout, so everything lands in the right place. `README_FIRST.md`
and `patches/` can stay or be deleted. **If a teammate changed `ConferenceView.jsx`, `LobbyView.jsx`,
`useRoomSocket.js` or `main.py` after `df8fb12`, do not overwrite blindly:** apply `patches/*.diff` instead
(`git apply --3way patches\frontend_src_views_LobbyView.jsx.diff`, one file at a time).

## 3. Delete dead files (Role 1)
```powershell
git rm frontend/src/GoogleAuth.jsx frontend/src/JoinScreen.jsx frontend/nginx.conf
```
`GoogleAuth.jsx` and `JoinScreen.jsx` are unused leftovers of the old simulated login. `nginx.conf` is replaced by the template.

## 4. Google sign-in setup (one time, 5 minutes)
1. https://console.cloud.google.com -> create/select a project -> **APIs & Services -> OAuth consent screen** (External, app name VAAK, your email; add your team's Gmail addresses as *test users* while it is in Testing mode).
2. **Credentials -> Create credentials -> OAuth client ID -> Web application**.
3. **Authorized JavaScript origins**: `http://localhost:5173` (local) and later `https://meet.yourdomain.com`. (No redirect URI needed for the Google button.)
4. Copy the **Client ID** (ends with `.apps.googleusercontent.com`). It is not a secret, but the same value goes in two places: the frontend and the call-server (it checks the token was issued for *your* app).

## 5. Run it locally on Windows (4 terminals)

**Terminal 1: LiveKit** (from the Releases zip `livekit_<ver>_windows_amd64.zip`, not the source zip)
```powershell
cd C:\path\to\livekit
.\livekit-server.exe --dev
```
**Terminal 2: call-server**
```powershell
cd C:\Users\AKSHAYA\Desktop\multilingual-meet\call-server
pip install -r requirements.txt
cd ..
notepad scripts\run-local.ps1      # paste your Client ID on the GOOGLE_CLIENT_ID line, save
.\scripts\run-local.ps1            # may need: Set-ExecutionPolicy -Scope Process Bypass
```
You should see `Uvicorn running on http://0.0.0.0:8000`. If you see "A10 API ... DISABLED" the `SESSION_SECRET` line did not run.

**Terminal 3 (optional, real translation):** Role 3 and Role 4 services on 8001/8002, then set `$env:MOCK="0"` in the script.
Without them keep `MOCK=1`: sign-in, meetings, friends and video all work; translation is mock.

**Terminal 4: frontend**
```powershell
cd C:\Users\AKSHAYA\Desktop\multilingual-meet\frontend
copy .env.example .env.local
notepad .env.local                 # set VITE_GOOGLE_CLIENT_ID, keep VITE_API_MOCK=0
npm install
npm run dev
```
Open **http://localhost:5173** (use `localhost`, not your LAN IP, so camera/mic and the cookie work without HTTPS).
For two users on one PC use a normal window and an incognito window with two different Google accounts.

## 6. Checklist: does it work?
- [ ] (If sign-in shows `BAD_ORIGIN`/403: `ALLOWED_ORIGINS` is missing, it is set in `run-local.ps1`.)
- [ ] http://localhost:8000/v1/health returns JSON; http://localhost:8000/api/v1/me returns `401` JSON (that is correct: not signed in).
- [ ] Sign in with Google -> animation -> Home. Refresh the page: still signed in (cookie). DevTools -> Application -> Cookies: `vaak_session` is **HttpOnly** and there is nothing in localStorage.
- [ ] New meeting -> ID looks like `abc-defg-hij` -> link copies -> lobby -> Join -> camera tiles appear, no error.
- [ ] Second account (incognito): Friends -> search the first account's exact email -> send request. First account: Friends shows the request -> accept. Both lists show each other with a green dot.
- [ ] First account joins a meeting: the other's friend list flips to **in meeting** within a second. Leave: back to **online**. Close the tab: **offline**.
- [ ] "Invite to meeting" on a friend: the friend receives an `invite` event (visible in DevTools -> Network -> WS -> `/ws/user`). **The UI does not show invite pop-ups yet** (see section 10).
- [ ] Host clicks **End meeting for all**: everyone gets the alert and returns Home; History shows the duration; "Rejoin" is gone; opening the old link says it ended.
- [ ] Settings: change display name/language/theme, refresh, they persist. "Delete my account" removes everything and signs out.

## 7. Tests (run before every push)
```powershell
cd C:\Users\AKSHAYA\Desktop\multilingual-meet\call-server
python -m pytest tests -q                  # expect: 43 passed (21 old + 22 new); on your PC fastapi/httpx exist so nothing is skipped
cd ..\frontend
node tests\netStats.check.mjs
node tests\queue_and_captions.check.mjs
node tests\resampler.check.mjs
node tests\wsUrl.check.mjs
npm test
npm run build                              # must finish without errors
```

## 8. Commit and push
```powershell
cd C:\Users\AKSHAYA\Desktop\multilingual-meet
git add -A
git status                                  # CHECK: no .env, no vaak.db, no metrics.csv in the list
git commit -m "A10 backend, production fixes, docker/nginx/compose"
git push -u origin role2-a10-and-deploy
```
Open a Pull Request into `main` on GitHub and let CI go green before merging. Add `vaak.db*` and `.env` to `.gitignore` if they are not there.

## 9. Deploy for real users
See `DEPLOY.md` (server, DNS, `.env`, `docker compose --profile tls up -d --build`, post-deploy checklist, rollback).

## 10. Honest status: what I tested and what I could not
**Tested here (passing):**
- All 22 new backend tests: sign-in rules (unverified email, bad token, tampered/expired cookie), cookie flags, profile validation, meeting
  create/join/end/idle-auto-end, history paging, friends (mutual, crossing requests, cancel, remove), friends-only presence over real WebSocket
  frames, invites live and queued, rate limits, cross-site Origin blocking, spoof-proof client IP, account deletion removes all rows, bridge failure rolls back.
  I also broke two rules on purpose (presence leak, host check) and confirmed the tests catch it.
- Your 21 existing call-server tests still pass; the new `plot_latency.py` scaling mode ran on sample CSVs; JS/JSX syntax checks; `wsUrl` unit check; YAML validity of compose and CI.

**NOT tested (I cannot run these here, so please do, and tell me what breaks):**
1. `main.py` itself (FastAPI is not installable in my sandbox): the mount, the 4410 refusal, the bridge. The A10 package it mounts is tested; the 40 lines in `main.py` are small but unrun.
2. **Real Google tokens** (I used a stub verifier). The code path is the standard `google.oauth2.id_token.verify_oauth2_token`.
3. **PostgreSQL** (tests use SQLite; SQL is written to be portable, including the `?`->`%s` conversion, but it has not met a real Postgres).
4. `npm run build`, Docker builds, nginx envsubst/CSP in a real browser (watch DevTools -> Console for "Refused to ..." CSP errors on first load), LiveKit in compose, Caddy.
5. Browser behaviour of the new socket code (4410 handling, `meeting_ended` alert) and a real two-device call.

**Known limits (decide consciously):**
- `/ws/room` and `/ws/audio` do not check the login cookie: the unguessable meeting ID acts as the secret (like a Meet link). Anyone with the link can open the sockets without signing in; LiveKit media still needs the token from the signed-in join.
- Sessions are stateless cookies (14 days). Logout clears the cookie in that browser; a copied cookie stays valid until expiry. Deleting the account invalidates it.
- Rate limiting is per process in memory: fine for one server container, not for several replicas.
- The UI does not yet display `invite` events from `/ws/user` (Role 1 task: a toast with a Join button; event shape is in `shared/CONTRACT_A10_ADDENDUM.md`).
- `speech-service/` and `speaker-service/` need their own Dockerfiles from Roles 3 and 4 before `docker compose build` works.
- The first-run animation, privacy and terms pages: you need real Privacy/Terms text before real public users (Google also requires them for production OAuth consent).

## 11. Still open for the team (not in this zip)
Role 3: real ASR/MT/TTS pipeline. Role 4: real Silero VAD and a Dockerfile. Role 2 (you): acceptance runs with 2/5/10/20 bots, save each `metrics.csv`, make the latency-vs-users chart, write the report. Role 1: invite toast, real-call check of the stats panel/mic in Chrome and Firefox.
