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
  const gainEvents = [], graphEvents = [], gainParameters = new WeakMap();
  let historyOverflow = false;
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
  function history(list, item) {
    if (list.length >= 4096) {
      if (!historyOverflow) fail('Bounded audio graph/gain history overflow');
      historyOverflow = true;
      return;
    }
    list.push({ sequence: list.length + 1, ...item });
  }
  function gainEvent(node, method, args = []) {
    history(gainEvents, { node: nodeIds.get(node), context: contextIds.get(node.context), method,
      args: args.map(value => ArrayBuffer.isView(value) ? Array.from(value).slice(0, 4097) : value),
      value: node.gain.value, context_time: node.context.currentTime, wall_ms: now() });
    if (args.some(value => ArrayBuffer.isView(value) && value.length > 4096)) {
      if (!historyOverflow) fail('Bounded audio gain automation history overflow');
      historyOverflow = true;
    }
  }
  function graphEvent(event, edge, context) {
    history(graphEvents, { event, from: edge.from, to: edge.to, output: edge.output, input: edge.input,
      context: contextIds.get(context), context_time: context.currentTime, wall_ms: now() });
  }
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
  function recordParameterAutomation(parameter, method, args = []) {
    const history = parameterAutomation.get(parameter) || [];
    if (history.length < 4096) history.push({ method, wall_ms: now() });
    else {
      if (!historyOverflow) fail('Bounded audio parameter history overflow');
      historyOverflow = true;
    }
    parameterAutomation.set(parameter, history);
    const gain = gainParameters.get(parameter);
    if (gain) gainEvent(gain, method, args);
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
        try { inspect(this, value); } catch (error) { fail(error); }
        return result;
      } });
    } catch (error) { fail(error); }
  }
  for (const property of ['loop', 'loopStart', 'loopEnd']) {
    observeSetter(host.AudioBufferSourceNode.prototype, property, source => auditSource(source, property + ' setter'));
  }
  if (!host.AudioParam) fail('AudioParam observation unavailable');
  else {
    observeSetter(host.AudioParam.prototype, 'value', (parameter, value) => {
      const gain = gainParameters.get(parameter);
      if (gain) gainEvent(gain, 'value', [value]);
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
          try { recordParameterAutomation(this, method, args); } catch (error) { fail(error); }
          return result;
        } });
      } catch (error) { fail(error); }
    }
    for (const method of ['cancelScheduledValues', 'cancelAndHoldAtTime']) {
      const descriptor = Object.getOwnPropertyDescriptor(host.AudioParam.prototype, method);
      if (!descriptor || typeof descriptor.value !== 'function') continue;
      Object.defineProperty(host.AudioParam.prototype, method, { ...descriptor, value: function (...args) {
        const result = Reflect.apply(descriptor.value, this, args);
        try { const gain = gainParameters.get(this); if (gain) gainEvent(gain, method, args); } catch (error) { fail(error); }
        return result;
      } });
    }
  }
  function nodeId(node) {
    if (!nodeIds.has(node)) {
      nodeIds.set(node, nodes.length + 1);
      nodes.push({ id: nodes.length + 1, kind: node.constructor.name, node });
      if (node.constructor.name === 'GainNode' && node.gain) {
        gainParameters.set(node.gain, node);
        gainEvent(node, 'initial');
      }
    }
    return nodeIds.get(node);
  }
  function registerContext(ctx) {
    if (!contextIds.has(ctx)) {
      const id = contexts.length + 1;
      contextIds.set(ctx, id);
      const entry = { id, ctx, destination: nodeId(ctx.destination), terminals: [], samples: [],
        stream: null, analyser: null, recorder: null, chunks: [], meters: [], moduleReady: null, moduleLoaded: false };
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
      installMeters(entry);
    }
    return entry;
  }
  function meterFailure(meter, reason, overflow = false) {
    const message = String(reason && reason.message || reason);
    if (meter.status !== 'failed') fail('Audio-thread ' + meter.tap_id + ': ' + message);
    meter.status = 'failed';
    meter.overflow ||= overflow;
    if (meter.errors.length < 16) meter.errors.push(message);
    for (const pending of meter.pending.values()) {
      host.clearTimeout(pending.timer);
      pending.reject(new Error(message));
    }
    meter.pending.clear();
  }
  function meterMessage(entry, meter, message) {
    if (meter.status === 'failed') return;
    try {
      if (!message || message.schema !== 1 || message.tap_id !== meter.tap_id || message.sample_rate !== entry.ctx.sampleRate) {
        throw new Error('Unknown audio-thread receipt');
      }
      if (message.type === 'error') {
        // Preserve the first actual failure before permanently rejecting this tap.
        // Delivery time/context is explicitly not the worklet processing time.
        meter.failure_receipt = { tap_id: meter.tap_id, source: meter.source, role: meter.role,
          error: String(message.error), sequence: message.sequence,
          processed_end_frame: message.processed_end_frame,
          diagnostic: message.diagnostic ? Object.fromEntries([
            'expected_frame', 'actual_frame', 'delta_frames', 'quantum_frames', 'input_channels',
            'previous_had_input', 'segment', 'partial_frames', 'pending_no_input_start', 'pending_no_input_end'
          ].map(key => [key, message.diagnostic[key]])) : null,
          delivery_ms: now(), delivery_context_time: entry.ctx.currentTime,
          delivery_context_state: entry.ctx.state,
          last_graph_event_sequence: graphEvents.length, last_gain_event_sequence: gainEvents.length };
        meterFailure(meter, message.error, message.overflow === true); return;
      }
      if (message.type === 'barrier') {
        const pending = meter.pending.get(message.id);
        if (!pending || message.sequence !== meter.sequence ||
            !(message.processed_end_frame === null || Number.isSafeInteger(message.processed_end_frame) && message.processed_end_frame >= 0) ||
            !Number.isSafeInteger(message.partial_frames) || message.partial_frames < 0 || message.partial_frames >= meter.window_frames ||
            message.processed_end_frame === null && (message.sequence !== 0 || message.partial_frames !== 0) ||
            meter.last_end_frame !== null && message.processed_end_frame !== meter.last_end_frame + message.partial_frames) {
          throw new Error('Invalid audio-thread barrier');
        }
        const receipt = { ...message, context: entry.id, delivery_ms: now() };
        delete receipt.type;
        meter.last_barrier = receipt;
        meter.pending.delete(message.id);
        host.clearTimeout(pending.timer);
        pending.resolve({ ...receipt });
        return;
      }
      if (!['window', 'gap'].includes(message.type) || message.sequence !== meter.sequence + 1 ||
          !Number.isSafeInteger(message.start_frame) || message.start_frame < 0 ||
          !Number.isSafeInteger(message.end_frame) || message.end_frame <= message.start_frame ||
          message.frames !== message.end_frame - message.start_frame ||
          meter.last_end_frame !== null && message.start_frame !== meter.last_end_frame) {
        throw new Error('Discontinuous or invalid audio-thread receipt');
      }
      const list = message.type === 'window' ? meter.windows : meter.gaps;
      if (list.length >= meter.max_windows) { meterFailure(meter, 'Main-thread evidence overflow', true); return; }
      if (message.type === 'window') {
        if (!Number.isSafeInteger(message.channels) || message.channels < 1 || message.channels > 32 ||
            message.samples !== message.frames * message.channels || message.frames > meter.window_frames ||
            message.complete !== (message.frames === meter.window_frames) ||
            !Number.isSafeInteger(message.segment) || message.segment < 1 ||
            !['rms', 'peak', 'square_sum', 'clipped_fraction'].every(key => Number.isFinite(message[key]) && message[key] >= 0) ||
            !Number.isSafeInteger(message.clipped_samples) || message.clipped_samples < 0 || message.clipped_samples > message.samples ||
            !['channel_samples', 'channel_square_sum', 'channel_rms', 'channel_peak', 'channel_clipped_samples'].every(key =>
              Array.isArray(message[key]) && message[key].length === message.channels && message[key].every(value => Number.isFinite(value) && value >= 0)) ||
            !message.channel_samples.every(value => value === message.frames)) throw new Error('Invalid actual PCM aggregate');
        const near = (left, right) => Math.abs(left - right) <= 1e-9 * Math.max(1, Math.abs(left), Math.abs(right));
        if (!near(message.channel_square_sum.reduce((sum, value) => sum + value, 0), message.square_sum) ||
            !near(message.rms * message.rms * message.samples, message.square_sum) ||
            !near(Math.max(...message.channel_peak), message.peak) || message.rms > message.peak + 1e-9 ||
            message.channel_clipped_samples.reduce((sum, value) => sum + value, 0) !== message.clipped_samples ||
            !near(message.clipped_fraction, message.clipped_samples / message.samples) ||
            message.channel_clipped_samples.some(value => !Number.isSafeInteger(value) || value > message.frames) ||
            message.channel_rms.some((value, channel) => value > message.channel_peak[channel] + 1e-9 ||
              !near(value * value * message.frames, message.channel_square_sum[channel]))) throw new Error('Inconsistent actual PCM aggregate');
      } else if (message.reason !== 'no-input' || !Number.isSafeInteger(message.segment_before) || message.segment_before < 0) {
        throw new Error('Invalid audio-thread no-input interval');
      }
      const receipt = { ...message, delivery_ms: now() };
      delete receipt.type;
      list.push(receipt);
      meter.sequence = message.sequence;
      meter.last_end_frame = message.end_frame;
      meter.node.port.postMessage({ type: 'ack', sequence: message.sequence });
    } catch (error) { meterFailure(meter, error); }
  }
  function createMeter(entry, source = null) {
    const meter = { schema: 1, tap_id: source === null ? 'mix:' + entry.id : 'node:' + source,
      source, role: source === null ? 'mix' : 'bus', status: 'loading', sample_rate: entry.ctx.sampleRate,
      window_frames: Math.round(entry.ctx.sampleRate / 10), max_windows: 12000, max_pending_messages: 256,
      overflow: false, errors: [], failure_receipt: null, windows: [], gaps: [], sequence: 0, last_end_frame: null,
      last_barrier: null, pending: new Map(), barrierId: 0, graph: null, node: null };
    entry.meters.push(meter);
    try {
      const node = meter.node = new host.AudioWorkletNode(entry.ctx, 'tidal-audio-meter-v1', {
        numberOfInputs: 1, numberOfOutputs: 1, outputChannelCount: [1], channelCountMode: 'max', channelInterpretation: 'discrete',
        processorOptions: { tapId: meter.tap_id, windowFrames: meter.window_frames,
          maxWindows: meter.max_windows, maxPendingMessages: meter.max_pending_messages }
      });
      node.port.onmessage = event => meterMessage(entry, meter, event.data);
      node.addEventListener('processorerror', () => meterFailure(meter, 'AudioWorklet processor error'));
      const input = source === null ? entry.analyser : nodes[source - 1].node;
      // Bypass only our observer, never the original WebAudio graph. The meter
      // returns zeros into the already-existing stream; no new speaker edge.
      Reflect.apply(originalConnect, input, [node, 0, 0]);
      Reflect.apply(originalConnect, node, [entry.stream, 0, 0]);
      meter.graph = { source, analyser: source === null ? nodeId(entry.analyser) : null,
        meter: nodeId(node), stream: nodeId(entry.stream), destination: entry.destination,
        input_active: true, output: 'zero-only', terminal_sources: entry.terminals.filter(item => item.active).map(item => item.source) };
      meter.status = 'ready';
      meter.ready_wall_ms = now();
      meter.ready_context_time = entry.ctx.currentTime;
    } catch (error) { meterFailure(meter, error); }
    return meter;
  }
  function ensureBusMeters(entry) {
    if (!entry.moduleLoaded) return;
    const terminals = new Set(entry.terminals.filter(item => item.active).map(item => item.source));
    const sources = [...new Set(edges.filter(edge => edge.active && terminals.has(edge.to) && edge.output === 0 && edge.input === 0 &&
      nodes[edge.from - 1].kind === 'GainNode' && !terminals.has(edge.from)).map(edge => edge.from))];
    if (sources.length > 8) {
      if (!entry.busOverflow) fail('Too many observed upstream gain buses');
      entry.busOverflow = true;
      return;
    }
    for (const source of sources) {
      let meter = entry.meters.find(item => item.source === source);
      if (!meter) {
        if (entry.meters.length >= 9) {
          if (!entry.busOverflow) fail('Bounded observed gain-bus meter overflow');
          entry.busOverflow = true;
          return;
        }
        meter = createMeter(entry, source);
      }
      else if (meter.status === 'ready' && !meter.graph.input_active) {
        Reflect.apply(originalConnect, nodes[source - 1].node, [meter.node, 0, 0]);
        meter.graph.input_active = true;
      }
    }
    for (const meter of entry.meters) if (meter.graph) meter.graph.terminal_sources = [...terminals];
  }
  function installMeters(entry) {
    if (entry.moduleReady) return;
    let url;
    try {
      if (typeof host.__tidalAudioWorkletSource !== 'string' || !host.__tidalAudioWorkletSource.trim() ||
          !entry.ctx.audioWorklet || typeof host.AudioWorkletNode !== 'function') throw new Error('Audio-thread source/API unavailable');
      url = host.URL.createObjectURL(new host.Blob([host.__tidalAudioWorkletSource], { type: 'application/javascript' }));
      entry.moduleReady = entry.ctx.audioWorklet.addModule(url).then(() => {
        entry.moduleLoaded = true;
        createMeter(entry);
        ensureBusMeters(entry);
      }).catch(error => { entry.moduleError = String(error && error.message || error); fail('Audio-thread module: ' + entry.moduleError); })
        .finally(() => host.URL.revokeObjectURL(url));
    } catch (error) {
      if (url) host.URL.revokeObjectURL(url);
      entry.moduleError = String(error && error.message || error);
      fail('Audio-thread module: ' + entry.moduleError);
      entry.moduleReady = Promise.resolve();
    }
  }
  function meterSnapshot(meter) {
    const copy = item => Object.fromEntries(Object.entries(item).map(([key, value]) => [key, Array.isArray(value) ? [...value] : value]));
    return { schema: meter.schema, tap_id: meter.tap_id, source: meter.source, role: meter.role, status: meter.status,
      sample_rate: meter.sample_rate, window_frames: meter.window_frames, max_windows: meter.max_windows,
      max_pending_messages: meter.max_pending_messages, overflow: meter.overflow, errors: [...meter.errors],
      sequence: meter.sequence, received_windows: meter.windows.length, received_gaps: meter.gaps.length,
      ready_wall_ms: meter.ready_wall_ms, ready_context_time: meter.ready_context_time,
      graph: meter.graph ? copy(meter.graph) : null, windows: meter.windows.map(copy), gaps: meter.gaps.map(copy),
      last_barrier: meter.last_barrier ? { ...meter.last_barrier } : null,
      failure_receipt: meter.failure_receipt ? { ...meter.failure_receipt,
        diagnostic: meter.failure_receipt.diagnostic ? { ...meter.failure_receipt.diagnostic } : null } : null };
  }
  async function ready() {
    if (contexts.length !== 1 || !contexts[0].analyser) throw new Error('No unambiguous observed live output graph');
    const entry = contexts[0];
    await entry.moduleReady;
    ensureBusMeters(entry);
    if (errors.length || !entry.terminals.some(item => item.active) || !entry.meters.length || entry.meters.some(item => item.status !== 'ready')) {
      throw new Error('Audio-thread meters are not ready: ' + (entry.moduleError || errors.join('; ')));
    }
    return { context: entry.id, streams: entry.meters.map(meter => ({ tap_id: meter.tap_id, source: meter.source, role: meter.role })) };
  }
  async function flush() {
    await ready();
    const entry = contexts[0];
    if (entry.ctx.state !== 'running') throw new Error('Audio-thread barrier requires an already-running context');
    return Promise.all(entry.meters.map(meter => new Promise((resolve, reject) => {
      if (meter.pending.size >= 8) { meterFailure(meter, 'Audio-thread barrier overflow', true); reject(new Error('Audio-thread barrier overflow')); return; }
      const id = ++meter.barrierId;
      const timer = host.setTimeout(() => meterFailure(meter, 'Audio-thread barrier timed out'), 10000);
      meter.pending.set(id, { resolve, reject, timer });
      meter.node.port.postMessage({ type: 'barrier', id });
    })));
  }
  const observedConstructors = new WeakMap();
  for (const name of ['AudioContext', 'webkitAudioContext']) {
    const Constructor = host[name];
    if (typeof Constructor !== 'function') continue;
    try {
      if (!observedConstructors.has(Constructor)) {
        const createGain = Constructor.prototype.createGain;
        if (typeof createGain === 'function') Object.defineProperty(Constructor.prototype, 'createGain', {
          configurable: true, writable: true, value: function (...args) {
            const node = Reflect.apply(createGain, this, args);
            try { registerContext(this); nodeId(node); } catch (error) { fail(error); }
            return node;
          }
        });
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
  if (typeof host.GainNode === 'function') {
    const Constructor = host.GainNode;
    try {
      const observed = new Proxy(Constructor, { construct(target, args, newTarget) {
        const node = Reflect.construct(target, args, newTarget);
        try { registerContext(node.context); nodeId(node); } catch (error) { fail(error); }
        return node;
      } });
      if (!Reflect.set(host, 'GainNode', observed) || host.GainNode !== observed) throw new Error('Cannot observe public GainNode constructor');
      if (Constructor.prototype.constructor === Constructor &&
          (!Reflect.set(Constructor.prototype, 'constructor', observed) || Constructor.prototype.constructor !== observed)) {
        throw new Error('Cannot observe GainNode prototype constructor');
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
      registerContext(this.context);
      const from = nodeId(this), to = nodeId(destination);
      if (!edges.some(edge => edge.active && edge.from === from && edge.to === to && edge.output === output && edge.input === input)) {
        const edge = { from, to, output, input, active: true, wall_ms: now(), context: contextIds.get(this.context), context_time: this.context.currentTime };
        edges.push(edge);
        graphEvent('connect', edge, this.context);
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
      const entry = contexts[contextIds.get(this.context) - 1];
      ensureBusMeters(entry);
    } catch (error) { fail(error); }
    return result;
  };
  host.AudioNode.prototype.disconnect = function (...args) {
    const result = Reflect.apply(originalDisconnect, this, args);
    try {
      const from = nodeId(this), destination = args[0];
      const matches = edge => !args.length || (typeof destination === 'number' ? edge.output === destination :
        edge.to === nodeId(destination) && (args.length < 2 || edge.output === args[1]) && (args.length < 3 || edge.input === args[2]));
      for (const edge of edges) if (edge.active && edge.from === from && matches(edge)) {
        edge.active = false;
        edge.disconnected_context_time = this.context.currentTime;
        edge.disconnected_ms = now();
        graphEvent('disconnect', edge, this.context);
      }
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
      if (entry) for (const meter of entry.meters) {
        if (meter.source === null || !meter.graph || !meter.graph.input_active || connectedPath(meter.source, entry.destination)) continue;
        // Broad disconnect on this exact source already removed its observer
        // edge. A targeted downstream disconnect requires removing that tap.
        if (meter.source !== from || args.length && typeof destination !== 'number') {
          Reflect.apply(originalDisconnect, nodes[meter.source - 1].node, [meter.node, 0, 0]);
        }
        meter.graph.input_active = false;
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
      if (!entry.moduleLoaded || !entry.meters.length || entry.meters.some(meter => meter.status !== 'ready')) fail('Real source started before audio-thread meters were ready');
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
        meter_taps: entry.meters.filter(meter => meter.source === null ||
          (connectedPath(nodeId(this), entry.destination) || []).includes(meter.source))
          .map(meter => ({ tap_id: meter.tap_id, source: meter.source, role: meter.role })),
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
      gain_events: gainEvents.map(item => ({ ...item, args: item.args.map(value => Array.isArray(value) ? [...value] : value) })),
      graph_events: graphEvents.map(item => ({ ...item })), history_overflow: historyOverflow,
      user_activation: { active: host.navigator.userActivation.isActive, has_been_active: host.navigator.userActivation.hasBeenActive },
      nodes: nodes.map(({ id, kind }) => ({ id, kind })), edges: edges.map(edge => ({ ...edge })),
      starts: starts.map(item => ({ ...item, mutations: item.mutations.map(value => ({ ...value })),
        parameter_automation: item.parameter_automation.map(value => ({ ...value })) })),
      contexts: contexts.map(entry => {
        const streams = entry.meters.map(meterSnapshot), mix = streams.find(item => item.role === 'mix');
        return { id: entry.id, state: entry.ctx.state, context_time: entry.ctx.currentTime,
          sample_rate: entry.ctx.sampleRate, destination: entry.destination, terminals: entry.terminals.map(item => ({ ...item })), samples: [...entry.samples],
          audio_thread: { ...(mix || { schema: 1, status: entry.moduleError ? 'failed' : entry.analyser ? 'loading' : 'not-installed',
            windows: [], gaps: [], errors: entry.moduleError ? [entry.moduleError] : [], overflow: false }), streams } };
      }) };
  }
  host.__tidalAudio = Object.freeze({
    snapshot, ready, flush,
    // Read-only bounded liveness diagnostics; never substitutes for PCM evidence.
    health: () => ({ errors: [...errors], history_overflow: historyOverflow,
      contexts: contexts.map(entry => ({ id: entry.id, state: entry.ctx.state,
        context_time: entry.ctx.currentTime, meters: entry.meters.map(meter => ({
          tap_id: meter.tap_id, status: meter.status, overflow: meter.overflow })) })) }),
    mark(name) { const item = { name, wall_ms: now(), context_times: contexts.map(entry => ({ id: entry.id, time: entry.ctx.currentTime })) }; marks.push(item); return item; },
    startRecording() {
      if (errors.length || contexts.length !== 1 || !contexts[0].terminals.some(item => item.active)) throw new Error('No unambiguous observed live output graph');
      const entry = contexts[0];
      if (!entry.moduleLoaded || !entry.meters.length || entry.meters.some(meter => meter.status !== 'ready')) throw new Error('Audio-thread meters are not ready');
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
