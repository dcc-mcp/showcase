'use strict';
// Pure processor tests pass explicit PCM blocks. They are not browser receipts.
const assert = require('node:assert/strict');
const test = require('node:test');
const createProcessor = require('./audio_meter_worklet.js');
function fixture(options = {}) {
  let frame = options.startFrame || 0;
  const messages = [];
  class Base { constructor() { this.port = { postMessage: value => messages.push(structuredClone(value)) }; } }
  const Processor = createProcessor(Base, () => frame, options.rate || 48000);
  const processor = new Processor({ processorOptions: { tapId: 'test:pcm', windowFrames: 4, ...options } });
  function block(channels, length = channels[0] ? channels[0].length : 4) {
    const output = new Float32Array(length).fill(.75);
    const result = processor.process([channels], [[output]]);
    assert(output.every(value => value === 0), 'observer output is always silence, including failures');
    frame += length;
    return result;
  }
  function message(value) { processor.port.onmessage({ data: value }); }
  return { processor, block, message, messages, jump: value => { frame = value; },
    ack: () => { for (let sequence = processor.acknowledged + 1; sequence <= processor.sequence; sequence++) message({ type: 'ack', sequence }); },
    records: () => messages.filter(item => item.type === 'window' || item.type === 'gap') };
}
const pcm = values => Float32Array.from(values);
const near = (actual, expected) => assert(Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);

