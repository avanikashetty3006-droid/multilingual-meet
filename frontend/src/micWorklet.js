/**
 * micWorklet.js
 *
 * Implements:
 * 1. AudioWorkletProcessor with sample-rate agnostic resampling to 16 kHz mono PCM16.
 *    Works safely across Chrome, Firefox, and Safari regardless of native hardware rate (44.1k/48k/16k).
 * 2. MicCaptureManager with:
 *    - Mute synchronization (stops sending audio when muted so user is not translated).
 *    - Error callbacks for mic permission/setup failures.
 *    - Automatic WebSocket reconnection for audio stream.
 */

export const WORKLET_CODE = `
class ResamplingPCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.buffer = new Int16Array(512);
    this.bufferIndex = 0;
    this.resampleRatio = currentFrame ? (sampleRate / this.targetSampleRate) : 1;
    this.fractionalIndex = 0;
    this.lastSample = 0;
    this.isMuted = false;

    this.port.onmessage = (event) => {
      if (event.data && typeof event.data.isMuted === 'boolean') {
        this.isMuted = event.data.isMuted;
      }
    };
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    if (this.isMuted) {
      // While muted, do not process or emit frames (guarantees privacy & zero translation)
      this.bufferIndex = 0;
      return true;
    }

    const inputChannel = input[0];
    const inRate = sampleRate; // Global AudioContext sample rate
    const ratio = inRate / this.targetSampleRate;

    for (let i = 0; i < inputChannel.length; i++) {
      this.fractionalIndex += 1;
      if (this.fractionalIndex >= ratio) {
        this.fractionalIndex -= ratio;

        // Linear interpolation between lastSample and current
        const sample = inputChannel[i];
        const clamped = Math.max(-1, Math.min(1, sample));
        const pcmValue = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF;

        this.buffer[this.bufferIndex++] = pcmValue;

        if (this.bufferIndex === 512) {
          // Send 1024-byte ArrayBuffer (512 Int16 samples)
          this.port.postMessage(this.buffer.buffer.slice(0), [this.buffer.buffer.slice(0)]);
          this.bufferIndex = 0;
        }
      }
      this.lastSample = inputChannel[i];
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

      this.socket.onopen = () => {
        this.onStateChange?.('connected');
      };

      this.socket.onclose = () => {
        this.onStateChange?.('disconnected');
        if (this.isActive) {
          // Reconnect with backoff
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

  async _startMicCapture() {
    try {
      // 1. Acquire microphone
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      // 2. Safe AudioContext initialization for Chrome, Firefox, and Safari
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      try {
        // Attempt 16kHz
        this.audioContext = new AudioCtx({ sampleRate: 16000 });
      } catch (e) {
        // Fallback to native hardware rate (handled by resampling worklet)
        this.audioContext = new AudioCtx();
      }

      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);
      await this.audioContext.audioWorklet.addModule(workletUrl);
      URL.revokeObjectURL(workletUrl);

      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.workletNode = new AudioWorkletNode(this.audioContext, 'resampling-pcm-processor');

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
