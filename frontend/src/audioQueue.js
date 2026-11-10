/**
 * audioQueue.js
 *
 * Manages an ordered queue of translated audio URLs.
 * Ensures:
 * - Clips play one at a time, in order, with zero overlap.
 * - Ducking callbacks fire ONCE per burst of clips: onDuckStart when the first clip starts,
 *   onDuckEnd only when the queue is empty again (no volume jumping between back-to-back clips).
 * - A clip's cleanup runs at most once (onended + onerror + play() rejection can all fire).
 */

export class AudioQueue {
  constructor(options = {}) {
    this.queue = [];
    this.isPlaying = false;
    this.currentAudio = null;
    this.ducked = false;
    this.onDuckStart = options.onDuckStart || null;
    this.onDuckEnd = options.onDuckEnd || null;
  }

  enqueue(audioUrl) {
    if (!audioUrl) return;
    this.queue.push(audioUrl);
    this._playNext();
  }

  _duckStart() {
    if (this.ducked) return;
    this.ducked = true;
    this.onDuckStart?.();
  }

  _duckEnd() {
    if (!this.ducked) return;
    this.ducked = false;
    this.onDuckEnd?.();
  }

  _playNext() {
    if (this.isPlaying) return;
    if (this.queue.length === 0) {
      this._duckEnd(); // nothing left to say: bring the call audio back up
      return;
    }

    const nextUrl = this.queue.shift();
    this.isPlaying = true;
    this._duckStart();

    const audio = new Audio(nextUrl);
    this.currentAudio = audio;

    let finished = false;
    const cleanup = () => {
      if (finished) return;                       // run once only
      finished = true;
      if (this.currentAudio !== audio) return;    // clear() already took over: stale event
      this.isPlaying = false;
      this.currentAudio = null;
      this._playNext();
    };

    audio.onended = cleanup;
    audio.onerror = (e) => {
      console.warn('Audio playback failed for clip:', nextUrl, e);
      cleanup();
    };

    audio.play().catch((err) => {
      console.warn('Autoplay prevented or playback error:', err);
      cleanup();
    });
  }

  clear() {
    this.queue = [];
    if (this.currentAudio) {
      this.currentAudio.onended = null;
      this.currentAudio.onerror = null;
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.isPlaying = false;
    this._duckEnd();
  }
}
