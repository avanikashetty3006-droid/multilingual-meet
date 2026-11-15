"""Measure real latency per stage (run on the machine that will host the service):

    python scripts/benchmark.py tests/data/hello_en.wav --runs 5 --targets hi kn --audio
    $env:WHISPER_MODEL="small"; python scripts/benchmark.py tests/data/hello_en.wav   # compare models

Prints a table you can paste into README.md. The call server only switches a listener to AUDIO mode when the
average total stays under 3000 ms, so choose the default model with 'total (audio)' under about 2500 ms.
"""
import argparse
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--targets", nargs="+", default=["hi"])
    ap.add_argument("--audio", action="store_true", help="include TTS")
    a = ap.parse_args()

    import time
    import engines
    from pipeline import Pipeline

    asr, mt, tts, device = engines.load_real_pipeline_parts(preload_voices=tuple(a.targets))
    p = Pipeline(asr, mt, tts, tempfile.mkdtemp(), "http://localhost:8001")
    data = Path(a.wav).read_bytes()
    p.run(data, "en", a.targets, a.audio)  # warm-up (not counted)
    rows = []
    for _ in range(a.runs):
        t0 = time.perf_counter()
        r = p.run(data, "en", a.targets, a.audio)
        r["timings_ms"]["total"] = round((time.perf_counter() - t0) * 1000)
        rows.append(r["timings_ms"])
    print(f"\nwhisper={engines.WHISPER_MODEL} device={device} targets={a.targets} audio={a.audio} runs={a.runs}")
    print("| stage | avg ms | max ms |\n|---|---|---|")
    for k in ("asr", "mt", "tts", "total"):
        v = [r[k] for r in rows]
        print(f"| {k} | {statistics.mean(v):.0f} | {max(v)} |")
    print("text:", r["source_text"])


if __name__ == "__main__":
    main()
