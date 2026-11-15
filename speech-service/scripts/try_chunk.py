"""Send one WAV to a running speech-service and print the answer (works the same in PowerShell, cmd and bash).

    python scripts/try_chunk.py tests/data/hello_en.wav --src en --targets hi kn --audio
"""
import argparse
import json

import httpx

ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("--url", default="http://localhost:8001")
ap.add_argument("--src", default="en")
ap.add_argument("--targets", nargs="+", default=["hi", "kn"])
ap.add_argument("--audio", action="store_true")
a = ap.parse_args()

with open(a.wav, "rb") as f:
    r = httpx.post(f"{a.url}/v1/process-chunk", timeout=60,
                   files={"audio": ("chunk.wav", f.read(), "audio/wav")},
                   data={"room_id": "r1", "participant_id": "p1", "chunk_id": "c1", "src_lang": a.src,
                         "tgt_langs": json.dumps(a.targets), "want_audio": "true" if a.audio else "false"})
print(r.status_code)
print(json.dumps(r.json(), indent=2, ensure_ascii=False))