test('aggregates every provided real channel sample with exact absolute frame bounds', () => {
  const f = fixture({ startFrame: 1024 });
  const channels = [pcm([.25, -.5, .75, -1]), pcm([.125, -.25, .375, -.5])];
  assert.equal(f.block(channels), true);
  const result = f.records()[0], squares = channels.map(values => values.reduce((sum, value) => sum + value * value, 0));
  assert.equal(result.sequence, 1); assert.equal(result.start_frame, 1024); assert.equal(result.end_frame, 1028);
  assert.equal(result.sample_rate, 48000); assert.equal(result.frames, 4); assert.equal(result.channels, 2);
  assert.equal(result.samples, 8); assert.deepEqual(result.channel_samples, [4, 4]);
  assert.deepEqual(result.channel_square_sum, squares); near(result.square_sum, squares[0] + squares[1]);
  near(result.rms, Math.sqrt((squares[0] + squares[1]) / 8)); assert.equal(result.peak, 1);
  assert.deepEqual(result.channel_peak, [1, .5]); assert.deepEqual(result.channel_clipped_samples, [1, 0]);
  assert.equal(result.clipped_samples, 1); assert.equal(result.clipped_fraction, 1 / 8); assert.equal(result.complete, true);
  assert.deepEqual(Array.from(channels[0]), [.25, -.5, .75, -1], 'observation never rewrites actual input PCM');
});
test('windows split real render quanta without repeating or dropping supplied samples', () => {
  const f = fixture({ windowFrames: 5 });
  f.block([pcm([1, 2, 3, 4])]); f.block([pcm([5, 6, 7, 8])]); f.block([pcm([9, 10, 11, 12])]);
  const windows = f.records();
  assert.deepEqual(windows.map(item => [item.start_frame, item.end_frame, item.square_sum]), [[0, 5, 55], [5, 10, 330]]);
  f.message({ type: 'barrier', id: 1 });
  assert.equal(f.messages.at(-1).processed_end_frame, 12); assert.equal(f.messages.at(-1).partial_frames, 2);
  assert.equal(f.records().length, 2, 'barrier neither pads nor invents a complete PCM window');
});
test('zero-valued supplied PCM is measurable silence with real channel/sample counts', () => {
  const f = fixture(); f.block([new Float32Array(4), new Float32Array(4)]);
  const value = f.records()[0];
  assert.equal(value.rms, 0); assert.equal(value.peak, 0); assert.equal(value.samples, 8);
  assert.equal(value.clipped_fraction, 0); assert.deepEqual(value.channel_samples, [4, 4]);
});
test('positive and negative clipping is counted in each actually supplied channel', () => {
  const f = fixture(); f.block([pcm([1, -1, 1.2, -1.2]), pcm([.5, -.5, 0, 0])]);
  const value = f.records()[0];
  assert.equal(value.clipped_samples, 4); assert.equal(value.clipped_fraction, .5);
  assert.deepEqual(value.channel_clipped_samples, [4, 0]); assert(value.peak > 1.19);
});
test('pre-source no-input intervals retain real frame gaps without manufactured zero PCM', () => {
  const f = fixture(); f.block([], 128); f.block([], 256);
  assert.deepEqual(f.records(), []);
  f.message({ type: 'barrier', id: 1 });
  const gap = f.records()[0];
  assert.equal(gap.type, 'gap'); assert.equal(gap.start_frame, 0); assert.equal(gap.end_frame, 384);
  assert.equal(gap.frames, 384); assert.equal(gap.segment_before, 0); assert.equal(gap.reason, 'no-input');
  assert.equal(gap.rms, undefined); assert.equal(gap.samples, undefined);
  f.ack(); f.block([], 4); f.block([pcm([.1, .2, .3, .4])]);
  assert.deepEqual(f.records().map(item => [item.type, item.sequence, item.start_frame, item.end_frame]),
    [['gap', 1, 0, 384], ['gap', 2, 384, 388], ['window', 3, 388, 392]]);
  assert.equal(f.records().at(-1).segment, 1);
});
test('cue endings retain actual partial PCM then a gap and a new segment', () => {
  const f = fixture({ windowFrames: 6 });
  f.block([pcm([.1, .2, .3, .4])]); f.block([], 4); f.block([pcm([.5, .6, .7, .8])]);
  f.block([pcm([.9, 1, 1.1, 1.2])]);
  const records = f.records();
  assert.deepEqual(records.map(item => [item.type, item.sequence, item.start_frame, item.end_frame]),
    [['window', 1, 0, 4], ['gap', 2, 4, 8], ['window', 3, 8, 14]]);
  assert.equal(records[0].complete, false); assert.equal(records[0].samples, 4);
  assert.equal(records[0].segment, 1); assert.equal(records[2].segment, 2);
});
test('missing, unequal or sparse channels fail closed instead of substituting PCM', () => {
  for (const channels of [[pcm([1, 2, 3, 4]), undefined], [pcm([1, 2, 3, 4]), pcm([1])], Array(2)]) {
    const f = fixture(); assert.equal(f.block(channels), false);
    assert.match(f.messages.at(-1).error, /Missing or unequal/); assert.deepEqual(f.records(), []);
    assert.equal(f.block([pcm([1, 2, 3, 4])]), false); assert.deepEqual(f.records(), []);
  }
});
test('genuine mono-to-stereo changes retain exact partial windows and new segments without conversion', () => {
  const f = fixture({ windowFrames: 6 });
  f.block([new Float32Array(4)]);
  assert.equal(f.block([pcm([.1, .2, .3, .4]), pcm([.5, .6, .7, .8])]), true);
  f.block([pcm([.2, .2, .2, .2]), pcm([.4, .4, .4, .4])]);
  const records = f.records();
  assert.deepEqual(records.map(item => [item.type, item.start_frame, item.end_frame, item.channels, item.samples, item.segment]),
    [['window', 0, 4, 1, 4, 1], ['window', 4, 10, 2, 12, 2]]);
  assert.equal(records[0].complete, false); assert.equal(records[0].rms, 0);
  assert.equal(records[1].complete, true); assert(records[1].rms > 0);
  assert.equal(f.messages.filter(item => item.type === 'gap' || item.type === 'error').length, 0);
  const boundary = fixture(); boundary.block([new Float32Array(4)]);
  boundary.block([new Float32Array(4), new Float32Array(4)]);
  assert.deepEqual(boundary.records().map(item => [item.frames, item.channels, item.segment]), [[4, 1, 1], [4, 2, 2]]);
});
test('dropped, repeated and out-of-order actual render blocks permanently fail', () => {
  for (const nextFrame of [0, 3, 5, 128]) {
    const f = fixture(); f.block([new Float32Array(4)]); f.jump(nextFrame);
    assert.equal(f.block([new Float32Array(4)]), false); assert.match(f.messages.at(-1).error, /Discontinuous/);
    assert.equal(f.records().length, 1);
  }
});
test('nonfinite PCM is rejected before any part of the invalid block is counted', () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    const f = fixture(); assert.equal(f.block([pcm([0, value, 0, 0])]), false);
    assert.match(f.messages.at(-1).error, /Nonfinite/); assert.deepEqual(f.records(), []);
  }
});
test('suspension creates no windows or silent placeholders without process callbacks', () => {
  const f = fixture();
  f.message({ type: 'barrier', id: 1 });
  assert.equal(f.messages.at(-1).processed_end_frame, null); assert.deepEqual(f.records(), []);
  f.block([pcm([.1, .2, .3, .4])]);
  const before = structuredClone(f.records());
  // No process invocation during an arbitrary wall-time suspension. A control
  // message cannot advance the audio clock or manufacture a sample.
  f.message({ type: 'barrier', id: 2 }); f.message({ type: 'barrier', id: 3 });
  assert.deepEqual(f.records(), before); assert.equal(f.messages.at(-1).processed_end_frame, 4);
  f.ack(); f.block([pcm([.5, .6, .7, .8])]); assert.equal(f.records().at(-1).start_frame, 4);
});
test('bounded pending transport fails on overflow and never overwrites earlier evidence', () => {
  const f = fixture({ maxPendingMessages: 2 });
  f.block([new Float32Array(4)]); f.block([new Float32Array(4)]);
  assert.equal(f.block([new Float32Array(4)]), false); assert.equal(f.records().length, 2);
  assert.equal(f.messages.at(-1).overflow, true); assert.match(f.messages.at(-1).error, /pending message overflow/);
});
test('acknowledgements free transport but never remove bounded evidence accounting', () => {
  const f = fixture({ maxPendingMessages: 1, maxWindows: 2 });
  f.block([new Float32Array(4)]); f.ack(); f.block([new Float32Array(4)]); f.ack();
  assert.equal(f.block([new Float32Array(4)]), false); assert.match(f.messages.at(-1).error, /evidence overflow/);
  assert.equal(f.records().length, 2);
});
test('invalid acknowledgements cannot conceal dropped or duplicate receipt sequences', () => {
  for (const sequence of [0, 2, 1.5]) {
    const f = fixture(); f.block([new Float32Array(4)]); f.message({ type: 'ack', sequence });
    assert.match(f.messages.at(-1).error, /acknowledgement/); assert.equal(f.processor.failed, true);
  }
});

test('forward and backward discontinuities preserve failure-only quantum telemetry without filling PCM', () => {
  for (const actual of [128, 0]) {
    const f = fixture(); f.block([pcm([.1, .2, .3, .4])]); f.ack(); f.jump(actual);
    assert.equal(f.block([], 128), false);
    const error = f.messages.at(-1);
    assert.equal(error.processed_end_frame, 4);
    assert.deepEqual(error.diagnostic, { expected_frame: 4, actual_frame: actual,
      delta_frames: actual - 4, quantum_frames: 128, input_channels: 0,
      previous_had_input: true, segment: 1, partial_frames: 0,
      pending_no_input_start: null, pending_no_input_end: null });
    assert.equal(f.records().length, 1);
    assert.equal(f.block([new Float32Array(128)]), false);
    assert.equal(f.records().length, 1, 'failed tap cannot resume or invent missing samples');
  }
});
