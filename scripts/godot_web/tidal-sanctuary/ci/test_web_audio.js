'use strict';
// Deterministic production-backend API fixtures, not browser/PCM acceptance.
const assert = require('node:assert/strict');
const test = require('node:test');
const {createWebAudio} = require('../game/web_audio.js');
const URLS = {music: 'music', chart_read: 'chart', key_pickup: 'key', pearl_pickup: 'pearl', beacon_resolve: 'beacon'};
const DURATIONS = {music: 32, chart: .72, key: 1.05, pearl: 1.65, beacon: 4.8};
const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}
function fixture({visible = true, focused = true} = {}) {
  let wall = 0, nextTimer = 0;
  const timers = new Map();
  const windowListeners = new Map(), documentListeners = new Map();
  const add = (map, name, callback) => { if (!map.has(name)) map.set(name, new Set()); map.get(name).add(callback); };
  const remove = (map, name, callback) => map.get(name)?.delete(callback);
  const emit = (map, name) => { for (const callback of map.get(name) || []) callback({type: name}); };
  let windowHasFocus = focused;
  const document = {visibilityState: visible ? 'visible' : 'hidden',
    hasFocus: () => windowHasFocus && document.visibilityState === 'visible',
    addEventListener: (name, callback) => add(documentListeners, name, callback),
    removeEventListener: (name, callback) => remove(documentListeners, name, callback)};
  const calls = {construct: 0, resume: 0, suspend: 0, close: 0, fetch: [], starts: [], nodes: []};
  const options = {fetchFailure: '', badDuration: '', decodeFailure: false, resumeFailure: false,
    resumeBlocked: false, startFailure: false, closeFailure: false, constructorFailure: false};
  let context;
  class Param {
    constructor() { this.intrinsic = 1; this.events = []; }
    get value() { return this.intrinsic; }
    set value(value) { this.intrinsic = value; this.setValueAtTime(value, context.currentTime); }
    // Scheduling alone does not synchronously update the intrinsic getter.
    setValueAtTime(value, at) { this.events.push(['set', value, at]); }
    renderStepEvents() {
      // Bounded master-gain fixture, not an audio renderer or ramp simulation.
      assert(this.events.every(event => event[0] === 'set'));
      for (const event of this.events) if (event[2] <= context.currentTime) this.intrinsic = event[1];
    }
    cancelScheduledValues(at) { this.events.push(['cancel', at]); }
    exponentialRampToValueAtTime(value, at) { this.events.push(['exponential', value, at]); }
  }
  class Node {
    constructor(ctx, type) { this.context = ctx; this.type = type; this.edges = []; calls.nodes.push(this); }
    connect(node) { assert.equal(node.context, this.context); this.edges.push(node); return node; }
    disconnect() { this.edges = []; this.disconnected = true; }
  }
  class Gain extends Node { constructor(ctx) { super(ctx, 'gain'); this.gain = new Param(); } }
  class Source extends Node {
    constructor(ctx) { super(ctx, 'source'); this.loop = false; this.stopped = false; }
    start(at, offset) {
      if (options.startFailure) throw Error('source start failed');
      calls.starts.push({source: this, at, offset});
      this.started = true;
    }
    stop() { this.stopped = true; }
  }
  class Context {
    constructor() {
      if (options.constructorFailure) throw Error('context construction failed');
      calls.construct++;
      this.currentTime = 0; this.state = 'suspended'; this.sampleRate = 44100;
      this.destination = new Node(this, 'destination'); context = this;
    }
    createGain() { if (options.gainFailure) throw Error('gain failed'); return new Gain(this); }
    createBufferSource() { if (options.sourceFailure) throw Error('source creation failed'); return new Source(this); }
    async decodeAudioData(bytes) {
      if (options.decodeFailure) throw Error('decode failed');
      if (options.decodeWait) await options.decodeWait.promise;
      return {duration: DURATIONS[bytes.url] + (options.badDuration === bytes.url ? 1 : 0), original: bytes};
    }
    async resume() {
      calls.resume++;
      if (options.resumeWait) await options.resumeWait.promise;
      if (options.resumeFailure) throw Error('resume denied');
      if (!options.resumeBlocked) this.state = 'running';
    }
    async suspend() {
      calls.suspend++;
      if (options.suspendWait) await options.suspendWait.promise;
      this.state = 'suspended';
    }
    async close() {
      calls.close++;
      if (options.closeWait) await options.closeWait.promise;
      if (options.closeFailure) throw Error('close failed');
      this.state = 'closed';
    }
  }
  const host = {AudioContext: Context, AbortController,
    document,
    addEventListener: (name, callback) => add(windowListeners, name, callback),
    removeEventListener: (name, callback) => remove(windowListeners, name, callback),
    setTimeout: (callback, milliseconds) => { const id = ++nextTimer; timers.set(id, {callback, at: wall + milliseconds}); return id; },
    clearTimeout: id => timers.delete(id),
    navigator: {userActivation: {isActive: false}},
    fetch: async (url, request) => {
      calls.fetch.push({url, signal: request.signal});
      if (options.fetchWait) await options.fetchWait.promise;
      return {ok: options.fetchFailure !== url, status: options.fetchFailure === url ? 503 : 200,
        arrayBuffer: async () => ({url})};
    }};
  const audio = createWebAudio(host);
  const state = () => JSON.parse(audio.getState());
  const advance = seconds => { if (context.state === 'running') context.currentTime += seconds; };
  const elapse = async milliseconds => {
    wall += milliseconds;
    for (const [id, timer] of [...timers]) if (timer.at <= wall) { timers.delete(id); timer.callback(); }
    await settle();
  };
  const begin = async () => { host.navigator.userActivation.isActive = true;
    const accepted = audio.start('begin_button'); await settle(); return accepted; };
  const events = {
    window: async name => { windowHasFocus = name === 'focus'; emit(windowListeners, name); await settle(); },
    visibility: async value => { document.visibilityState = value; emit(documentListeners, 'visibilitychange'); await settle(); },
    listenerCount: () => [...windowListeners.values(), ...documentListeners.values()].reduce((total, set) => total + set.size, 0)
  };
  return {audio, calls, options, host, state, advance, begin, elapse, timers, events, context: () => context};
}

