// Run:  node frontend/tests/netStats.check.mjs
import assert from 'node:assert/strict';
import { createStatsTracker } from '../src/netStats.js';

const report = (items) => new Map(items.map((i) => [i.id, i]));

function sample({ rtt = 0.05, bytesIn = 0, bytesOut = 0, lost = 0, recv = 0, sent = 0, jitter = 0.01, bwe }) {
  return report([
    { id: 'T', type: 'transport', selectedCandidatePairId: 'CP' },
    { id: 'CP', type: 'candidate-pair', currentRoundTripTime: rtt, availableOutgoingBitrate: bwe },
    { id: 'IN', type: 'inbound-rtp', bytesReceived: bytesIn, packetsReceived: recv, packetsLost: lost, jitter },
    { id: 'OUT', type: 'outbound-rtp', bytesSent: bytesOut, packetsSent: sent },
  ]);
}

// first sample: not enough data yet
{
  const t = createStatsTracker();
  assert.equal(t([sample({})], 0), null);
  console.log('ok first call returns null');
}

// loss and bitrate are measured per window (not since the start of the call)
{
  const t = createStatsTracker();
  t([sample({ recv: 10000, lost: 500, bytesIn: 5e6 })], 0);                       // old history: 4.8% loss
  const clean = t([sample({ recv: 10100, lost: 500, bytesIn: 5e6 + 250000 })], 2000); // this window: 0 lost
  assert.equal(clean.packet_loss_pct, 0, 'old loss must not leak into the new window');
  assert.equal(clean.bitrate_kbps, 1000, '250000 bytes in 2 s = 1000 kbps measured');
  const lossy = t([sample({ recv: 10190, lost: 510, bytesIn: 5e6 + 400000 })], 4000); // 10 lost of 100
  assert.equal(lossy.packet_loss_pct, 10);
  console.log('ok per-window loss and bitrate', clean, lossy);
}

// outgoing loss (reported by the other side) counts too
{
  const t = createStatsTracker();
  const out = (sent, lost) => report([
    { id: 'T', type: 'transport', selectedCandidatePairId: 'CP' },
    { id: 'CP', type: 'candidate-pair', currentRoundTripTime: 0.05 },
    { id: 'OUT', type: 'outbound-rtp', bytesSent: sent * 1000, packetsSent: sent },
    { id: 'RIN', type: 'remote-inbound-rtp', packetsLost: lost, roundTripTime: 0.05 },
  ]);
  t([out(1000, 0)], 0);
  const r = t([out(1100, 8)], 2000);                          // 8 lost of 100 sent
  assert.equal(r.packet_loss_pct, 8);
  console.log('ok outgoing loss', r);
}

// several streams are summed, a counter reset counts as 0
{
  const t = createStatsTracker();
  const two = (a, b) => report([
    { id: 'T', type: 'transport', selectedCandidatePairId: 'CP' },
    { id: 'CP', type: 'candidate-pair', currentRoundTripTime: 0.04 },
    { id: 'A', type: 'inbound-rtp', bytesReceived: a, packetsReceived: 0, packetsLost: 0 },
    { id: 'V', type: 'inbound-rtp', bytesReceived: b, packetsReceived: 0, packetsLost: 0 },
  ]);
  t([two(1000, 2000)], 0);
  const r = t([two(1000 + 50000, 2000 + 200000)], 1000);      // 250000 bytes in 1 s = 2000 kbps
  assert.equal(r.bitrate_kbps, 2000);
  const reset = t([two(0, 0)], 2000);                         // counters restarted
  assert.equal(reset.bitrate_kbps, 0);
  console.log('ok streams summed, reset handled');
}

// the bandwidth estimate wins over measured traffic when the browser provides it
{
  const t = createStatsTracker();
  t([sample({ bwe: 2500000 })], 0);
  const r = t([sample({ bwe: 2500000, bytesIn: 1000 })], 2000);
  assert.equal(r.bitrate_kbps, 2500);
  console.log('ok availableOutgoingBitrate used', r);
}

// no round-trip time => null (do not guess); window too short => null
{
  const t = createStatsTracker();
  const noRtt = () => report([{ id: 'IN', type: 'inbound-rtp', bytesReceived: 1, packetsReceived: 1, packetsLost: 0 }]);
  t([noRtt()], 0);
  assert.equal(t([noRtt()], 2000), null);
  const t2 = createStatsTracker();
  t2([sample({})], 0);
  assert.equal(t2([sample({})], 100), null);
  assert.ok(t2([sample({})], 2000), 'a later call still works after a too-short one');
  console.log('ok null when RTT missing or window too short');
}

// rtt, jitter units
{
  const t = createStatsTracker();
  t([sample({ rtt: 0.12, jitter: 0.03 })], 0);
  const r = t([sample({ rtt: 0.12, jitter: 0.03 })], 2000);
  assert.equal(r.rtt_ms, 120);
  assert.equal(r.jitter_ms, 30);
  console.log('ok units', r);
}

