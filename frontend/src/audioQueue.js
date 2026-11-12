/**
 * Audio Queue to play translated audio one at a time in order without overlap
 */
class AudioQueue {
  constructor() {
    this.queue = [];
    this.isPlaying = false;
    this.currentAudio = null;
  }

  enqueue(url) {
    if (!url) return;
    this.queue.push(url);
    if (!this.isPlaying) {
      this.playNext();
    }
  }

  playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      this.currentAudio = null;
      return;
    }

    this.isPlaying = true;
    const url = this.queue.shift();
    this.currentAudio = new Audio(url);

    this.currentAudio.onended = () => {
      this.playNext();
    };

    this.currentAudio.onerror = (e) => {
      console.warn("Audio playback failed for", url, e);
      this.playNext();
    };

    this.currentAudio.play().catch((err) => {
      console.warn("Autoplay error:", err);
      this.playNext();
    });
  }

  clear() {
    if (this.currentAudio) {
      this.currentAudio.pause();
      this.currentAudio = null;
    }
    this.queue = [];
    this.isPlaying = false;
  }
}

export const audioQueue = new AudioQueue();
