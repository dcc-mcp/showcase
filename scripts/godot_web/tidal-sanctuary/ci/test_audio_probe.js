'use strict';
// Pure public-API fixtures. These do not run a browser or claim rendered output.
const assert = require('node:assert/strict');
const test = require('node:test');
const install = require('./audio_probe.js');
function fixture() {
  let wall = 0, originalStarts = 0, resumes = 0;
  const events = {}, timers = [];
  class AudioNode {
    constructor(context) { this.context = context; this.out = []; }
    connect(destination, output = 0, input = 0) {
      if (!destination || destination.context !== this.context) throw new Error('InvalidAccessError');
      if (!this.out.some(edge => edge.destination === destination && edge.output === output && edge.input === input)) this.out.push({ destination, output, input });
      return destination;
    }
    disconnect(...args) {
      this.out = this.out.filter(edge => !(args.length === 0 || (typeof args[0] === 'number' ? edge.output === args[0] :
        edge.destination === args[0] && (args.length < 2 || edge.output === args[1]) && (args.length < 3 || edge.input === args[2]))));
    }
    addEventListener(name, callback) { (this.listeners ||= {})[name] = callback; }
  }
  class AudioDestinationNode extends AudioNode {}
  class GainNode extends AudioNode { constructor(context) { super(context); this.gain = { value: 1 }; } }
  class MediaStreamAudioDestinationNode extends AudioNode { constructor(context) { super(context); this.stream = { getAudioTracks: () => [{}] }; } }
  class AnalyserNode extends AudioNode {
    getFloatTimeDomainData(data) {
      const amplitude = (node, seen = new Set()) => {
        if (seen.has(node)) return 0;
        seen.add(node);
        if (node instanceof AudioBufferSourceNode) return node.started && !node.stopped ? node.amplitude : 0;
        let total = 0;
        for (const source of this.context.nodes) if (source.out.some(edge => edge.destination === node)) total += amplitude(source, new Set(seen));
        return total * (node.gain ? node.gain.value : 1);
      };
      data.fill(this.context.state === 'running' ? amplitude(this) : 0);
    }
  }
  class AudioBufferSourceNode extends AudioNode {
    constructor(context) { super(context); this.playbackRate = { value: 1 }; this.detune = { value: 0 }; this.loop = false; this.amplitude = .1; }
    start() { originalStarts++; this.started = true; }
    stop() { this.stopped = true; }
  }
  class UnknownNode extends AudioNode {}
  class Context {
    constructor() { this.currentTime = 0; this.sampleRate = 48000; this.state = 'suspended'; this.nodes = []; this.destination = new AudioDestinationNode(this); }
    create(Type) { const node = new Type(this); this.nodes.push(node); return node; }
    createMediaStreamDestination() { return this.create(MediaStreamAudioDestinationNode); }
    createAnalyser() { return this.create(AnalyserNode); }
    resume() { resumes++; this.state = 'running'; }
  }
  class MediaRecorder {
    static isTypeSupported(type) { return type === 'audio/webm;codecs=opus'; }
    constructor(stream, options) { this.stream = stream; this.mimeType = options.mimeType; this.state = 'inactive'; }
    addEventListener() {}
    start() { this.state = 'recording'; }
  }
  const host = { AudioNode, AudioBufferSourceNode, MediaRecorder,
    performance: { now: () => wall }, navigator: { userActivation: { isActive: false, hasBeenActive: false } },
    setInterval: callback => { timers.push(callback); return timers.length; }, clearInterval() {},
    addEventListener: (name, callback) => { events[name] = callback; } };
  const probe = install(host), ctx = new Context();
  function source(duration = 32, amplitude = .1) {
    const source = ctx.create(AudioBufferSourceNode);
    source.amplitude = amplitude;
    source.buffer = { duration, length: Math.round(duration * 100), sampleRate: 100, numberOfChannels: 2,
      getChannelData: () => new Float32Array(Math.round(duration * 100)).fill(amplitude) };
    return source;
  }
  function advance(ms) { wall += ms; if (ctx.state === 'running') ctx.currentTime += ms / 1000; for (const timer of timers) timer(); }
  return { probe, host, ctx, source, advance, events, AudioNode, GainNode, UnknownNode,
    counters: () => ({ originalStarts, resumes }) };
}

