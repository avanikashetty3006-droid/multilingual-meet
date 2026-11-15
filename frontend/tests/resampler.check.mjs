// Run:  node frontend/tests/resampler.check.mjs
// Feeds a sine wave through the worklet processor the way the browser does (128-sample blocks).
import assert from 'node:assert/strict';
import { WORKLET_CODE } from '../src/micWorklet.js';

function makeProcessor(rate) {
  let Registered;
  const messages = [];
  class AudioWorkletProcessor {
    constructor() {
      this.port = { onmessage: null, postMessage: (data) => messages.push(new Int16Array(data)) };
    }
  }
  const registerProcessor = (_name, cls) => { Registered = cls; };
  new Function('AudioWorkletProcessor', 'registerProcessor', 'sampleRate', WORKLET_CODE)(
    AudioWorkletProcessor, registerProcessor, rate);
  return { proc: new Registered(), messages };
}

function run(rate, freq, seconds, muted = false) {
  const { proc, messages } = makeProcessor(rate);
  if (muted) proc.port.onmessage({ data: { isMuted: true } });
  const total = Math.floor(rate * seconds);
  for (let start = 0; start < total; start += 128) {
    const block = new Float32Array(128);
    for (let i = 0; i < 128; i++) block[i] = 0.5 * Math.sin((2 * Math.PI * freq * (start + i)) / rate);
    proc.process([[block]]);
  }
  const out = [];
  messages.forEach((m) => out.push(...m));
  return { messages, out };
}

function frequencyByZeroCrossings(samples, sampleRate) {
  let crossings = 0;
  for (let i = 1; i < samples.length; i++) if (samples[i - 1] < 0 && samples[i] >= 0) crossings++;
  return (crossings * sampleRate) / samples.length;
}

function rms(samples) {
  return Math.sqrt(samples.reduce((s, v) => s + v * v, 0) / samples.length);
}

for (const rate of [48000, 44100, 16000]) {
  const { messages, out } = run(rate, 440, 2);
  assert.ok(messages.length >= 60, `${rate}: expected about 62 frames, got ${messages.length}`);
  messages.forEach((m) => assert.equal(m.byteLength, 1024, 'every message must be 512 samples = 1024 bytes'));
  const f = frequencyByZeroCrossings(out, 16000);
  assert.ok(Math.abs(f - 440) < 6, `${rate}: output frequency ${f.toFixed(1)} Hz should be about 440`);
  const peak = Math.max(...out.map(Math.abs));
  assert.ok(peak > 0.45 * 32767 && peak < 0.55 * 32767, `${rate}: peak ${peak} should be about 16384`);
  // no clicks: biggest jump between neighbouring samples is small for a 440 Hz tone at 16 kHz
  let maxJump = 0;
  for (let i = 1; i < out.length; i++) maxJump = Math.max(maxJump, Math.abs(out[i] - out[i - 1]));
  assert.ok(maxJump < 0.2 * 32767, `${rate}: max jump ${maxJump} suggests a click at a block border`);
  console.log(`ok ${rate} Hz -> 16 kHz: ${messages.length} frames, ${f.toFixed(1)} Hz, peak ${peak}`);
}

// muted: nothing is produced
assert.equal(run(48000, 440, 1, true).messages.length, 0);
console.log('ok muted: no frames');

// aliasing: a 10 kHz tone (above the 8 kHz limit) is attenuated compared with keeping every 3rd sample
{
  const rate = 48000, freq = 10000;
  const { out } = run(rate, freq, 1);
  const naive = [];
  for (let i = 0; i < rate; i += 3) naive.push(0.5 * Math.sin((2 * Math.PI * freq * i) / rate) * 32767);
  console.log(`ok aliasing: 10 kHz tone RMS ${rms(out.slice(2000)).toFixed(0)} (averaging) vs ${rms(naive).toFixed(0)} (keep every 3rd sample)`);
  assert.ok(rms(out.slice(2000)) < rms(naive), 'averaging must attenuate out-of-band tones');
}

