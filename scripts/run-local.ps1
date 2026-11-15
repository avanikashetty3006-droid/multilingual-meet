# Run the VAAK call-server locally on Windows (no Docker). From the repo root:  .\scripts\run-local.ps1
# Fill in GOOGLE_CLIENT_ID below (same value as VITE_GOOGLE_CLIENT_ID in frontend\.env.local).
$ErrorActionPreference = "Stop"
$env:GOOGLE_CLIENT_ID = "PASTE-YOUR-CLIENT-ID.apps.googleusercontent.com"
$env:SESSION_SECRET   = -join ((1..48) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })  # new each run => you sign in again
$env:ALLOWED_ORIGINS  = "http://localhost:5173"   # the Vite dev server (it rewrites the Host header, so allow it explicitly)
$env:COOKIE_SECURE    = "0"                      # local http only! never in production
$env:DATABASE_URL     = "sqlite:///vaak.db"      # file created inside call-server\
$env:LIVEKIT_URL      = "ws://localhost:7880"
$env:LIVEKIT_API_KEY  = "devkey"
$env:LIVEKIT_API_SECRET = "secret"
$env:MOCK             = "1"                      # 0 once speech-service and speaker-service run
Set-Location "$PSScriptRoot\..\call-server"
python -m uvicorn main:app --host 0.0.0.0 --port 8000