test('initialize decodes five unchanged buffers into one silent context and never starts or resumes', async () => {
  const f = fixture();
  f.audio.setMuted(true);
  assert(await f.audio.initialize(JSON.stringify(URLS)));
  assert.deepEqual(f.calls.fetch.map(item => item.url), Object.values(URLS));
  assert.equal(f.calls.construct, 1); assert.equal(f.calls.resume, 0); assert.equal(f.calls.starts.length, 0);
  assert.equal(f.state().status, 'ready'); assert(f.state().ready); assert(!f.state().started);
  assert.equal(f.state().context_state, 'suspended'); assert(f.state().muted);
  const terminals = f.calls.nodes.filter(node => node.edges.includes(f.context().destination));
  assert.equal(terminals.length, 1); assert.equal(terminals[0].gain.value, 0);
  assert(await f.audio.initialize(URLS)); assert.equal(f.calls.construct, 1); assert.equal(f.calls.fetch.length, 5);
  await f.audio.setFocusActive(false); await f.audio.setFocusActive(true);
  f.audio.setMuted(false); f.audio.resetCues();
  assert.equal(f.calls.resume, 0); assert.equal(f.calls.starts.length, 0);
});

test('start needs ready assets and a live actual activation; duplicate and empty starts are rejected', async () => {
  const f = fixture();
  assert(!f.audio.start('begin_button'));
  await f.audio.initialize(URLS);
  assert(!f.audio.start('begin_button')); assert.match(f.state().error, /active user gesture/);
  assert.equal(f.calls.resume, 0);
  f.host.navigator.userActivation.isActive = true;
  assert(!f.audio.start('  '));
  assert(f.audio.start('begin_button'));
  assert.equal(f.calls.resume, 1, 'resume happens synchronously in the input callback');
  assert(f.state().start_pending); assert(!f.state().started); assert(!f.state().music_playing);
  assert(!f.audio.start('duplicate_pending'));
  await settle();
  assert(f.state().started); assert(f.state().music_playing); assert.equal(f.state().start_count, 1);
  assert(!f.state().start_pending); assert.equal(f.state().trigger, 'begin_button');
  assert(!f.audio.start('duplicate')); assert.equal(f.calls.starts.length, 1);
});

