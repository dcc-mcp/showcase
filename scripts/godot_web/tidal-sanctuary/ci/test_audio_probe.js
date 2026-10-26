'use strict';
// Pure public-API fixtures. These do not run a browser or claim rendered output.
const assert = require('node:assert/strict');
const test = require('node:test');
const install = require('./audio_probe.js');
function fixture(options = {}) {
  let wall = 0, originalStarts = 0, resumes = 0;
  const events = {}, timers = [], constructorOptions = [], moduleUrls = [], revokedUrls = [];
  class AudioNode {
    constructor(context) { this.context = context; this.out = []; }
    connect(destination, output = 0, input = 0) {
      if (!destination || (!(destination instanceof AudioParam) && destination.context !== this.context)) throw new Error('InvalidAccessError');
      if (!this.out.some(edge => edge.destination === destination && edge.output === output && edge.input === input)) this.out.push({ destination, output, input });
      return destination instanceof AudioParam ? undefined : destination;
    }
    disconnect(...args) {
      this.out = this.out.filter(edge => !(args.length === 0 || (typeof args[0] === 'number' ? edge.output === args[0] :
        edge.destination === args[0] && (args.length < 2 || edge.output === args[1]) && (args.length < 3 || edge.input === args[2]))));
    }
    addEventListener(name, callback) { (this.listeners ||= {})[name] = callback; }
  }
  class AudioDestinationNode extends AudioNode {}
  class AudioParam {
    constructor(value) { this._value = value; this.calls = []; }
    get value() { return this._value; }
    set value(value) { if (!Number.isFinite(value)) throw new TypeError('Nonfinite parameter'); this._value = value; }
    setValueAtTime(value, time) { this.calls.push(['setValueAtTime', value, time]); return this; }
    linearRampToValueAtTime(value, time) { this.calls.push(['linearRampToValueAtTime', value, time]); return this; }
    exponentialRampToValueAtTime(value, time) { this.calls.push(['exponentialRampToValueAtTime', value, time]); return this; }
    setTargetAtTime(value, time, constant) { this.calls.push(['setTargetAtTime', value, time, constant]); return this; }
    setValueCurveAtTime(values, time, duration) { this.calls.push(['setValueCurveAtTime', values, time, duration]); return this; }
    cancelScheduledValues(time) { this.calls.push(['cancelScheduledValues', time]); return this; }
    cancelAndHoldAtTime(time) { this.calls.push(['cancelAndHoldAtTime', time]); return this; }
  }
  class GainNode extends AudioNode { constructor(context) { super(context); this.gain = new AudioParam(1); } }
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
      if (this.context.state === 'running') this.lastAmplitude = amplitude(this);
      data.fill(this.lastAmplitude || 0); // Suspension freezes the actual last analyser window.
    }
  }
  class AudioBufferSourceNode extends AudioNode {
    constructor(context) { super(context); this.playbackRate = new AudioParam(1); this.detune = new AudioParam(0); this._loop = false; this._loopStart = 0; this._loopEnd = 0; this.amplitude = .1; }
    get loop() { return this._loop; }
    set loop(value) { this._loop = Boolean(value); }
    get loopStart() { return this._loopStart; }
    set loopStart(value) { if (!Number.isFinite(value)) throw new TypeError('Nonfinite loop start'); this._loopStart = value; }
    get loopEnd() { return this._loopEnd; }
    set loopEnd(value) { if (!Number.isFinite(value)) throw new TypeError('Nonfinite loop end'); this._loopEnd = value; }
    start() { originalStarts++; this.started = true; }
    stop() { this.stopped = true; }
  }
  class UnknownNode extends AudioNode {}
  class AudioWorkletNode extends AudioNode {
    constructor(context, name, options) {
      super(context); context.nodes.push(this); this.processorName = name; this.options = options;
      this.port = { sent: [], onmessage: null, postMessage(message) { this.sent.push(message); } };
    }
    deliver(message) { this.port.onmessage({ data: message }); }
  }
  class Context {
    constructor(options) {
      if (options && options.fixtureError) throw options.fixtureError;
      constructorOptions.push(options);
      this.currentTime = 0; this.sampleRate = options && options.sampleRate || 48000;
      this.state = 'suspended'; this.nodes = []; this.destination = new AudioDestinationNode(this);
      this.audioWorklet = { addModule(url) {
        moduleUrls.push(url);
        if (options && options.moduleError) return Promise.reject(options.moduleError);
        // Synchronously settled deterministic module fixture. No renderer and
        // no fabricated PCM. Deferred installation is tested separately below.
        return { then(callback) { callback(); return Promise.resolve(); } };
      } };
    }
    create(Type) { const node = new Type(this); this.nodes.push(node); return node; }
    createMediaStreamDestination() { return this.create(MediaStreamAudioDestinationNode); }
    createAnalyser() { return this.create(AnalyserNode); }
    createGain() { return this.create(GainNode); }
    resume() { resumes++; this.state = 'running'; }
  }
  class MediaRecorder {
    static isTypeSupported(type) { return type === 'audio/webm;codecs=opus'; }
    constructor(stream, options) { this.stream = stream; this.mimeType = options.mimeType; this.state = 'inactive'; }
    addEventListener() {}
    start() { this.state = 'recording'; }
  }
  const host = { AudioContext: Context, AudioNode, AudioParam, AudioBufferSourceNode, GainNode, AudioWorkletNode, MediaRecorder,
    __tidalAudioWorkletSource: '// Deterministic module-loading fixture; no audio execution', Blob,
    URL: { createObjectURL: () => 'blob:audio-meter-fixture/' + (moduleUrls.length + 1), revokeObjectURL: url => revokedUrls.push(url) },
    performance: { now: () => wall }, navigator: { userActivation: { isActive: false, hasBeenActive: false } },
    setInterval: callback => { timers.push(callback); return timers.length; }, clearInterval() {},
    setTimeout, clearTimeout,
    addEventListener: (name, callback) => { events[name] = callback; } };
  if (options.alias) host.webkitAudioContext = Context;
  if (options.prefixedOnly) { host.webkitAudioContext = Context; delete host.AudioContext; }
  const originalResume = Context.prototype.resume;
  const probe = install(host), ctx = new (host.AudioContext || host.webkitAudioContext)();
  function source(duration = 32, amplitude = .1) {
    const source = ctx.create(AudioBufferSourceNode);
    source.amplitude = amplitude;
    source.buffer = { duration, length: Math.round(duration * 100), sampleRate: 100, numberOfChannels: 2,
      getChannelData: () => new Float32Array(Math.round(duration * 100)).fill(amplitude) };
    return source;
  }
  function advance(ms) { wall += ms; if (ctx.state === 'running') ctx.currentTime += ms / 1000; for (const timer of timers) timer(); }
  return { probe, host, ctx, source, advance, events, AudioNode, GainNode, UnknownNode,
    Context, originalResume, constructorOptions, moduleUrls, revokedUrls, AudioWorkletNode,
    counters: () => ({ originalStarts, resumes }) };
}

