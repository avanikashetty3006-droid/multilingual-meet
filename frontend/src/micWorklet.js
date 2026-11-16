/**
 * micWorklet.js  (replacement for frontend/src/micWorklet.js)
 *
 * 1. AudioWorkletProcessor that turns the microphone into 16 kHz mono PCM16, 512 samples (1024 bytes) per message.
 *    - If the AudioContext already runs at 16 kHz (Chrome) it is a plain pass-through.
 *    - Otherwise it down-samples by AVERAGING all input samples that fall into each output sample
 *      (a simple low-pass: far less aliasing than "keep every Nth sample").
 *    - State is carried between 128-sample blocks, so there are no clicks at block borders.
 * 2. MicCaptureManager:
 *    - mute sync (no frames are produced while muted, so a muted user is never translated),
 *    - error callback for microphone problems,
 *    - automatic WebSocket reconnection.
 */

export const WORKLET_CODE = `
class ResamplingPCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;      // input samples per output sample (3 for 48 kHz, 1 for 16 kHz)
    this.out = new Int16Array(512);
    this.outIndex = 0;
    this.acc = 0;                         // running sum of the current averaging window
    this.count = 0;                       // samples in the current window
    this.phase = 0;                       // how much of the window is filled (in input samples)
    this.isMuted = false;

    this.port.onmessage = (event) => {
      if (event.data && typeof event.data.isMuted === 'boolean') {
        this.isMuted = event.data.isMuted;
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    if (this.isMuted) {
      // Muted: produce nothing and forget any half-built frame.
      this.outIndex = 0;
      this.acc = 0;
      this.count = 0;
      this.phase = 0;
      return true;
    }

    const channel = input[0];
    for (let i = 0; i < channel.length; i++) {
      this.acc += channel[i];
      this.count += 1;
      this.phase += 1;

      if (this.phase >= this.ratio) {
        this.phase -= this.ratio;
        const v = Math.max(-1, Math.min(1, this.acc / this.count));
        this.out[this.outIndex++] = v < 0 ? v * 0x8000 : v * 0x7fff;
        this.acc = 0;
        this.count = 0;

        if (this.outIndex === 512) {
          const copy = this.out.buffer.slice(0);   // one copy, and that same copy is transferred
          this.port.postMessage(copy, [copy]);
          this.outIndex = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('resampling-pcm-processor', ResamplingPCMProcessor);
`;

export class MicCaptureManager {
  constructor(wsUrl, options = {}) {
    this.wsUrl = wsUrl;
    this.onError = options.onError || null;
    this.onStateChange = options.onStateChange || null;
    this.socket = null;
    this.audioContext = null;
    this.mediaStream = null;
    this.workletNode = null;
    this.isMuted = false;
    this.isActive = false;
    this.reconnectTimer = null;
  }

  setMuted(muted) {
    this.isMuted = Boolean(muted);
    if (this.workletNode) {
      this.workletNode.port.postMessage({ isMuted: this.isMuted });
    }
  }

  async start() {
    this.isActive = true;
    this._connectSocket();
    await this._startMicCapture();
  }

  _connectSocket() {
    if (!this.isActive) return;
    try {
      this.socket = new WebSocket(this.wsUrl);
      this.socket.binaryType = 'arraybuffer';
      this.socket.onopen = () => this.onStateChange?.('connected');
      this.socket.onclose = () => {
        this.onStateChange?.('disconnected');
        if (this.isActive) {
          this.reconnectTimer = setTimeout(() => this._connectSocket(), 2000);
        }
      };
      this.socket.onerror = (err) => {
        console.warn('Audio WebSocket error:', err);
        this.socket?.close();
      };
    } catch (err) {
      console.warn('Failed to initialize audio WebSocket:', err);
    }
  }

  /**
   * Create the AudioContext and connect the microphone to it.
   * Chrome can run the context at 16 kHz (best quality: the browser resamples for us).
   * Firefox/Safari may refuse that, and Firefox throws when the MediaStream is connected to a
   * context with a different sample rate. So: try 16 kHz first, and if creating the context OR
   * connecting the stream fails, close it and retry at the default rate (our worklet resamples).
   */
  async _createContextAndSource() {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;

    try {
      const ctx = new AudioCtx({ sampleRate: 16000 });
      try {
        const source = ctx.createMediaStreamSource(this.mediaStream);
        return { ctx, source };
      } catch (e) {
        await ctx.close().catch(() => {});
        throw e;
      }
    } catch (e) {
      const ctx = new AudioCtx();                    // native rate, resampled in the worklet
      const source = ctx.createMediaStreamSource(this.mediaStream);
      return { ctx, source };
    }
  }

  async _startMicCapture() {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      const { ctx, source } = await this._createContextAndSource();
      this.audioContext = ctx;

      if (ctx.state === 'suspended') {
        await ctx.resume();
      }

      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);
      await ctx.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      this.workletNode = new AudioWorkletNode(ctx, 'resampling-pcm-processor');
      this.workletNode.port.postMessage({ isMuted: this.isMuted });   // apply a mute that happened before start

      this.workletNode.port.onmessage = (event) => {
        const pcmBuffer = event.data;
        if (!this.isMuted && this.socket && this.socket.readyState === WebSocket.OPEN) {
          if (pcmBuffer.byteLength === 1024) {
            this.socket.send(pcmBuffer);
          }
        }
      };

      source.connect(this.workletNode);
    } catch (err) {
      const msg = err.name === 'NotAllowedError'
        ? 'Microphone access was denied. Please allow microphone permissions for translation.'
        : `Microphone initialization error: ${err.message || err}`;
      console.error(msg, err);
      this.onError?.(msg);
    }
  }

  stop() {
    this.isActive = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