test('music uses native exact 0..32 looping and audio-clock dB fade, with no ended-loop restart', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin();
  const start = f.calls.starts[0], source = start.source, gain = source.edges[0];
  assert.equal(source.buffer.original.url, URLS.music); assert.equal(source.buffer.duration, 32);
  assert.equal(source.loop, true); assert.equal(source.loopStart, 0); assert.equal(source.loopEnd, 32);
  assert.equal(start.at, 0); assert.equal(start.offset, 0);
  assert.deepEqual(gain.gain.events.slice(-3), [['cancel', 0], ['set', .01, 0], ['exponential', Math.pow(10, -.25), 1.5]]);
  f.advance(100.25);
  assert.equal(f.state().music_position, 4.25); assert.equal(f.calls.starts.length, 1);
  source.onended();
  assert.equal(f.calls.starts.length, 1, 'unexpected ended reports failure instead of frame-driven replacement');
  assert(!f.state().music_playing); assert.match(f.state().error, /ended unexpectedly/);
});

test('muted Begin and later mute/unmute keep the same single source and clock', async () => {
  const f = fixture(); await f.audio.initialize(URLS); f.audio.setMuted(true); await f.begin();
  const source = f.calls.starts[0].source, master = source.edges[0].edges[0];
  assert(f.state().started); assert(f.state().music_playing); assert(f.state().bus_muted);
  assert.equal(master.gain.value, 0); f.advance(2.5);
  f.audio.setMuted(false); assert.equal(master.gain.value, 1); assert.equal(f.state().music_position, 2.5);
  f.audio.setMuted(true); f.audio.setMuted(false);
  assert.equal(f.calls.starts.length, 1); assert.equal(f.calls.starts[0].source, source); assert(!source.stopped);
  assert.equal(f.calls.resume, 1);
});

test('focus suspends the existing timeline and preserves mute preference on return', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); f.advance(4.75);
  assert(f.audio.playCue(0)); const music = f.calls.starts[0].source;
  await f.audio.setFocusActive(false); f.advance(10);
  assert.equal(f.state().music_position, 4.75); assert(f.state().music_paused); assert(f.state().cue_paused);
  assert(f.state().bus_muted); assert(!f.state().music_playing);
  f.audio.setMuted(true); await f.audio.setFocusActive(true);
  assert.equal(f.state().music_position, 4.75); assert(!f.state().music_paused); assert(f.state().bus_muted);
  f.audio.setMuted(false); f.advance(.25);
  assert.equal(f.state().music_position, 5); assert.equal(f.calls.starts[0].source, music);
  assert.equal(f.state().start_count, 1);
});

test('rapid focus changes and focus loss during pending Begin cannot create out-of-order playback', async () => {
  const f = fixture(); await f.audio.initialize(URLS);
  f.options.resumeWait = deferred(); f.host.navigator.userActivation.isActive = true;
  assert(f.audio.start('begin_button')); f.audio.setFocusActive(false);
  f.options.resumeWait.resolve(); await settle();
  assert(f.state().started); assert.equal(f.state().context_state, 'suspended'); assert(f.state().bus_muted);
  delete f.options.resumeWait;
  f.audio.setFocusActive(true); f.audio.setFocusActive(false); await settle();
  assert.equal(f.state().context_state, 'suspended'); assert.equal(f.calls.starts.length, 1);
  f.audio.setFocusActive(false); await f.audio.setFocusActive(true);
  assert.equal(f.state().context_state, 'running'); assert.equal(f.calls.starts.length, 1);
});

test('four original cues are guarded, replace a single voice, and end by audio time even without callbacks', async () => {
  const f = fixture(); await f.audio.initialize(URLS);
  assert(!f.audio.playCue(0)); await f.begin();
  for (const index of [-1, 4, 1.5, '1', NaN]) assert(!f.audio.playCue(index));
  for (let index = 0; index < 4; index++) {
    const previous = f.calls.starts.at(-1).source;
    assert(f.audio.playCue(index)); assert(!f.audio.playCue(index));
    const source = f.calls.starts.at(-1).source;
    assert.equal(source.buffer.original.url, Object.values(URLS)[index + 1]);
    assert.equal(source.loop, false);
    assert.deepEqual(source.edges[0].gain.events, [['set', Math.pow(10, -3 / 20), 0]]);
    if (index) { assert(previous.stopped); assert(previous.disconnected); previous.onended(); assert(f.state().cue_playing); }
  }
  assert.deepEqual(f.state().cue_counts, [1, 1, 1, 1]);
  f.advance(4.81); assert(!f.state().cue_playing);
  const music = f.calls.starts[0].source;
  f.audio.resetCues(); assert.deepEqual(f.state().cue_counts, [0, 0, 0, 0]); assert(!f.state().cue_playing);
  assert(f.audio.playCue(0)); assert(!music.stopped); assert.equal(f.state().start_count, 1);
});

