// Run:  node frontend/tests/queue_and_captions.check.mjs
import assert from 'node:assert/strict';
import { latestPerTalker } from '../src/captions.js';

// ---- fake browser Audio: we fire the events ourselves ----
const made = [];
globalThis.Audio = class {
  constructor(url) { this.url = url; this.paused = false; made.push(this); }
  play() { return this.playResult ?? Promise.resolve(); }
  pause() { this.paused = true; }
};
const { AudioQueue } = await import('../src/audioQueue.js');

function make() {
  made.length = 0;
  const log = [];
  const q = new AudioQueue({ onDuckStart: () => log.push('duck'), onDuckEnd: () => log.push('unduck') });
  return { q, log };
}
const tick = () => new Promise((r) => setTimeout(r, 0));

// 1. three clips: ducks once, unducks once at the very end, plays strictly one at a time
{
  const { q, log } = make();
  q.enqueue('a'); q.enqueue('b'); q.enqueue('c');
  assert.equal(made.length, 1, 'only the first clip starts');
  assert.deepEqual(log, ['duck']);
  made[0].onended(); assert.equal(made.length, 2); assert.deepEqual(log, ['duck'], 'no unduck between clips');
  made[1].onended(); assert.equal(made.length, 3);
  made[2].onended();
  assert.deepEqual(log, ['duck', 'unduck']);
  assert.equal(q.isPlaying, false);
  console.log('ok duck once / unduck once, one clip at a time');
}

// 2. onended AND onerror for the same clip must not start the next clip twice
{
  const { q } = make();
  q.enqueue('a'); q.enqueue('b'); q.enqueue('c');
  made[0].onended(); made[0].onerror('x');       // double fire
  assert.equal(made.length, 2, 'second clip started exactly once');
  assert.equal(q.currentAudio, made[1]);
  console.log('ok cleanup runs once');
}

// 3. play() rejected (autoplay blocked) moves on and eventually unducks
{
  const { q, log } = make();
  const origPlay = globalThis.Audio.prototype.play;
  globalThis.Audio.prototype.play = function () { return Promise.reject(new Error('blocked')); };
  q.enqueue('a');
  await tick();
  globalThis.Audio.prototype.play = origPlay;
  assert.equal(q.isPlaying, false);
  assert.deepEqual(log, ['duck', 'unduck']);
  console.log('ok blocked autoplay recovers');
}

// 4. clear() mid-playback: unducks once, stale events from the old clip are ignored
{
  const { q, log } = make();
  q.enqueue('a'); q.enqueue('b');
  const first = made[0];
  q.clear();
  assert.deepEqual(log, ['duck', 'unduck']);
  assert.equal(first.paused, true);
  first.onended?.();                              // already detached, nothing may happen
  q.clear();                                      // clear twice: no second unduck
  assert.equal(made.length, 1);
  assert.deepEqual(log, ['duck', 'unduck']);
  q.enqueue('c');                                 // usable again afterwards
  assert.equal(made.length, 2);
  console.log('ok clear() mid-playback');
}

// 5. latestPerTalker: newest-first input, one line per talker, max 2 talkers
{
  const caps = [
    { from: 'A', text: 'a2' }, { from: 'A', text: 'a1' }, { from: 'B', text: 'b1' }, { from: 'C', text: 'c1' },
  ];
  const out = latestPerTalker(caps);
  assert.deepEqual(out.map((c) => c.text), ['a2', 'b1']);
  assert.deepEqual(latestPerTalker([]), []);
  assert.deepEqual(latestPerTalker([{ from: 'A', text: 'x' }, { from: 'A', text: 'y' }]).map((c) => c.text), ['x']);
  console.log('ok latestPerTalker');
}

// 6. VideoGrid page clamp (same formula as in VideoGrid.jsx)
{
  const per = 6;
  const pageFor = (stored, n) => { const total = Math.max(1, Math.ceil(n / per)); return Math.min(stored, total - 1); };
  assert.equal(pageFor(3, 20), 3);
  assert.equal(pageFor(3, 7), 1, 'people left: clamp to the last page');
  assert.equal(pageFor(3, 0), 0);
  console.log('ok page clamp');
}
