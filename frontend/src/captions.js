/**
 * Latest caption of each DISTINCT talker, newest first, at most `max` talkers.
 * `captions` is newest-first (App prepends), so the first time we see a talker is their latest line.
 * Without this, one talker's own earlier lines could fill both "Also Speaking" slots.
 */
export function latestPerTalker(captions, max = 2) {
  const seen = new Set();
  const out = [];
  for (const cap of captions) {
    const who = cap.from ?? cap.from_name;
    if (seen.has(who)) continue;
    seen.add(who);
    out.push(cap);
    if (out.length === max) break;
  }
  return out;
}