test('loading is single-flight and a fetch/decode/duration failure can retry in the same context', async () => {
  for (const failure of ['fetchFailure', 'decodeFailure', 'badDuration']) {
    const f = fixture(); f.options[failure] = failure === 'decodeFailure' ? true : URLS.music;
    const first = f.audio.initialize(URLS);
    assert.equal(f.audio.initialize(URLS), first);
    assert.equal(await first, false);
    assert.equal(f.state().status, 'error'); assert(!f.state().ready); assert(!f.state().started);
    assert(!await f.begin()); assert.equal(f.calls.starts.length, 0); assert.equal(f.calls.resume, 0);
    f.options[failure] = failure === 'decodeFailure' ? false : '';
    assert(await f.audio.initialize(URLS)); assert.equal(f.calls.construct, 1);
    assert(!f.state().started); assert.equal(f.calls.resume, 0); assert(await f.begin());
  }
});

test('cue creation/start failures do not claim playback or consume the story cue guard', async () => {
  for (const failure of ['sourceFailure', 'startFailure']) {
    const f = fixture(); await f.audio.initialize(URLS); await f.begin();
    f.options[failure] = true;
    assert(!f.audio.playCue(0)); assert(!f.state().cue_playing);
    assert.equal(f.state().cue_counts[0], 0); assert.equal(f.state().status, 'error');
    f.options[failure] = false;
    assert(f.audio.playCue(0)); assert.equal(f.state().cue_counts[0], 1);
    assert.equal(f.state().start_count, 1); assert.equal(f.calls.starts.length, 2);
  }
});

test('malformed URLs and unavailable context fail honestly and can retry before any playback', async () => {
  const f = fixture();
  assert.equal(await f.audio.initialize('{}'), false); assert.equal(f.calls.construct, 0);
  f.options.constructorFailure = true;
  assert.equal(await f.audio.initialize(URLS), false); assert(!f.state().ready); assert.equal(f.calls.construct, 0);
  f.options.constructorFailure = false;
  assert(await f.audio.initialize(URLS)); assert.equal(f.calls.construct, 1); assert.equal(f.calls.starts.length, 0);
});

test('rejected or blocked resume never claims a logical start or playing, and another real Begin retries', async () => {
  for (const failure of ['resumeFailure', 'resumeBlocked', 'startFailure']) {
    const f = fixture(); await f.audio.initialize(URLS); f.options[failure] = true;
    assert(await f.begin());
    assert.equal(f.state().status, 'error'); assert(f.state().ready);
    assert(!f.state().started); assert(!f.state().music_playing); assert.equal(f.state().start_count, 0);
    f.options[failure] = false;
    const resumes = f.calls.resume, fetched = f.calls.fetch.length;
    assert(await f.audio.initialize(URLS));
    assert.equal(f.state().status, 'ready'); assert.equal(f.state().error, '');
    assert.equal(f.calls.resume, resumes); assert.equal(f.calls.fetch.length, fetched);
    assert(!f.state().started); assert(!f.state().music_playing);
    assert(await f.begin()); assert(f.state().started); assert.equal(f.state().start_count, 1);
    assert.equal(f.calls.construct, 1); assert.equal(f.calls.starts.length, 1);
  }
});

test('graph setup failure retries with the same context and exactly one terminal edge', async () => {
  const f = fixture(); f.options.gainFailure = true;
  assert.equal(await f.audio.initialize(URLS), false); assert(!f.state().ready);
  f.options.gainFailure = false;
  assert(await f.audio.initialize(URLS)); assert.equal(f.calls.construct, 1);
  assert.equal(f.calls.nodes.filter(node => node.edges.includes(f.context().destination)).length, 1);
  assert.equal(f.calls.resume, 0); assert.equal(f.calls.starts.length, 0);
});