test('construction alone is counted without creating nodes, meter evidence or activation', () => {
  const f = fixture();
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.contexts.length, 1);
  assert.equal(snapshot.contexts[0].state, 'suspended');
  assert.deepEqual(snapshot.contexts[0].terminals, []);
  assert.deepEqual(snapshot.contexts[0].samples, []);
  assert.equal(f.ctx.nodes.length, 0);
  assert.equal(f.ctx.resume, f.originalResume);
  assert.equal(f.host.AudioContext.prototype, f.Context.prototype);
  assert(f.ctx instanceof f.host.AudioContext);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
  assert.equal(snapshot.user_activation.has_been_active, false);
});
test('an unused second context fails the exactly-one-context recording contract', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination);
  const unused = new f.host.AudioContext();
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.contexts.length, 2);
  assert.deepEqual(snapshot.contexts[1].terminals, []);
  assert.deepEqual(snapshot.contexts[1].samples, []);
  assert.equal(unused.nodes.length, 0);
  assert.throws(() => f.probe.startRecording(), /No unambiguous/);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('an unused first context cannot disappear when a later context becomes audible', () => {
  const f = fixture(), second = new f.host.AudioContext();
  const master = second.create(f.GainNode);
  master.connect(second.destination);
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.contexts.length, 2);
  assert.deepEqual(snapshot.contexts[0].terminals, []);
  assert.equal(snapshot.contexts[1].terminals.length, 1);
  assert.throws(() => f.probe.startRecording(), /No unambiguous/);
});
test('prefixed constructor and shared aliases count every context exactly once', () => {
  const f = fixture({ alias: true });
  assert.equal(f.host.AudioContext, f.host.webkitAudioContext);
  const second = new f.host.webkitAudioContext();
  second.create(f.GainNode).connect(second.destination);
  assert.equal(f.probe.snapshot().contexts.length, 2);
  const prefixed = fixture({ prefixedOnly: true });
  assert.equal(prefixed.probe.snapshot().contexts.length, 1);
  assert.equal(prefixed.ctx.nodes.length, 0);
});
test('constructor observation preserves options, subclassing and native exceptions', () => {
  const f = fixture(), options = { sampleRate: 44100 };
  class DerivedContext extends f.host.AudioContext {}
  const second = new DerivedContext(options);
  assert.equal(Object.getPrototypeOf(second), DerivedContext.prototype);
  assert(second instanceof f.Context);
  assert.equal(second.sampleRate, 44100);
  assert.equal(f.constructorOptions.at(-1), options);
  const error = new Error('Native constructor rejected options');
  assert.throws(() => new f.host.AudioContext({ fixtureError: error }), actual => actual === error);
  assert.throws(() => f.host.AudioContext(), TypeError);
  assert.equal(f.probe.snapshot().contexts.length, 2);
  assert.deepEqual(f.probe.snapshot().errors, []);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('closed unused contexts remain counted rather than disappearing from evidence', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode);
  master.connect(f.ctx.destination);
  const unused = new f.host.AudioContext();
  unused.state = 'closed';
  assert.equal(f.probe.snapshot().contexts.length, 2);
  assert.equal(f.probe.snapshot().contexts[1].state, 'closed');
  assert.throws(() => f.probe.startRecording(), /No unambiguous/);
});
test('construction through an instance constructor alias is also counted', () => {
  const f = fixture();
  assert.equal(f.ctx.constructor, f.host.AudioContext);
  new f.ctx.constructor();
  assert.equal(f.probe.snapshot().contexts.length, 2);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});

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
test('terminal gain observations include only active genuine destination gains without rewriting values', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), upstream = f.ctx.create(f.GainNode), detached = f.ctx.create(f.GainNode);
  upstream.connect(master); master.connect(f.ctx.destination); master.connect(f.ctx.destination);
  detached.connect(f.ctx.destination); detached.disconnect();
  upstream.gain.value = 0; detached.gain.value = 0;
  const source = f.probe.snapshot().contexts[0].terminals.find(item => item.active).source;
  for (const value of [1, .5, -1, 1e-9, 0]) {
    master.gain.value = value;
    assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).terminal_gain_values, [{ source, value }]);
  }
  master.disconnect(f.ctx.destination);
  assert.deepEqual(f.probe.snapshot().contexts[0].samples.at(-1).terminal_gain_values, []);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('suspension records real terminal mute separately and preserves the frozen nonzero analyser PCM', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master); f.ctx.state = 'running'; source.start(); f.advance(100);
  const before = f.probe.snapshot().contexts[0].samples.at(-1);
  assert(before.rms > 0);
  master.gain.value = 0; f.ctx.state = 'suspended'; f.advance(1200);
  const muted = f.probe.snapshot().contexts[0].samples.at(-1);
  assert.equal(muted.context_time, before.context_time); assert.equal(muted.rms, before.rms);
  assert.equal(muted.terminal_gain_values[0].value, 0);
  master.gain.value = .25; f.advance(100);
  const unmuted = f.probe.snapshot().contexts[0].samples.at(-1);
  assert.equal(unmuted.rms, before.rms); assert.equal(unmuted.terminal_gain_values[0].value, .25);
  assert.equal(muted.terminal_gain_values[0].value, 0, 'historical values remain immutable observations');
  assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
  assert.deepEqual(f.probe.snapshot().errors, []);
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

