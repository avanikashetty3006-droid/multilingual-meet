# Load Testing & Simulation Bots

Simulates multiple concurrent video call participants streaming mic audio (WAV file or synthetic speech) and sending WebRTC network stats to test:
- **Speaking token passing and overlap cap**: tests that only 1 participant is active token holder and simultaneous talkers are capped at `max_overlap` (2).
- **Per-listener network adaptation**: tests that throttled listeners flip to `subtitle` mode while fast listeners stay on `audio`.
- **Concurrency scaling**: tests 5, 10, and 20-user runs.

---

## Usage

### 1. Test 5 Users with Mixed Network (50% good, 50% poor)
```bash
python bots.py --num-bots 5 --network mixed --speak-pattern round-robin --duration 30
```
- Half the bots report low RTT/0% loss (audio mode).
- Half report high RTT/5% packet loss (switch to subtitle mode).

### 2. Test 10 Users with Overlap Speaking Cap
```bash
python bots.py --num-bots 10 --speak-pattern overlap --duration 20
```
- First 3 bots speak simultaneously.
- Verifies that bot 1 gets the token (`lane="main"`), bot 2 gets `lane="overlap"`, and excessive overlap is capped/dropped.

### 3. Test 20 Users Concurrency Benchmark
```bash
python bots.py --num-bots 20 --languages en,hi,kn,ta,te --speak-pattern random --duration 60
```
- Measures system latency and throughput under high participant counts.

### 4. Streaming Custom Audio from a WAV File
```bash
python bots.py --num-bots 4 --wav path/to/sample.wav --speak-pattern round-robin
```
Streams real 16 kHz mono speech segments into the Call Server chunker.