test('failed focus resume reports paused source and a real gesture can resume without replacement', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); await f.audio.setFocusActive(false);
  const original = f.calls.starts[0].source, gainEvents = original.edges[0].gain.events.slice();
  f.options.resumeFailure = true; await f.audio.setFocusActive(true);
  assert.equal(f.state().status, 'error'); assert(f.state().music_paused); assert(!f.state().music_playing);
  f.options.resumeFailure = false; assert(f.audio.start('retry_audio_button')); await settle();
  assert.equal(f.state().status, 'ready'); assert(f.state().music_playing);
  assert.equal(f.calls.starts.length, 1); assert.equal(f.state().start_count, 1);
  assert.equal(f.calls.starts[0].source, original); assert.equal(f.state().trigger, 'begin_button');
  assert.deepEqual(original.edges[0].gain.events, gainEvents); assert(!original.stopped);
});

test('close is asynchronous, idempotent, disconnects all production edges and never reinitializes', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); f.audio.playCue(1);
  f.options.closeWait = deferred();
  const closing = f.audio.close(); assert.equal(f.audio.close(), closing);
  assert.equal(f.state().status, 'closing'); assert(!f.state().ready); assert(!f.state().music_playing);
  assert(f.calls.starts.every(item => item.source.stopped)); assert(f.calls.nodes.every(node => !node.edges.length));
  assert(!await f.audio.initialize(URLS)); assert(!f.audio.start('begin_button')); assert(!f.audio.playCue(2));
  f.options.closeWait.resolve(); assert(await closing);
  assert.equal(f.state().status, 'closed'); assert.equal(f.state().context_state, 'closed');
  assert.equal(f.calls.close, 1); assert.equal(f.calls.construct, 1);
});

test('closing during decode or pending resume prevents late source creation and ready resurrection', async () => {
  const loading = fixture(); loading.options.decodeWait = deferred();
  const initialized = loading.audio.initialize(URLS); await settle();
  await loading.audio.close(); loading.options.decodeWait.resolve(); assert(!await initialized);
  assert.equal(loading.state().status, 'closed'); assert.equal(loading.calls.starts.length, 0);
  assert(loading.calls.fetch.every(item => item.signal.aborted));
  const starting = fixture(); await starting.audio.initialize(URLS);
  starting.options.resumeWait = deferred(); starting.host.navigator.userActivation.isActive = true;
  starting.audio.start('begin_button'); await starting.audio.close(); starting.options.resumeWait.resolve(); await settle();
  assert.equal(starting.state().status, 'closed'); assert(!starting.state().started);
  assert.equal(starting.calls.starts.length, 0); assert(!starting.state().ready);
});

test('close failure remains explicit and cannot be reported as successful shutdown', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); f.options.closeFailure = true;
  assert.equal(await f.audio.close(), false); assert.equal(f.state().status, 'error');
  assert.match(f.state().error, /close failed/); assert(!f.state().ready); assert(!f.state().music_playing);
});

test('15-second network/decode deadline aborts requests and fences late results through a same-context retry', async () => {
  for (const wait of ['fetchWait', 'decodeWait']) {
    const f = fixture(), expired = deferred(); f.options[wait] = expired;
    const first = f.audio.initialize(URLS); await settle();
    await f.elapse(14999); assert.equal(f.state().status, 'loading');
    await f.elapse(1); assert.equal(await first, false);
    assert.match(f.state().error, /initialization timed out/); assert(!f.state().ready);
    assert(f.calls.fetch.every(item => item.signal.aborted));
    delete f.options[wait];
    assert(await f.audio.initialize(URLS)); assert.equal(f.calls.construct, 1);
    assert.equal(f.calls.resume, 0); assert(!f.state().started);
    expired.resolve(); await settle();
    assert.equal(f.state().status, 'ready'); assert.equal(f.calls.starts.length, 0);
    assert.equal(f.timers.size, 0); assert(await f.begin()); assert.equal(f.calls.starts.length, 1);
  }
});

