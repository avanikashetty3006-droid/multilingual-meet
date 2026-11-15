/**
 * netStats.js  (NEW file: frontend/src/netStats.js)
 *
 * Turns WebRTC getStats() reports into the 4 numbers the call server wants, measured over the
 * WINDOW since the previous call (not since the start of the call):
 *   { rtt_ms, packet_loss_pct, bitrate_kbps, jitter_ms }
 *
 * Usage:
 *   const tracker = createStatsTracker();
 *   const stats = tracker([publisherReport, subscriberReport]);   // null until it has two samples
 *
 * Returns null when there is not enough data (first call, no round-trip time yet, window too short).
 * The caller must then SKIP sending net_stats instead of inventing numbers.
 *
 * Bitrate: if the browser reports the bandwidth estimate (candidate-pair availableOutgoingBitrate,
 * Chrome) that is used, because it measures how much the link CAN carry. Otherwise the measured
 * traffic (bytes in + out) is used, which is only a weak proxy: a quiet call with the camera off
 * can look "slow" on a perfect network.
 */

function entriesOf(report) {
  const out = [];
  if (report && typeof report.forEach === 'function') {
    report.forEach((value) => out.push(value));
  }
  return out;
}

export function createStatsTracker(minWindowMs = 500) {
  let prev = null; // { t, counters: Map(key -> {bytes, packets, lost}) }

  return function compute(reports, nowMs = Date.now()) {
    const counters = new Map();
    let rttSeconds = null;
    let availableBitrate = null;
    let jitterSeconds = 0;

    reports.forEach((report, source) => {
      const all = entriesOf(report);
      const byId = new Map(all.map((r) => [r.id, r]));

      // --- round-trip time: from the SELECTED candidate pair of each connection ---
      const transport = all.find((r) => r.type === 'transport' && r.selectedCandidatePairId);
      let pair = transport ? byId.get(transport.selectedCandidatePairId) : null;
      if (!pair) {
        pair = all.find((r) => r.type === 'candidate-pair' && (r.selected || (r.nominated && r.state === 'succeeded')));
      }
      if (pair) {
        if (typeof pair.currentRoundTripTime === 'number' && pair.currentRoundTripTime > 0) {
          rttSeconds = Math.max(rttSeconds ?? 0, pair.currentRoundTripTime);
        }
        if (typeof pair.availableOutgoingBitrate === 'number' && pair.availableOutgoingBitrate > 0) {
          availableBitrate = Math.min(availableBitrate ?? Infinity, pair.availableOutgoingBitrate);
        }
      }

      for (const r of all) {
        const key = `${source}:${r.id}`;
        if (r.type === 'inbound-rtp') {
          counters.set(key, {
            bytes: r.bytesReceived || 0,
            recv: r.packetsReceived || 0,
            lostIn: r.packetsLost || 0,
            sent: 0,
            lostOut: 0,
          });
          if (typeof r.jitter === 'number') jitterSeconds = Math.max(jitterSeconds, r.jitter);
        } else if (r.type === 'outbound-rtp') {
          counters.set(key, { bytes: r.bytesSent || 0, recv: 0, lostIn: 0, sent: r.packetsSent || 0, lostOut: 0 });
        } else if (r.type === 'remote-inbound-rtp') {
          // what the other side says about OUR outgoing stream
          counters.set(key, { bytes: 0, recv: 0, lostIn: 0, sent: 0, lostOut: r.packetsLost || 0 });
          if (typeof r.roundTripTime === 'number' && r.roundTripTime > 0 && rttSeconds === null) {
            rttSeconds = r.roundTripTime;
          }
          if (typeof r.jitter === 'number') jitterSeconds = Math.max(jitterSeconds, r.jitter);
        }
      }
    });

    const before = prev;
    prev = { t: nowMs, counters };
    if (!before) return null;                       // need two samples to measure a window
    const dtMs = nowMs - before.t;
    if (dtMs < minWindowMs) {
      prev = before;                                // keep the older sample, try again later
      return null;
    }
    if (rttSeconds === null) return null;           // cannot judge the link without an RTT

    let dBytes = 0;
    let dRecv = 0;
    let dLostIn = 0;
    let dSent = 0;
    let dLostOut = 0;
    const grow = (a, b) => Math.max(0, a - b);      // a counter reset (negative) counts as 0
    counters.forEach((now, key) => {
      const old = before.counters.get(key);
      if (!old) return;                             // new stream: no baseline yet
      dBytes += grow(now.bytes, old.bytes);
      dRecv += grow(now.recv, old.recv);
      dLostIn += grow(now.lostIn, old.lostIn);
      dSent += grow(now.sent, old.sent);
      dLostOut += grow(now.lostOut, old.lostOut);
    });

    // incoming loss = lost / (received + lost); outgoing loss = lost (reported by the other side) / sent
    const lossIn = dRecv + dLostIn > 0 ? (dLostIn / (dRecv + dLostIn)) * 100 : 0;
    const lossOut = dSent > 0 ? (dLostOut / dSent) * 100 : 0;
    const lossPct = Math.max(lossIn, lossOut);
    const measuredKbps = (dBytes * 8) / (dtMs / 1000) / 1000;
    const bitrateKbps = availableBitrate !== null ? availableBitrate / 1000 : measuredKbps;

    return {
      rtt_ms: Math.round(rttSeconds * 1000),
      packet_loss_pct: Math.round(Math.min(100, lossPct) * 10) / 10,
      bitrate_kbps: Math.round(bitrateKbps),
      jitter_ms: Math.round(jitterSeconds * 1000),
    };
  };
}
