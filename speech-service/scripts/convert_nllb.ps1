# One-time: convert NLLB-200 distilled 600M to a CTranslate2 int8 folder (about 600 MB). Run from speech-service\
#   .\scripts\convert_nllb.ps1
# Needs the real requirements installed (torch + transformers + ctranslate2). Takes a few minutes and ~3 GB of downloads.
$ErrorActionPreference = "Stop"
$out = Join-Path $PSScriptRoot "..\models\nllb-600m-ct2"
if (Test-Path $out) { Write-Host "Already converted: $out"; exit 0 }
ct2-transformers-converter --model facebook/nllb-200-distilled-600M --output_dir $out --quantization int8
Write-Host "Done. Model folder: $out"