test('10-second Begin deadline permits retry, and a late expired resume is suspended without a voice', async () => {
  const f = fixture(); await f.audio.initialize(URLS);
  const expired = deferred(); f.options.resumeWait = expired;
  f.host.navigator.userActivation.isActive = true; assert(f.audio.start('begin_button'));
  await f.elapse(9999); assert(f.state().start_pending);
  await f.elapse(1); assert(!f.state().start_pending);
  assert.match(f.state().error, /resume timed out/); assert(!f.state().started);
  expired.resolve(); await settle();
  assert.equal(f.state().context_state, 'suspended'); assert.equal(f.calls.starts.length, 0);
  assert(!f.state().music_playing); assert.equal(f.state().start_count, 0);
  const resumes = f.calls.resume; assert(await f.audio.initialize(URLS));
  assert.equal(f.state().status, 'ready'); assert.equal(f.calls.resume, resumes);
  delete f.options.resumeWait; assert(await f.begin());
  assert.equal(f.calls.starts.length, 1); assert.equal(f.calls.construct, 1); assert.equal(f.timers.size, 0);
});

test('late expired Begin cannot replace or cancel a newer authorized attempt or its music source', async () => {
  const f = fixture(); await f.audio.initialize(URLS);
  const expired = deferred(); f.options.resumeWait = expired;
  f.host.navigator.userActivation.isActive = true; f.audio.start('old_begin');
  await f.elapse(10000); assert(await f.audio.initialize(URLS));
  const current = deferred(); f.options.resumeWait = current;
  assert(f.audio.start('new_begin')); expired.resolve(); await settle();
  assert(f.state().start_pending); assert(!f.state().started); assert.equal(f.calls.starts.length, 0);
  current.resolve(); await settle();
  assert(f.state().started); assert.equal(f.state().trigger, 'new_begin');
  assert.equal(f.state().context_state, 'running'); assert.equal(f.calls.starts.length, 1);
  assert.equal(f.state().start_count, 1); assert.equal(f.calls.construct, 1);
});

test('expired focus resume cannot revive background playback or block a later focus request', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); await f.audio.setFocusActive(false);
  const expired = deferred(); f.options.resumeWait = expired;
  const focusIn = f.audio.setFocusActive(true); await settle();
  await f.elapse(10000); await focusIn;
  assert.match(f.state().error, /focus resume timed out/);
  await f.audio.setFocusActive(false); expired.resolve(); await settle();
  assert.equal(f.state().context_state, 'suspended'); assert(f.state().bus_muted);
  delete f.options.resumeWait; await f.audio.setFocusActive(true);
  assert(f.state().music_playing); assert.equal(f.calls.starts.length, 1);
});

test('real Retry clears a late-resumed same-source error without another resume, fade or logical start', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); await f.audio.setFocusActive(false);
  const original = f.calls.starts[0].source, gainEvents = original.edges[0].gain.events.slice();
  const expired = deferred(); f.options.resumeWait = expired;
  const focusIn = f.audio.setFocusActive(true); await settle();
  await f.elapse(10000); await focusIn;
  expired.resolve(); await settle();
  assert.equal(f.state().status, 'error'); assert(f.state().music_playing);
  const resumes = f.calls.resume;
  f.host.navigator.userActivation.isActive = false;
  assert(!f.audio.start('retry_audio_button')); assert.equal(f.state().status, 'error');
  f.host.navigator.userActivation.isActive = true;
  assert(f.audio.start('retry_audio_button'));
  assert.equal(f.state().status, 'ready'); assert.equal(f.state().error, '');
  assert.equal(f.calls.resume, resumes); assert.equal(f.calls.starts.length, 1);
  assert.equal(f.state().start_count, 1); assert.equal(f.state().trigger, 'begin_button');
  assert.equal(f.calls.starts[0].source, original); assert.deepEqual(original.edges[0].gain.events, gainEvents);
  assert(!f.audio.start('duplicate_retry'));
});

test('initial hidden/unfocused state and pre-Begin DOM focus events never activate audio', async () => {
  const f = fixture({visible: false, focused: false}); await f.audio.initialize(URLS);
  assert(!f.state().focus_active); assert(f.state().bus_muted); assert(!await f.begin());
  await f.events.window('focus'); assert(!f.state().focus_active);
  await f.events.visibility('visible'); assert(f.state().focus_active);
  await f.events.window('blur'); await f.events.window('focus');
  assert.equal(f.calls.resume, 0); assert.equal(f.calls.starts.length, 0);
  assert.equal(f.state().context_state, 'suspended');
});