test('native full-buffer loop exposes immutable bounds and remains one voice after 32 seconds', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master);
  source.loop = true; source.loopStart = 0; source.loopEnd = 32;
  f.ctx.state = 'running'; source.start(); f.advance(32100);
  const snapshot = f.probe.snapshot(), start = snapshot.starts[0];
  assert.equal(start.looping, true); assert.equal(start.loop_start, 0); assert.equal(start.loop_end, 32);
  assert.equal(start.detune, 0); assert.equal(start.rate, 1); assert.equal(start.requested_duration, null);
  assert.equal(start.planned_end, null); assert.deepEqual(start.mutations, []); assert.deepEqual(start.parameter_automation, []);
  assert.equal(snapshot.contexts[0].samples.at(-1).active_music, 1);
  assert.deepEqual(snapshot.contexts[0].samples.at(-1).source_metadata, [
    { id: start.id, looping: true, rate: 1, detune: 0, loop_start: 0, loop_end: 32 }
  ]);
  assert.deepEqual(snapshot.errors, []);
  assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
});
test('short loop bounds and finite requested duration remain visible to the strict validator', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master);
  source.loop = true; source.loopStart = 2; source.loopEnd = 16; source.start(0, 0, 1);
  const start = f.probe.snapshot().starts[0];
  assert.equal(start.loop_start, 2); assert.equal(start.loop_end, 16); assert.equal(start.requested_duration, 1);
});
test('all post-start metadata mutations and change-restore pairs fail between meter ticks', () => {
  for (const [property, value, field] of [['loop', false, 'looping'], ['loopStart', 1, 'loop_start'],
    ['loopEnd', 16, 'loop_end'], ['playbackRate', 2, 'rate'], ['detune', 1200, 'detune']]) {
    const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
    master.connect(f.ctx.destination); source.connect(master);
    source.loop = true; source.loopEnd = 32; source.start();
    const previous = property === 'playbackRate' || property === 'detune' ? source[property].value : source[property];
    if (property === 'playbackRate' || property === 'detune') { source[property].value = value; source[property].value = previous; }
    else { source[property] = value; source[property] = previous; }
    const snapshot = f.probe.snapshot();
    assert.equal(snapshot.starts[0].mutations.length, 2, property);
    assert(snapshot.starts[0].mutations.every(item => item.field === field), property);
    assert.equal(snapshot.errors.filter(error => error.includes('Post-start source metadata changed')).length, 2, property);
    assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
  }
});
test('same-value setters, ordinary stop/disconnect and gain automation are not metadata mutations', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master);
  source.loop = true; source.loopEnd = 32; source.start();
  source.loop = true; source.loopStart = 0; source.loopEnd = 32;
  source.playbackRate.value = 1; source.detune.value = 0;
  assert.equal(master.gain.setValueAtTime(0, 1), master.gain);
  assert.deepEqual(master.gain.calls, [['setValueAtTime', 0, 1]]);
  master.gain.value = 0;
  source.stop(); source.disconnect();
  const snapshot = f.probe.snapshot();
  assert.deepEqual(snapshot.starts[0].mutations, []);
  assert.deepEqual(snapshot.starts[0].parameter_automation, []);
  assert.deepEqual(snapshot.errors, []);
});
test('native setter exceptions propagate without inventing a successful mutation', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master); source.start();
  assert.throws(() => { source.loopStart = NaN; }, /Nonfinite loop start/);
  assert.throws(() => { source.playbackRate.value = Infinity; }, /Nonfinite parameter/);
  assert.deepEqual(f.probe.snapshot().starts[0].mutations, []);
  assert.deepEqual(f.probe.snapshot().errors, []);
});
test('sample-time metadata reads also detect actual parameter changes', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master); source.start();
  source.detune._value = 100; // Fixture models a native-engine change outside a JS setter.
  f.advance(100);
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.starts[0].mutations[0].reason, 'meter sample');
  assert.equal(snapshot.contexts[0].samples.at(-1).source_metadata[0].detune, 100);
  assert.match(snapshot.errors[0], /Post-start source metadata changed/);
});
test('future source parameter automation fails even while the current value is unchanged', () => {
  for (const field of ['playbackRate', 'detune']) {
    for (const method of ['setValueAtTime', 'linearRampToValueAtTime', 'exponentialRampToValueAtTime',
      'setTargetAtTime', 'setValueCurveAtTime']) {
      const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
      master.connect(f.ctx.destination); source.connect(master); source.start();
      const parameter = source[field], before = parameter.value;
      assert.equal(parameter[method](2, 40, 1), parameter);
      assert.equal(parameter.value, before);
      assert.deepEqual(parameter.calls, [[method, 2, 40, ...(['setTargetAtTime', 'setValueCurveAtTime'].includes(method) ? [1] : [])]]);
      const snapshot = f.probe.snapshot();
      assert.equal(snapshot.starts[0].parameter_automation.length, 1);
      assert.match(snapshot.errors[0], /Uncertifiable source parameter automation/);
    }
  }
});
test('rate automation scheduled before start cannot evade the source audit', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master);
  source.playbackRate.setValueAtTime(2, 31);
  source.start();
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.starts[0].parameter_automation[0].field, 'rate');
  assert.match(snapshot.errors[0], /Uncertifiable source parameter automation/);
});
test('audio-rate modulation of a source parameter cannot evade fixed-rate evidence', () => {
  for (const beforeStart of [true, false]) {
    const f = fixture(), master = f.ctx.create(f.GainNode), modulator = f.ctx.create(f.GainNode), source = f.source();
    master.connect(f.ctx.destination); source.connect(master);
    if (!beforeStart) source.start();
    assert.equal(modulator.connect(source.playbackRate), undefined);
    assert.equal(modulator.out[0].destination, source.playbackRate);
    if (beforeStart) source.start();
    const snapshot = f.probe.snapshot();
    assert.equal(source.playbackRate.value, 1);
    assert.equal(snapshot.starts[0].parameter_automation[0].method, 'audio_input');
    assert.match(snapshot.errors[0], /Uncertifiable source parameter automation/);
  }
});
test('public gain-parameter input retains its API return and does not alter source timing checks', () => {
  const f = fixture(), master = f.ctx.create(f.GainNode), modulator = f.ctx.create(f.GainNode), source = f.source();
  master.connect(f.ctx.destination); source.connect(master); source.start();
  assert.equal(modulator.connect(master.gain), undefined);
  assert.deepEqual(f.probe.snapshot().errors, []);
  assert.deepEqual(f.probe.snapshot().starts[0].parameter_automation, []);
});

