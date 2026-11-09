/**
 * micWorklet.js
 *
 * Implements:
 * 1. An AudioWorkletProcessor inline string definition for real-time PCM extraction.
 * 2. A MicCaptureManager helper class that:
 *    - Acquires user microphone stream.
 *    - Downsamples/resamples to 16 kHz mono PCM16.
 *    - Emits frames of exactly 512 samples (1024 bytes = 32ms) to WS /ws/audio/{room_id}/{participant_id}.
 */

export const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Float32Array(512);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];
    for (let i = 0; i < channelData.length; i++) {
      this.buffer[this.bufferIndex++] = channelData[i];
      if (this.bufferIndex === 512) {
        // Convert Float32 [-1.0, 1.0] to Int16 PCM [-32768, 32767]
        const pcm16 = new Int16Array(512);
        for (let j = 0; j < 512; j++) {
          const s = Math.max(-1, Math.min(1, this.buffer[j]));
          pcm16[j] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
        this.bufferIndex = 0;
      }
    }
    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
`;

export class MicCaptureManager {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.socket = null;
    this.audioContext = null;
    this.mediaStream = null;
    this.workletNode = null;
  }

  async start() {
    // Connect WebSocket
    this.socket = new WebSocket(this.wsUrl);
    this.socket.binaryType = 'arraybuffer';

    await new Promise((resolve, reject) => {
      this.socket.onopen = resolve;
      this.socket.onerror = reject;
    });

    // Acquire mic at 16000Hz mono if possible
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
      },
      video: false,
    });

    this.audioContext = new AudioContext({ sampleRate: 16000 });
    const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
    const workletUrl = URL.createObjectURL(blob);
    await this.audioContext.audioWorklet.addModule(workletUrl);

    const source = this.audioContext.createMediaStreamSource(this.mediaStream);
    this.workletNode = new AudioWorkletNode(this.audioContext, 'pcm-processor');

    this.workletNode.port.onmessage = (event) => {
      const pcmBuffer = event.data;
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        // Enforce 1024 bytes frame size
        if (pcmBuffer.byteLength === 1024) {
          this.socket.send(pcmBuffer);
        }
      }
    };

    source.connect(this.workletNode);
  }

  stop() {
    if (this.workletNode) {
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