test('mirrors exactly once in the same context and preserves original terminal edge and return', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  assert.equal(master.connect(f.ctx.destination), f.ctx.destination);
  master.connect(f.ctx.destination);
  assert.equal(master.out.length, 3);
  assert(master.out.every(edge => edge.destination.context === f.ctx));
  const terminal = f.probe.snapshot().contexts[0].terminals[0];
  assert.equal(terminal.mirror_count, 1);
  assert.equal(terminal.duplicate_connect_calls, 1);
  assert.equal(f.probe.snapshot().errors.length, 0);
});
test('targeted disconnect removes only its mirrors and reconnect deduplicates', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), other = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination); master.connect(other);
  master.disconnect(f.ctx.destination);
  assert.equal(master.out.length, 1); assert.equal(master.out[0].destination, other);
  master.connect(f.ctx.destination);
  assert.equal(f.probe.snapshot().contexts[0].terminals.filter(item => item.active).length, 1);
  master.disconnect(0);
  assert.equal(master.out.length, 0);
  assert.equal(f.probe.snapshot().contexts[0].terminals.filter(item => item.active).length, 0);
});
test('no-argument disconnect removes original and probe edges', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination); master.disconnect();
  assert.equal(master.out.length, 0);
  assert.equal(f.probe.snapshot().contexts[0].terminals[0].active, false);
});
test('missing and unknown graphs fail closed without fabricating audio', () => {
  const f = fixture();
  assert.throws(() => f.probe.startRecording(), /No unambiguous/);
  f.ctx.create(f.UnknownNode).connect(f.ctx.destination);
  assert.match(f.probe.snapshot().errors[0], /Unknown terminal/);
  assert.throws(() => f.probe.startRecording(), /No unambiguous/);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('original WebAudio exceptions propagate unchanged', () => {
  const f = fixture(), node = f.ctx.create(f.GainNode);
  assert.throws(() => node.connect(null), /InvalidAccessError/);
  assert.equal(f.probe.snapshot().errors.length, 0);
});
test('public source starts have real paths/fingerprints; live post-mute tap becomes quiet', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master);
  f.probe.startRecording();
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
  f.ctx.state = 'running'; source.start(); f.advance(100);
  let snapshot = f.probe.snapshot(), start = snapshot.starts[0];
  assert.equal(start.name, 'music'); assert.equal(start.path_at_start.length, 3);
  assert(start.pcm_peak > 0); assert(snapshot.contexts[0].samples.at(-1).rms > .05);
  master.gain.value = 0; f.advance(100);
  assert.equal(f.probe.snapshot().contexts[0].samples.at(-1).rms, 0);
  assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
  assert.throws(() => f.probe.startRecording(), /already started/);
});
test('recreated looping sources keep PCM identity without observer-created sources', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), first = f.source();
  master.connect(f.ctx.destination); first.connect(master); f.ctx.state = 'running'; first.start();
  f.advance(32000); first.disconnect(); const next = f.source(); next.connect(master); next.start();
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.starts.length, 2);
  assert.equal(snapshot.starts[0].pcm_fingerprint, snapshot.starts[1].pcm_fingerprint);
  assert.equal(snapshot.contexts[0].samples.at(-1).active_music, 1);
  assert.deepEqual(f.counters(), { originalStarts: 2, resumes: 0 });
});
test('duplicate simultaneously live music sources are visible to acceptance', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination); f.ctx.state = 'running';
  for (let index = 0; index < 2; index++) { const source = f.source(); source.connect(master); source.start(); }
  assert.equal(f.probe.snapshot().contexts[0].samples.at(-1).active_music, 2);
});
test('source silence and unknown durations remain diagnostic failures, not fabricated signal', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination); const silent = f.source(.72, 0); silent.connect(master); silent.start();
  assert.equal(f.probe.snapshot().starts[0].pcm_peak, 0);
  const unknown = f.source(3.5); unknown.connect(master); unknown.start();
  assert.match(f.probe.snapshot().errors[0], /Unknown source duration/);
});
test('observer cannot invent a trusted activation or replace user input', () => {
  const f = fixture();
  assert.equal(f.probe.snapshot().gestures.length, 0);
  f.events.pointerdown({ isTrusted: true, clientX: 10, clientY: 20 });
  assert.equal(f.probe.snapshot().gestures[0].trusted, true);
  assert.equal(f.probe.snapshot().user_activation.has_been_active, false);
});

test('active cue ledger follows actual live source and current nonzero destination path', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), cue = f.source(.72);
  master.connect(f.ctx.destination); cue.connect(master); f.ctx.state = 'running'; cue.start(); f.advance(100);
  const id = f.probe.snapshot().starts[0].id;
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).active_cues, [id]);
  master.gain.value = 0; f.advance(100);
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).active_cues, []);
  master.gain.value = 1; f.advance(100);
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).active_cues, [id]);
  cue.disconnect();
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).active_cues, []);
  cue.connect(master); cue.stop(); f.advance(100);
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).active_cues, []);
  assert(Math.abs(f.probe.snapshot().starts[0].stopped_context_time - .3) < 1e-9);
  assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
});


test('voice ledger does not invent a five-millisecond pre-end gap', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master); f.ctx.state = 'running'; source.start();
  f.advance(31998);
  assert.equal(f.probe.snapshot().contexts[0].samples.at(-1).active_music, 1);
  f.advance(2);
  assert.equal(f.probe.snapshot().contexts[0].samples.at(-1).active_music, 0);
});
