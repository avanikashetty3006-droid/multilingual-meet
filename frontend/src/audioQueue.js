/**
 * audioQueue.js
 *
 * Manages an ordered queue of translated audio URLs.
 * Ensures:
 * - Clips play one at a time, in order, with zero overlap.
 * - Optional ducking callback to duck LiveKit call audio while translated speech is playing.
 */

export class AudioQueue {
  constructor(options = {}) {
    this.queue = [];
    this.isPlaying = false;
    this.currentAudio = null;
    this.onDuckStart = options.onDuckStart || null;
    this.onDuckEnd = options.onDuckEnd || null;
  }

  enqueue(audioUrl) {
    if (!audioUrl) return;
    this.queue.push(audioUrl);
    this._playNext();
  }

  _playNext() {
    if (this.isPlaying || this.queue.length === 0) {
      return;
    }

    const nextUrl = this.queue.shift();
    this.isPlaying = true;
    this.onDuckStart?.();

    const audio = new Audio(nextUrl);
    this.currentAudio = audio;

    const cleanup = () => {
      this.isPlaying = false;
      this.currentAudio = null;
      this.onDuckEnd?.();
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
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.isPlaying = false;
    this.onDuckEnd?.();
  }
}
