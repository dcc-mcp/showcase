/* CI-only audio-thread observer. Inputs are the browser's actual rendered PCM.
 * Outputs are always zero; this processor cannot start/resume sources or mix
 * substitute audio. No process() call means no new frames, samples or silence.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory;
  else registerProcessor('tidal-audio-meter-v1', factory(AudioWorkletProcessor, () => currentFrame, sampleRate));
})(globalThis, function createTidalAudioMeterProcessor(Base, frameNow, rate) {
  'use strict';
  return class TidalAudioMeterProcessor extends Base {
    constructor(options = {}) {
      super();
      const config = options.processorOptions || {};
      this.tap = config.tapId;
      this.windowFrames = config.windowFrames ?? Math.round(rate / 10);
      this.maxWindows = config.maxWindows ?? 12000;
      this.maxPending = config.maxPendingMessages ?? 256;
      this.sequence = 0;
      this.acknowledged = 0;
      this.windowCount = 0;
      this.gapCount = 0;
      this.segment = 0;
      this.expectedFrame = null;
      this.window = null;
      this.gap = null;
      this.hadInput = false;
      this.failed = false;
      this.port.onmessage = event => this.message(event.data);
      if (typeof this.tap !== 'string' || !this.tap || !Number.isFinite(rate) || rate <= 0 ||
          !Number.isSafeInteger(this.windowFrames) || this.windowFrames < 1 || this.windowFrames > rate ||
          !Number.isSafeInteger(this.maxWindows) || this.maxWindows < 1 || this.maxWindows > 12000 ||
          !Number.isSafeInteger(this.maxPending) || this.maxPending < 1 || this.maxPending > 256) {
        this.fail('Invalid audio-thread meter configuration');
      }
    }
    fail(reason, overflow = false, diagnostic = null) {
      if (!this.failed) {
        this.failed = true;
        this.port.postMessage({ type: 'error', schema: 1, tap_id: this.tap, sample_rate: rate,
          error: reason, overflow, sequence: this.sequence, processed_end_frame: this.expectedFrame, diagnostic });
      }
      return false;
    }
    emit(type, record) {
      if (this.failed) return false;
      if (this.sequence - this.acknowledged >= this.maxPending) return this.fail('Audio-thread pending message overflow', true);
      if ((type === 'window' ? this.windowCount : this.gapCount) >= this.maxWindows) {
        return this.fail('Audio-thread evidence overflow', true);
      }
      if (type === 'window') this.windowCount++; else this.gapCount++;
      this.port.postMessage({ type, schema: 1, tap_id: this.tap, sample_rate: rate,
        sequence: ++this.sequence, ...record });
      return true;
    }
    emitWindow(complete) {
      const value = this.window;
      if (!value) return true;
      this.window = null;
      const samples = value.frames * value.channels;
      const square = value.channel_square_sum.reduce((sum, item) => sum + item, 0);
      const clipped = value.channel_clipped_samples.reduce((sum, item) => sum + item, 0);
      return this.emit('window', { ...value, end_frame: value.start_frame + value.frames, complete,
        samples, channel_samples: Array(value.channels).fill(value.frames), square_sum: square,
        rms: Math.sqrt(square / samples), peak: Math.max(...value.channel_peak),
        clipped_samples: clipped, clipped_fraction: clipped / samples,
        channel_rms: value.channel_square_sum.map(sum => Math.sqrt(sum / value.frames)) });
    }
    emitGap() {
      const value = this.gap;
      if (!value) return true;
      this.gap = null;
      return this.emit('gap', { ...value, frames: value.end_frame - value.start_frame,
        reason: 'no-input', segment_before: this.segment });
    }
    message(message) {
      if (this.failed) return;
      if (!message || typeof message !== 'object') { this.fail('Invalid audio-thread message'); return; }
      if (message.type === 'ack') {
        if (!Number.isSafeInteger(message.sequence) || message.sequence !== this.acknowledged + 1 ||
            message.sequence > this.sequence) this.fail('Invalid audio-thread acknowledgement');
        else this.acknowledged = message.sequence;
      } else if (message.type === 'barrier') {
        if (!Number.isSafeInteger(message.id) || message.id < 1) { this.fail('Invalid audio-thread barrier'); return; }
        // Empty input has real frame coverage but no PCM. Flush only its actual
        // observed interval. A partial PCM window remains partial, never padded.
        if (!this.emitGap()) return;
        this.port.postMessage({ type: 'barrier', schema: 1, tap_id: this.tap, sample_rate: rate,
          id: message.id, sequence: this.sequence, processed_end_frame: this.expectedFrame,
          partial_frames: this.window ? this.window.frames : 0 });
      } else this.fail('Unknown audio-thread message');
    }
    process(inputs, outputs) {
      // The single silent output keeps the observer in the existing live stream
      // graph. Its actual length also measures no-input render quanta exactly.
      for (const output of outputs) for (const channel of output) channel.fill(0);
      if (this.failed) return false;
      const frame = frameNow(), output = outputs[0];
      if (!Number.isSafeInteger(frame) || frame < 0 || !output || output.length !== 1 ||
          !Number.isSafeInteger(output[0].length) || output[0].length < 1 || output[0].length > 16384) {
        return this.fail('Invalid audio-thread render quantum');
      }
      const frames = output[0].length;
      if (this.expectedFrame !== null && frame !== this.expectedFrame) {
        // Failure-only telemetry. Never accept, fill, restart, or relabel a gap.
        return this.fail('Discontinuous audio-thread render frames', false, {
          expected_frame: this.expectedFrame, actual_frame: frame,
          delta_frames: frame - this.expectedFrame, quantum_frames: frames,
          input_channels: Array.isArray(inputs) && Array.isArray(inputs[0]) ? inputs[0].length : null,
          previous_had_input: this.hadInput, segment: this.segment,
          partial_frames: this.window ? this.window.frames : 0,
          pending_no_input_start: this.gap ? this.gap.start_frame : null,
          pending_no_input_end: this.gap ? this.gap.end_frame : null
        });
      }
      if (!Array.isArray(inputs) || inputs.length !== 1 || !Array.isArray(inputs[0])) return this.fail('Missing audio-thread input');
      const channels = inputs[0];
      if (channels.length > 32) return this.fail('Too many audio-thread channels');
      for (let channel = 0; channel < channels.length; channel++) {
        if (!channels[channel] || channels[channel].length !== frames) return this.fail('Missing or unequal audio-thread channels');
      }
      this.expectedFrame = frame + frames;
      if (!channels.length) {
        if (!this.emitWindow(false)) return false;
        if (!this.gap) this.gap = { start_frame: frame, end_frame: frame + frames };
        else this.gap.end_frame = frame + frames;
        this.hadInput = false;
        return true;
      }
      if (!this.emitGap()) return false;
      if (!this.hadInput) { this.segment++; this.hadInput = true; this.segmentChannels = channels.length; }
      if (this.segmentChannels !== channels.length) {
        // A connected silent bus can genuinely render mono before a stereo
        // source begins. Retain exactly those channel samples, finish their
        // partial window and begin a new segment. Do not up/downmix or pad.
        if (!this.emitWindow(false)) return false;
        this.segment++;
        this.segmentChannels = channels.length;
      }
      // Validate the supplied block before accumulating any of it.
      for (const channel of channels) for (const value of channel) {
        if (!Number.isFinite(value)) return this.fail('Nonfinite actual audio-thread PCM');
      }
      let offset = 0;
      while (offset < frames) {
        if (!this.window) this.window = { start_frame: frame + offset, frames: 0, channels: channels.length,
          segment: this.segment, channel_square_sum: Array(channels.length).fill(0),
          channel_peak: Array(channels.length).fill(0), channel_clipped_samples: Array(channels.length).fill(0) };
        const take = Math.min(frames - offset, this.windowFrames - this.window.frames);
        for (let channel = 0; channel < channels.length; channel++) {
          for (let index = offset; index < offset + take; index++) {
            const value = channels[channel][index], magnitude = Math.abs(value);
            this.window.channel_square_sum[channel] += value * value;
            this.window.channel_peak[channel] = Math.max(this.window.channel_peak[channel], magnitude);
            if (magnitude >= .999) this.window.channel_clipped_samples[channel]++;
          }
        }
        this.window.frames += take;
        offset += take;
        if (this.window.frames === this.windowFrames && !this.emitWindow(true)) return false;
      }
      return true;
    }
  };
});