// These module/port fixtures only exercise observer plumbing. Actual PCM
// arithmetic and processing-clock continuity have independent processor tests.
test('ready pre-arms mix and both graph-discovered buses without sources or resume', async () => {
  const f = fixture(), master = f.ctx.createGain(), firstBus = f.ctx.createGain(), secondBus = f.ctx.createGain();
  firstBus.connect(master); secondBus.connect(master); master.connect(f.ctx.destination);
  const ready = await f.probe.ready(), snapshot = f.probe.snapshot(), thread = snapshot.contexts[0].audio_thread;
  assert.equal(f.moduleUrls.length, 1); assert.deepEqual(f.revokedUrls, f.moduleUrls);
  assert.equal(ready.streams.length, 3); assert.equal(thread.streams.length, 3);
  assert.equal(thread.role, 'mix'); assert.equal(thread.source, null);
  assert.deepEqual(thread.streams.map(item => item.role), ['mix', 'bus', 'bus']);
  assert(thread.streams.every(item => item.status === 'ready' && item.graph.output === 'zero-only'));
  assert(thread.streams.every(item => item.windows.length === 0 && item.gaps.length === 0));
  assert(thread.streams.every(item => item.graph.destination === snapshot.contexts[0].destination));
  assert.equal(master.out.length, 3, 'original speaker, original analyser tap, original stream tap');
  assert.equal(firstBus.out.length, 2, 'original master edge plus genuine bus observer');
  assert.equal(secondBus.out.length, 2);
  const observers = f.ctx.nodes.filter(node => node instanceof f.AudioWorkletNode);
  assert(observers.every(node => node.out.length === 1 && node.out[0].destination.stream));
  assert(observers.every(node => node.options.numberOfInputs === 1 && node.options.numberOfOutputs === 1));
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
  assert.deepEqual(snapshot.errors, []);
});
test('gain creation captures initial and scheduled values before the first original graph connection', () => {
  const f = fixture(), node = f.ctx.createGain();
  node.gain.setValueAtTime(.7, 0); node.gain.value = .4;
  node.gain.cancelScheduledValues(1); node.gain.cancelAndHoldAtTime(2);
  let events = f.probe.snapshot().gain_events;
  assert.deepEqual(events.map(item => item.method), ['initial', 'setValueAtTime', 'value', 'cancelScheduledValues', 'cancelAndHoldAtTime']);
  assert.deepEqual(events.map(item => item.args), [[], [.7, 0], [.4], [1], [2]]);
  assert(events.every(item => item.context === 1 && item.context_time === 0));
  assert.equal(events[0].value, 1); assert.equal(f.probe.snapshot().graph_events.length, 0);
  const direct = new f.host.GainNode(f.ctx);
  assert.equal(direct.constructor, f.host.GainNode);
  direct.gain.setValueAtTime(.2, 0);
  events = f.probe.snapshot().gain_events;
  assert.equal(events.at(-2).method, 'initial'); assert.equal(events.at(-1).method, 'setValueAtTime');
  assert.notEqual(events.at(-1).node, events[0].node);
});
test('source taps are selected from the actual connected path and preserve original graph events', async () => {
  const f = fixture(), master = f.ctx.createGain(), firstBus = f.ctx.createGain(), secondBus = f.ctx.createGain();
  firstBus.connect(master); secondBus.connect(master); master.connect(f.ctx.destination); await f.probe.ready();
  f.ctx.state = 'running'; const source = f.source(.72); source.connect(secondBus); source.start();
  const snapshot = f.probe.snapshot(), start = snapshot.starts[0];
  assert.deepEqual(start.meter_taps.map(item => item.role), ['mix', 'bus']);
  assert.equal(start.meter_taps[1].source, start.path_at_start[1]);
  assert.equal(snapshot.graph_events.length, 4, 'observer-only edges never enter original-source graph history');
  assert(snapshot.graph_events.every(item => item.event === 'connect' && item.context_time === 0));
  source.disconnect();
  assert.equal(f.probe.snapshot().graph_events.at(-1).event, 'disconnect');
  assert.deepEqual(f.counters(), { originalStarts: 1, resumes: 0 });
});
test('bus disconnect detaches only its observer tap and reconnect restores one tap', async () => {
  const f = fixture(), master = f.ctx.createGain(), bus = f.ctx.createGain();
  bus.connect(master); master.connect(f.ctx.destination); await f.probe.ready();
  bus.disconnect(master); assert.equal(bus.out.length, 0);
  assert.equal(f.probe.snapshot().contexts[0].audio_thread.streams[1].graph.input_active, false);
  bus.connect(master); bus.connect(master);
  assert.equal(bus.out.length, 2); assert.equal(f.probe.snapshot().contexts[0].audio_thread.streams.length, 2);
  bus.disconnect(); assert.equal(bus.out.length, 0);
  assert.deepEqual(f.probe.snapshot().errors, []);
});
test('async module loading is explicit, does not activate audio, and is required before recording', async () => {
  const f = fixture(); let resolveModule;
  f.ctx.audioWorklet.addModule = url => { f.moduleUrls.push(url); return new Promise(resolve => { resolveModule = resolve; }); };
  const master = f.ctx.createGain(); master.connect(f.ctx.destination);
  assert.equal(f.probe.snapshot().contexts[0].audio_thread.status, 'loading');
  assert.throws(() => f.probe.startRecording(), /meters are not ready/);
  let settled = false; const ready = f.probe.ready().then(() => { settled = true; });
  await Promise.resolve(); assert.equal(settled, false);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
  resolveModule(); await ready;
  assert.equal(f.probe.snapshot().contexts[0].audio_thread.status, 'ready');
  assert.deepEqual(f.revokedUrls, f.moduleUrls);
});
test('missing worklet source and failed addModule preserve exact failures and never substitute a meter', async () => {
  for (const failure of ['missing-source', 'module-rejected']) {
    const f = fixture();
    if (failure === 'missing-source') delete f.host.__tidalAudioWorkletSource;
    else f.ctx.audioWorklet.addModule = url => { f.moduleUrls.push(url); return Promise.reject(new Error('Fixture module rejected')); };
    f.ctx.createGain().connect(f.ctx.destination);
    await assert.rejects(f.probe.ready(), /meters are not ready/);
    const thread = f.probe.snapshot().contexts[0].audio_thread;
    assert.equal(thread.status, 'failed'); assert.deepEqual(thread.streams, []); assert.deepEqual(thread.windows, []);
    assert.match(f.probe.snapshot().errors[0], /source\/API unavailable|Fixture module rejected/);
    assert.throws(() => f.probe.startRecording(), /No unambiguous/);
    assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
  }
});
test('real source started before readiness remains a failure even if module later loads', async () => {
  const f = fixture(); let resolveModule;
  f.ctx.audioWorklet.addModule = () => new Promise(resolve => { resolveModule = resolve; });
  const master = f.ctx.createGain(); master.connect(f.ctx.destination);
  const source = f.source(); source.connect(master); source.start();
  assert.match(f.probe.snapshot().errors[0], /source started before audio-thread meters/);
  resolveModule(); await assert.rejects(f.probe.ready(), /not ready/);
  assert.equal(f.probe.snapshot().starts.length, 1, 'actual native start is still retained');
});
function actualFixtureReceipt(tap, start = 0) {
  const create = require('./audio_meter_worklet.js'), emitted = [];
  class Base { constructor() { this.port = { postMessage: value => emitted.push(value) }; } }
  const Processor = create(Base, () => start, tap.sample_rate), processor = new Processor({ processorOptions: {
    tapId: tap.tap_id, windowFrames: tap.window_frames } });
  processor.process([[new Float32Array(tap.window_frames).fill(.125), new Float32Array(tap.window_frames).fill(.25)]],
    [[new Float32Array(tap.window_frames)]]);
  return emitted[0];
}
test('received PCM keeps processing frames separate from late delivery and current source metadata', async () => {
  const f = fixture(), master = f.ctx.createGain(); master.connect(f.ctx.destination); await f.probe.ready();
  const tap = f.probe.snapshot().contexts[0].audio_thread, node = f.ctx.nodes.find(item => item instanceof f.AudioWorkletNode);
  f.advance(12345); node.deliver(actualFixtureReceipt(tap));
  const receipt = f.probe.snapshot().contexts[0].audio_thread.windows[0];
  assert.equal(receipt.delivery_ms, 12345); assert.equal(receipt.start_frame, 0); assert.equal(receipt.end_frame, 4800);
  assert.equal(receipt.active_cues, undefined); assert.equal(receipt.active_music, undefined);
  assert.equal(receipt.source_metadata, undefined); assert.equal(receipt.terminal_gain_values, undefined); assert.equal(receipt.wall_ms, undefined);
  assert.equal(receipt.samples, 9600); assert.equal(node.port.sent[0].type, 'ack');
  assert.equal(f.probe.snapshot().contexts[0].state, 'suspended', 'late delivered receipt is not relabeled as current PCM');
  const before = f.probe.snapshot().contexts[0].audio_thread.windows;
  f.advance(60000); assert.deepEqual(f.probe.snapshot().contexts[0].audio_thread.windows, before);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('flush awaits an actual worklet barrier and never resumes a suspended context', async () => {
  const f = fixture(), master = f.ctx.createGain(); master.connect(f.ctx.destination); await f.probe.ready();
  await assert.rejects(f.probe.flush(), /already-running/);
  f.ctx.state = 'running';
  const node = f.ctx.nodes.find(item => item instanceof f.AudioWorkletNode), tap = f.probe.snapshot().contexts[0].audio_thread;
  node.deliver(actualFixtureReceipt(tap));
  const flushed = f.probe.flush(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  const request = node.port.sent.find(item => item.type === 'barrier'); assert(request);
  node.deliver({ type: 'barrier', schema: 1, tap_id: tap.tap_id, sample_rate: tap.sample_rate,
    id: request.id, sequence: 1, processed_end_frame: 4928, partial_frames: 128 });
  const receipts = await flushed;
  assert.equal(receipts[0].context, 1); assert.equal(receipts[0].processed_end_frame, 4928); assert.equal(receipts[0].partial_frames, 128);
  assert.equal(f.probe.snapshot().contexts[0].audio_thread.windows.length, 1);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});
test('dropped and duplicate worklet receipts or processor errors permanently fail recording', async () => {
  for (const failure of ['dropped', 'duplicate', 'processor']) {
    const f = fixture(), master = f.ctx.createGain(); master.connect(f.ctx.destination); await f.probe.ready();
    const node = f.ctx.nodes.find(item => item instanceof f.AudioWorkletNode), tap = f.probe.snapshot().contexts[0].audio_thread;
    if (failure === 'processor') node.listeners.processorerror();
    else {
      const receipt = actualFixtureReceipt(tap); node.deliver(receipt);
      node.deliver(failure === 'duplicate' ? receipt : { ...actualFixtureReceipt(tap, 9600), sequence: 3 });
    }
    assert.equal(f.probe.snapshot().contexts[0].audio_thread.status, 'failed');
    assert.throws(() => f.probe.startRecording(), /No unambiguous/);
  }
});
test('bounded gain history overflow is retained and fails closed', () => {
  const f = fixture(), gain = f.ctx.createGain();
  for (let index = 0; index < 4100; index++) gain.gain.value = index / 5000;
  const snapshot = f.probe.snapshot();
  assert.equal(snapshot.gain_events.length, 4096); assert.equal(snapshot.history_overflow, true);
  assert(snapshot.errors.some(message => /history overflow/.test(message)));
});

test('worklet failure frame telemetry survives late main-thread delivery and snapshot copying', async () => {
  const f = fixture(), master = f.ctx.createGain(); master.connect(f.ctx.destination); await f.probe.ready();
  const node = f.ctx.nodes.find(item => item instanceof f.AudioWorkletNode), tap = f.probe.snapshot().contexts[0].audio_thread;
  f.advance(12345); f.ctx.state = 'running';
  node.deliver({ type: 'error', schema: 1, tap_id: tap.tap_id, sample_rate: tap.sample_rate,
    error: 'Discontinuous audio-thread render frames', overflow: false, sequence: 7,
    processed_end_frame: 512, diagnostic: { expected_frame: 512, actual_frame: 640,
      delta_frames: 128, quantum_frames: 128, input_channels: 0, previous_had_input: false,
      segment: 2, partial_frames: 0, pending_no_input_start: 256, pending_no_input_end: 512 } });
  const thread = f.probe.snapshot().contexts[0].audio_thread;
  assert.equal(thread.status, 'failed'); assert.equal(thread.failure_receipt.delivery_ms, 12345);
  assert.equal(thread.failure_receipt.delivery_context_state, 'running');
  assert.equal(thread.failure_receipt.processed_end_frame, 512);
  assert.equal(thread.failure_receipt.diagnostic.actual_frame, 640);
  thread.failure_receipt.diagnostic.actual_frame = 999;
  assert.equal(f.probe.snapshot().contexts[0].audio_thread.failure_receipt.diagnostic.actual_frame, 640);
  await assert.rejects(f.probe.ready(), /not ready/); await assert.rejects(f.probe.flush(), /not ready/);
  assert.deepEqual(f.probe.snapshot().contexts[0].audio_thread.windows, []);
  assert.deepEqual(f.counters(), { originalStarts: 0, resumes: 0 });
});

test('health is bounded read-only metadata and cannot clear failure or resume the graph', async () => {
  const f=fixture(), master=f.ctx.createGain();master.connect(f.ctx.destination);await f.probe.ready();
  const h=f.probe.health();assert.equal(h.contexts.length,1);assert.equal(h.contexts[0].state,'suspended');
  assert.equal(h.contexts[0].meters.length,1);assert.equal(h.contexts[0].samples,undefined);
  h.contexts[0].meters[0].status='failed';assert.equal(f.probe.health().contexts[0].meters[0].status,'ready');
  assert.deepEqual(f.counters(),{originalStarts:0,resumes:0});
});
