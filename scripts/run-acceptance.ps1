# Role 2 acceptance runs: bots with 2, 5, 10 and 20 users, one CSV per run, then the latency-vs-users chart.
# BEFORE running, start these in other terminals (see START_HERE.md section C):
#   speaker-service (MOCK=0, 8002), speech-service (8001), call-server (MOCK=0, 8000, SPEAKER_SERVICE_URL=http://127.0.0.1:8002)
# Run from the repo root:  .\scripts\run-acceptance.ps1 -Wav speaker-service\tests\fixtures\speech_sample.wav
param(
  [string]$Wav = "speaker-service\tests\fixtures\speech_sample.wav",
  [int[]]$Users = @(2, 5, 10, 20),
  [int]$Duration = 60,
  [string]$Server = "ws://127.0.0.1:8000"
)
$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$metrics = Join-Path $root "call-server\metrics.csv"
$out = Join-Path $root "results"
New-Item -ItemType Directory -Force $out | Out-Null
$pairs = @()

foreach ($n in $Users) {
  $before = if (Test-Path $metrics) { @(Get-Content $metrics).Count } else { 0 }
  Write-Host "=== $n bots for $Duration s ==="
  Push-Location "$root\load-test"
  python bots.py --num-bots $n --room "accept-$n" --server $Server --wav (Join-Path $root $Wav) `
    --speak-pattern overlap --overlap-count ([Math]::Min(3, $n)) --network good --duration $Duration
  Pop-Location
  Start-Sleep -Seconds 3
  $all = @(Get-Content $metrics)
  $csv = Join-Path $out "run$n.csv"
  if ($before -eq 0) { $all | Set-Content $csv } else { @($all[0]) + $all[$before..($all.Count - 1)] | Set-Content $csv }
  Write-Host "saved $csv ($($all.Count - $before) new rows)"
  $pairs += "$n=$csv"
}

Push-Location "$root\call-server"
python plot_latency.py @pairs
Pop-Location
Write-Host "Chart: $out\latency_vs_users.png"
