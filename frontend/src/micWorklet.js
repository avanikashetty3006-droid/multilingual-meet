// AudioWorkletProcessor for 16 kHz Mono PCM16 mic streaming
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = new Int16Array(512);
    this.bufferIndex = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0];
    for (let i = 0; i < channelData.length; i++) {
      // Float32 to Int16 PCM conversion
      let s = Math.max(-1, Math.min(1, channelData[i]));
      this.buffer[this.bufferIndex++] = s < 0 ? s * 0x8000 : s * 0x7FFF;

      if (this.bufferIndex >= 512) {
        this.port.postMessage(this.buffer.buffer.slice(0), [this.buffer.buffer.slice(0)]);
        this.buffer = new Int16Array(512);
        this.bufferIndex = 0;
      }
    }
    return true;
  }
}

registerProcessor('mic-processor', MicProcessor);
