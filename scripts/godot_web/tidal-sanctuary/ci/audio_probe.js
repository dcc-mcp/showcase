/* Test-only observer of the browser's real public WebAudio graph.
 * Inject before the engine. It never resumes a context or starts a source.
 * Godot 4.6.3 Sample's terminal bus output is its post-mute GainNode:
 * https://github.com/godotengine/godot/blob/4.6.3-stable/platform/web/js/libs/library_godot_audio.js
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory;
  else factory(root);
})(globalThis, function installTidalAudioProbe(host) {
  'use strict';
  if (host.__tidalAudio) throw new Error('Audio probe installed twice');
  const errors = [], contexts = [], nodes = [], edges = [], starts = [], gestures = [], marks = [];
  const nodeIds = new WeakMap(), contextIds = new WeakMap();
  const observedSources = new WeakMap(), sourceParameters = new WeakMap(), parameterAutomation = new WeakMap();
  const now = () => host.performance.now();
  const originalConnect = host.AudioNode.prototype.connect;
  const originalDisconnect = host.AudioNode.prototype.disconnect;
  const originalStart = host.AudioBufferSourceNode.prototype.start;
  const originalStop = host.AudioBufferSourceNode.prototype.stop;
  const allowedTerminals = new Set(['GainNode', 'AudioWorkletNode', 'ScriptProcessorNode']);
  const expected = { music: 32, chart_read: .72, key_pickup: 1.05, pearl_pickup: 1.65, beacon_resolve: 4.8 };
  const fail = error => errors.push(String(error && error.message || error));
  function sourceMetadata(source) {
    return { looping: source.loop, rate: source.playbackRate.value, detune: source.detune.value,
      loop_start: source.loopStart, loop_end: source.loopEnd };
  }
  function auditSource(source, reason) {
    const observed = observedSources.get(source);
    if (!observed) return;
    const current = sourceMetadata(source);
    for (const field of Object.keys(current)) {
      if (current[field] === observed.last[field]) continue;
      observed.item.mutations.push({ field, previous: observed.last[field], value: current[field], reason,
        wall_ms: now(), context_time: source.context.currentTime });
      fail('Post-start source metadata changed: ' + observed.item.id + '/' + field);
    }
    observed.last = current;
  }
  function recordParameterAutomation(parameter, method) {
    const history = parameterAutomation.get(parameter) || [];
    history.push({ method, wall_ms: now() });
    parameterAutomation.set(parameter, history);
    const binding = sourceParameters.get(parameter);
    if (binding) {
      binding.item.parameter_automation.push({ field: binding.field, method, wall_ms: now() });
      fail('Uncertifiable source parameter automation: ' + binding.item.id + '/' + binding.field + '/' + method);
      auditSource(binding.source, binding.field + '.' + method);
    }
  }
  function observeSetter(prototype, property, inspect) {
    try {
      const descriptor = Object.getOwnPropertyDescriptor(prototype, property);
      if (!descriptor || typeof descriptor.set !== 'function') throw new Error('Unobservable audio setter: ' + property);
      Object.defineProperty(prototype, property, { ...descriptor, set(value) {
        const result = Reflect.apply(descriptor.set, this, [value]);
        try { inspect(this); } catch (error) { fail(error); }
        return result;
      } });
    } catch (error) { fail(error); }
  }
  for (const property of ['loop', 'loopStart', 'loopEnd']) {
    observeSetter(host.AudioBufferSourceNode.prototype, property, source => auditSource(source, property + ' setter'));
  }
  if (!host.AudioParam) fail('AudioParam observation unavailable');
  else {
    observeSetter(host.AudioParam.prototype, 'value', parameter => {
      const binding = sourceParameters.get(parameter);
      if (binding) auditSource(binding.source, binding.field + '.value setter');
    });
    // Future rate/detune automation cannot be certified from current .value.
    // Observe native calls unchanged and reject such source automation, even
    // when scheduled before start. Gain fades/muting are not source parameters.
    for (const method of ['setValueAtTime', 'linearRampToValueAtTime', 'exponentialRampToValueAtTime',
      'setTargetAtTime', 'setValueCurveAtTime']) {
      try {
        const descriptor = Object.getOwnPropertyDescriptor(host.AudioParam.prototype, method);
        if (!descriptor || typeof descriptor.value !== 'function') throw new Error('Unobservable AudioParam method: ' + method);
        Object.defineProperty(host.AudioParam.prototype, method, { ...descriptor, value: function (...args) {
          const result = Reflect.apply(descriptor.value, this, args);
          try { recordParameterAutomation(this, method); } catch (error) { fail(error); }
          return result;
        } });
      } catch (error) { fail(error); }
    }
  }
  function nodeId(node) {
    if (!nodeIds.has(node)) {
      nodeIds.set(node, nodes.length + 1);
      nodes.push({ id: nodes.length + 1, kind: node.constructor.name, node });
    }
    return nodeIds.get(node);
  }
  function registerContext(ctx) {
    if (!contextIds.has(ctx)) {
      const id = contexts.length + 1;
      contextIds.set(ctx, id);
      const entry = { id, ctx, destination: nodeId(ctx.destination), terminals: [], samples: [],
        stream: null, analyser: null, recorder: null, chunks: [] };
      contexts.push(entry);
    }
    return contexts[contextIds.get(ctx) - 1];
  }
  function contextFor(ctx) {
    const entry = registerContext(ctx);
    // Unused contexts count too, but observation creates no nodes until the
    // application actually connects its output or starts a real source.
    if (!entry.analyser) {
      entry.stream = ctx.createMediaStreamDestination();
      entry.analyser = ctx.createAnalyser();
      entry.analyser.fftSize = 2048;
      entry.data = new Float32Array(entry.analyser.fftSize);
    }
    return entry;
  }
  const observedConstructors = new WeakMap();
  for (const name of ['AudioContext', 'webkitAudioContext']) {
    const Constructor = host[name];
    if (typeof Constructor !== 'function') continue;
    try {
      if (!observedConstructors.has(Constructor)) {
        observedConstructors.set(Constructor, new Proxy(Constructor, {
          construct(target, args, newTarget) {
            // Keep native construction, options, subclassing and exceptions.
            // Never call resume/start or create a substitute AudioContext.
            const ctx = Reflect.construct(target, args, newTarget);
            try { registerContext(ctx); } catch (error) { fail(error); }
            return ctx;
          }
        }));
      }
      const observed = observedConstructors.get(Constructor);
      if (!Reflect.set(host, name, observed) || host[name] !== observed) {
        throw new Error('Cannot observe public AudioContext constructor: ' + name);
      }
      // Preserve the usual ctx.constructor === window.AudioContext identity,
      // and observe construction through that public alias as well.
      if (Constructor.prototype.constructor === Constructor &&
          (!Reflect.set(Constructor.prototype, 'constructor', observed) || Constructor.prototype.constructor !== observed)) {
        throw new Error('Cannot observe AudioContext prototype constructor: ' + name);
      }
    } catch (error) { fail(error); }
  }
  function terminalKey(source, output, input) { return `${nodeId(source)}:${output}:${input}`; }
  function connectedPath(sourceId, destinationId, requireNonzeroGains = false) {
    const queue = [[sourceId]], seen = new Set();
    while (queue.length) {
      const path = queue.shift(), last = path[path.length - 1];
      if (last === destinationId) return path;
      if (seen.has(last)) continue;
      const node = nodes[last - 1].node;
      if (requireNonzeroGains && node.constructor.name === 'GainNode' && node.gain.value <= 1e-6) continue;
      seen.add(last);
      for (const edge of edges) if (edge.active && edge.from === last) queue.push([...path, edge.to]);
    }
    return null;
  }
  host.AudioNode.prototype.connect = function (...args) {
    const result = Reflect.apply(originalConnect, this, args); // Preserve the actual edge and API return.
    try {
      const [destination, output = 0, input = 0] = args;
      if (host.AudioParam && destination instanceof host.AudioParam) {
        // Audio-rate modulation need not appear in AudioParam.value. Record
        // it before/after source start; only rate/detune uses fail acceptance.
        recordParameterAutomation(destination, 'audio_input');
        return result;
      }
      if (!destination || !destination.context) return result; // AudioParam is not a graph node.
      const from = nodeId(this), to = nodeId(destination);
      if (!edges.some(edge => edge.active && edge.from === from && edge.to === to && edge.output === output && edge.input === input)) {
        edges.push({ from, to, output, input, active: true, wall_ms: now() });
      }
      if (destination === this.context.destination) {
        const entry = contextFor(this.context), key = terminalKey(this, output, input);
        if (!allowedTerminals.has(this.constructor.name) || output !== 0 || input !== 0) {
          throw new Error('Unknown terminal audio graph: ' + this.constructor.name + ':' + output + ':' + input);
        }
        const existing = entry.terminals.find(item => item.key === key && item.active);
        if (existing) { existing.duplicate_connect_calls++; return result; }
        // Original methods bypass this observer. Both taps are in the SAME context,
        // post-mute, and leave the genuine destination/speaker edge untouched.
        Reflect.apply(originalConnect, this, [entry.stream, output, 0]);
        Reflect.apply(originalConnect, this, [entry.analyser, output, 0]);
        entry.terminals.push({ key, source: from, output, input, kind: this.constructor.name,
          active: true, mirror_count: 1, duplicate_connect_calls: 0, connected_ms: now() });
      }
    } catch (error) { fail(error); }
    return result;
  };
  host.AudioNode.prototype.disconnect = function (...args) {
    const result = Reflect.apply(originalDisconnect, this, args);
    try {
      const from = nodeId(this), destination = args[0];
      const matches = edge => !args.length || (typeof destination === 'number' ? edge.output === destination :
        edge.to === nodeId(destination) && (args.length < 2 || edge.output === args[1]) && (args.length < 3 || edge.input === args[2]));
      for (const edge of edges) if (edge.active && edge.from === from && matches(edge)) edge.active = false;
      const entry = contextIds.has(this.context) && contexts[contextIds.get(this.context) - 1];
      if (entry) for (const terminal of entry.terminals) {
        if (!terminal.active || terminal.source !== from || !matches({ to: entry.destination, output: terminal.output, input: terminal.input })) continue;
        // No-argument / numeric overload already removed our taps too.
        if (args.length && typeof destination !== 'number') {
          Reflect.apply(originalDisconnect, this, [entry.stream, terminal.output, 0]);
          Reflect.apply(originalDisconnect, this, [entry.analyser, terminal.output, 0]);
        }
        terminal.active = false;
        terminal.disconnected_ms = now();
      }
    } catch (error) { fail(error); }
    return result;
  };
  function fingerprint(buffer) {
    let hash = 2166136261, peak = 0;
    // Stable diagnostic fingerprint of real source PCM; not an asset SHA.
    for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
      const data = buffer.getChannelData(channel), step = Math.max(1, Math.floor(data.length / 2048));
      for (let index = 0; index < data.length; index += step) {
        peak = Math.max(peak, Math.abs(data[index]));
        const sample = Math.round(data[index] * 8388607);
        hash = Math.imul(hash ^ sample, 16777619) >>> 0;
      }
    }
    return { pcm_fingerprint: hash.toString(16).padStart(8, '0'), pcm_peak: peak };
  }
  host.AudioBufferSourceNode.prototype.start = function (...args) {
    const result = Reflect.apply(originalStart, this, args);
    try {
      const entry = contextFor(this.context), buffer = this.buffer;
      if (!buffer) throw new Error('Started source has no observable PCM buffer');
      const name = Object.keys(expected).find(key => Math.abs(expected[key] - buffer.duration) < .005) || 'unknown';
      const rate = this.playbackRate.value;
      const startTime = Math.max(this.context.currentTime, args[0] || 0), offset = args[1] || 0;
      if (name === 'unknown' || !Number.isFinite(rate) || Math.abs(rate - 1) > .0001 || this.detune.value !== 0) {
        throw new Error('Unknown source duration/rate/detune: ' + buffer.duration + '/' + rate + '/' + this.detune.value);
      }
      const item = { id: nodeId(this), context: entry.id, name, duration: buffer.duration,
        frames: buffer.length, sample_rate: buffer.sampleRate, channels: buffer.numberOfChannels,
        wall_ms: now(), context_time: this.context.currentTime, scheduled_start: startTime, offset, rate,
        ...sourceMetadata(this), requested_duration: args[2] === undefined ? null : args[2],
        mutations: [], parameter_automation: [],
        planned_end: this.loop ? null : startTime + Math.min(args[2] === undefined ? Infinity : args[2], buffer.duration - offset) / rate,
        path_at_start: connectedPath(nodeId(this), entry.destination),
        nonzero_gain_path_at_start: connectedPath(nodeId(this), entry.destination, true), ...fingerprint(buffer) };
      starts.push(item);
      observedSources.set(this, { item, last: sourceMetadata(this) });
      for (const [field, parameter] of [['rate', this.playbackRate], ['detune', this.detune]]) {
        sourceParameters.set(parameter, { source: this, item, field });
        for (const event of parameterAutomation.get(parameter) || []) {
          item.parameter_automation.push({ field, ...event });
          fail('Uncertifiable source parameter automation: ' + item.id + '/' + field + '/' + event.method);
        }
      }
      this.addEventListener('ended', () => { item.ended_context_time = this.context.currentTime; item.ended_wall_ms = now(); });
    } catch (error) { fail(error); }
    return result;
  };
  host.AudioBufferSourceNode.prototype.stop = function (...args) {
    const result = Reflect.apply(originalStop, this, args);
    const item = starts.find(source => source.id === nodeId(this));
    if (item) item.stopped_context_time = Math.max(this.context.currentTime, args[0] || 0);
    return result;
  };
  const voiceEnd = item => Math.min(...[item.planned_end, item.stopped_context_time, item.ended_context_time].filter(value => value !== undefined && value !== null));
  const alive = (item, entry) => item.context === entry.id && item.scheduled_start <= entry.ctx.currentTime &&
    voiceEnd(item) > entry.ctx.currentTime && !!connectedPath(item.id, entry.destination);
  function sample() {
    for (const entry of contexts) {
      if (!entry.analyser) continue; // No invented meter evidence for an unused context.
      try {
        const source_metadata = starts.filter(item => item.context === entry.id).map(item => {
          const source = nodes[item.id - 1].node;
          auditSource(source, 'meter sample');
          return { id: item.id, ...sourceMetadata(source) };
        });
        // Raw values of the genuine active destination gains. A suspended
        // analyser retains its last PCM window; never manufacture silent PCM
        // from context state or these gain values.
        const terminal_gain_values = entry.terminals.filter(item => item.active && item.kind === 'GainNode')
          .map(item => ({ source: item.source, value: nodes[item.source - 1].node.gain.value }));
        entry.analyser.getFloatTimeDomainData(entry.data);
        let square = 0, peak = 0, clipped = 0;
        for (const value of entry.data) { square += value * value; peak = Math.max(peak, Math.abs(value)); if (Math.abs(value) >= .999) clipped++; }
        entry.samples.push({ wall_ms: now(), context_time: entry.ctx.currentTime, state: entry.ctx.state,
          rms: Math.sqrt(square / entry.data.length), peak, clipped_fraction: clipped / entry.data.length, source_metadata, terminal_gain_values,
          active_music: starts.filter(item => item.name === 'music' && alive(item, entry)).length,
          active_cues: starts.filter(item => item.name !== 'music' && alive(item, entry) &&
            connectedPath(item.id, entry.destination, true)).map(item => item.id) });
      } catch (error) { fail(error); }
    }
  }
  const timer = host.setInterval(sample, 100);
  for (const type of ['pointerdown', 'touchstart', 'mousedown', 'keydown']) host.addEventListener(type, event => {
    gestures.push({ type, trusted: event.isTrusted, key: event.key || null, wall_ms: now(),
      x: event.clientX === undefined ? null : event.clientX, y: event.clientY === undefined ? null : event.clientY });
  }, true);
  function snapshot() {
    sample();
    return { schema: 1, errors: [...errors], wall_ms: now(), gestures: [...gestures], marks: [...marks],
      user_activation: { active: host.navigator.userActivation.isActive, has_been_active: host.navigator.userActivation.hasBeenActive },
      nodes: nodes.map(({ id, kind }) => ({ id, kind })), edges: edges.map(edge => ({ ...edge })),
      starts: starts.map(item => ({ ...item, mutations: item.mutations.map(value => ({ ...value })),
        parameter_automation: item.parameter_automation.map(value => ({ ...value })) })),
      contexts: contexts.map(entry => ({ id: entry.id, state: entry.ctx.state, context_time: entry.ctx.currentTime,
        sample_rate: entry.ctx.sampleRate, destination: entry.destination, terminals: entry.terminals.map(item => ({ ...item })), samples: [...entry.samples] })) };
  }
  host.__tidalAudio = Object.freeze({
    snapshot,
    mark(name) { const item = { name, wall_ms: now(), context_times: contexts.map(entry => ({ id: entry.id, time: entry.ctx.currentTime })) }; marks.push(item); return item; },
    startRecording() {
      if (errors.length || contexts.length !== 1 || !contexts[0].terminals.some(item => item.active)) throw new Error('No unambiguous observed live output graph');
      const entry = contexts[0];
      if (entry.recorder) throw new Error('Recording already started');
      const mimeType = 'audio/webm;codecs=opus';
      if (!host.MediaRecorder.isTypeSupported(mimeType)) throw new Error('Opus WebM MediaRecorder unavailable');
      const recorder = entry.recorder = new host.MediaRecorder(entry.stream.stream, { mimeType, audioBitsPerSecond: 128000 });
      recorder.addEventListener('dataavailable', event => { if (event.data.size) entry.chunks.push(event.data); });
      recorder.addEventListener('error', event => fail(event.error || 'MediaRecorder error'));
      recorder.start(1000);
      entry.record_started_ms = now();
      return { mime_type: recorder.mimeType, started_ms: entry.record_started_ms, audio_tracks: entry.stream.stream.getAudioTracks().length,
        graph: 'public original destination edges mirrored in the same AudioContext; no microphone, offline mix or context resume' };
    },
    async finishRecording() {
      const entry = contexts[0], recorder = entry && entry.recorder;
      if (!recorder || recorder.state !== 'recording') throw new Error('No live recording to finish');
      await new Promise((resolve, reject) => { recorder.addEventListener('stop', resolve, { once: true }); recorder.addEventListener('error', reject, { once: true }); recorder.stop(); });
      const blob = new host.Blob(entry.chunks, { type: recorder.mimeType });
      const bytes = new Uint8Array(await blob.arrayBuffer());
      if (bytes.length < 1024) throw new Error('Live audio recording is empty');
      let binary = '';
      for (let offset = 0; offset < bytes.length; offset += 32768) binary += String.fromCharCode(...bytes.subarray(offset, offset + 32768));
      host.clearInterval(timer);
      return { base64: host.btoa(binary), bytes: bytes.length, mime_type: recorder.mimeType,
        wall_seconds: (now() - entry.record_started_ms) / 1000, snapshot: snapshot() };
    }
  });
  return host.__tidalAudio;
});