test('window blur and visibility suspend the original voices, preserve mute and require native canvas intent', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin(); f.audio.playCue(1); f.advance(.2);
  const music = f.calls.starts[0].source, cue = f.calls.starts[1].source;
  await f.events.window('blur'); f.advance(10);
  assert(!f.state().focus_active); assert.equal(f.state().music_position, .2);
  assert(f.state().music_paused); assert(f.state().cue_paused);
  await f.audio.setFocusActive(false); await f.events.window('focus');
  assert(!f.state().focus_active); assert.equal(f.state().context_state, 'suspended');
  await f.events.visibility('hidden'); await f.audio.setFocusActive(true);
  assert(!f.state().focus_active); assert.equal(f.state().context_state, 'suspended');
  f.audio.setMuted(true); await f.events.visibility('visible');
  assert(f.state().focus_active); assert(f.state().music_playing); assert(f.state().cue_playing);
  assert(f.state().muted); assert(f.state().bus_muted); assert.equal(f.state().music_position, .2);
  assert.equal(f.calls.starts.length, 2); assert(!music.stopped); assert(!cue.stopped);
  assert.equal(f.state().start_count, 1);
});

test('native and DOM focus ordering deduplicates suspension/resume and cannot resume a hidden document', async () => {
  for (const domFirst of [false, true]) {
    const f = fixture(); await f.audio.initialize(URLS); await f.begin();
    if (domFirst) await f.events.window('blur');
    await f.audio.setFocusActive(false);
    if (!domFirst) await f.events.window('blur');
    await f.events.visibility('hidden'); await f.audio.setFocusActive(false);
    assert.equal(f.calls.suspend, 1);
    await f.audio.setFocusActive(true); await f.events.window('focus');
    assert.equal(f.calls.resume, 1); assert(!f.state().focus_active);
    await f.events.visibility('visible'); await f.audio.setFocusActive(true); await f.events.window('focus');
    assert.equal(f.calls.resume, 2); assert(f.state().focus_active); assert.equal(f.calls.starts.length, 1);
  }
});

test('close removes all production DOM listeners and subsequent focus events cannot resume', async () => {
  const f = fixture(); assert.equal(f.events.listenerCount(), 3);
  await f.audio.initialize(URLS); await f.begin(); await f.events.window('blur');
  await f.audio.close(); assert.equal(f.events.listenerCount(), 0);
  const resumes = f.calls.resume, focus = f.state().focus_active;
  await f.events.window('focus'); await f.events.visibility('hidden'); await f.events.visibility('visible');
  assert.equal(f.calls.resume, resumes); assert.equal(f.state().focus_active, focus);
  assert.equal(f.state().context_state, 'closed'); assert.equal(f.calls.starts.length, 1);
});

test('focus mute is intrinsic before suspension can prevent the next render quantum', async () => {
  const f = fixture(); await f.audio.initialize(URLS); await f.begin();
  const source = f.calls.starts[0].source, master = source.edges[0].edges[0];
  const fade = source.edges[0].gain.events.slice();
  const before = f.context().currentTime;
  await f.audio.setFocusActive(false);
  assert.equal(f.context().state, 'suspended');
  assert.equal(f.context().currentTime, before);
  assert.equal(master.gain.value, 0, 'no render quantum was simulated before checking the real setter contract');
  f.audio.setMuted(true); await f.audio.setFocusActive(true);
  assert.equal(master.gain.value, 0);
  f.audio.setMuted(false); f.audio.setMuted(true); f.audio.setMuted(false);
  assert.equal(master.gain.value, 1);
  master.gain.renderStepEvents();
  assert.equal(master.gain.value, 1, 'the last same-time event also wins when rendering resumes');
  assert.deepEqual(source.edges[0].gain.events, fade);
  assert.equal(f.calls.starts.length, 1); assert.equal(f.calls.starts[0].source, source);
  assert.equal(f.state().start_count, 1);
});

test('hidden initialization and same-time visibility changes preserve the terminal mute', async () => {
  const f = fixture({visible: false, focused: false}); await f.audio.initialize(URLS);
  const master = f.calls.nodes.find(node => node.edges.includes(f.context().destination));
  assert.equal(master.gain.value, 0);
  f.audio.setMuted(true); await f.events.window('focus'); await f.events.visibility('visible');
  assert.equal(master.gain.value, 0);
  f.audio.setMuted(false); await f.events.visibility('hidden');
  assert.equal(master.gain.value, 0); master.gain.renderStepEvents(); assert.equal(master.gain.value, 0);
  assert.equal(f.calls.resume, 0); assert.equal(f.calls.starts.length, 0);
});
