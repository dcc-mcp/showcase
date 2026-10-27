/* Contract checks against the actual production JS constant.
 * This controlled in-memory transaction fixture is NOT real IndexedDB,
 * a browser refresh/reopen test, a Godot run, or proof of durable storage.
 */
'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { TextEncoder } = require('node:util');

const sourcePath = path.join(__dirname, '../overlay/fifty/view/indexeddb_source.gd');
const source = fs.readFileSync(sourcePath, 'utf8');
const match = source.match(/const SCRIPT := """([\s\S]*?)"""/);
assert.ok(match, 'The real GDScript JS constant must be present');
const script = match[1];
const KEY = 'stairkeep-fifty-slice/v1/classic_restart/first-chapter';
const PRACTICE = 'stairkeep-fifty-slice/v1/practice_checkpoint/first-chapter';
const DB_NAME = 'stairkeep-chapter-one-storage-v1';
const STORE = 'slots';

class Clock {
  constructor() { this.now = 0; this.serial = 0; this.queue = []; }
  setTimeout(fn, delay = 0) {
    const id = ++this.serial;
    this.queue.push({ id, at: this.now + Math.max(0, Number(delay) || 0), fn });
    return id;
  }
  clearTimeout(id) { this.queue = this.queue.filter(item => item.id !== id); }
  next() {
    this.queue.sort((a, b) => a.at - b.at || a.id - b.id);
    if (!this.queue.length || this.queue[0].at > this.now) return false;
    this.queue.shift().fn();
    return true;
  }
  drain() {
    let steps = 0;
    while (this.next()) assert.ok(++steps < 1000, 'Fixture event loop stalled');
  }
  advance(ms) { this.now += ms; this.drain(); }
}

function copy(value) { return value === undefined ? undefined : JSON.parse(JSON.stringify(value)); }

function dispatch(object, type, extra = {}) {
  const event = { target: object, preventDefault() { this.defaultPrevented = true; }, ...extra };
  if (typeof object['on' + type] === 'function') object['on' + type](event);
  for (const fn of object.listeners?.[type] || []) fn(event);
}

function fixture(options = {}) {
  const clock = new Clock();
  const values = new Map(Object.entries(options.values || {}));
  const log = [];
  const state = { openRequests: [], transactions: [], closes: 0, opens: 0, writes: 0, strictAttempts: 0, writeCommitted: false, availabilityGetterCalls: 0 };
  let stores = options.storeMissing ? new Set() : new Set([STORE]);
  const database = {
    objectStoreNames: { contains(name) { return stores.has(name); } },
    createObjectStore(name) { stores.add(name); return {}; },
    close() {
      state.closes++;
      if (options.closeThrows) throw Object.assign(new Error('Closing storage failed'), { name: 'InvalidStateError' });
    },
    transaction(names, mode = 'readonly', settings) {
      const requested = Array.isArray(names) ? names : [names];
      assert.deepEqual(Array.from(requested), [STORE], 'Backend must use only its own store');
      assert.ok(stores.has(STORE), 'Missing object store');
      if (settings?.durability === 'strict') {
        state.strictAttempts++;
        if (options.strictUnsupported) throw Object.assign(new TypeError('Unsupported durability option'), { name: 'TypeError' });
      }
      if (options.transactionThrow) throw Object.assign(new Error('Storage disabled'), { name: 'SecurityError' });
      const tx = {
        mode, pending: 0, finished: false, aborted: false, completing: false, error: null,
        staged: new Map(), listeners: {},
        addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); },
        abort() {
          if (this.finished || this.aborted) throw Object.assign(new Error('No active transaction'), { name: 'InvalidStateError' });
          if (options.abortThrows) throw new Error('Abort unavailable');
          this.aborted = true;
          this.staged.clear();
          clock.setTimeout(() => {
            log.push('tx_abort:' + mode);
            dispatch(this, 'abort');
          }, 0);
        },
        objectStore(name) {
          assert.equal(name, STORE);
          const request = (kind, key, value) => {
            assert.ok(!tx.finished && !tx.aborted, 'Request requires active transaction');
            tx.pending++;
            const result = { result: undefined, error: null, listeners: {}, addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); } };
            clock.setTimeout(() => {
              if (tx.aborted || tx.finished) return;
              if (options.requestHang && mode === 'readwrite') return;
              if (options.readbackHang && mode === 'readonly' && state.writeCommitted) return;
              if (kind === 'get') {
                result.result = copy(tx.staged.has(key) ? tx.staged.get(key) : values.get(key));
              } else if (options.quota && mode === 'readwrite') {
                result.error = tx.error = Object.assign(new Error('No space left'), { name: 'QuotaExceededError' });
                log.push('request_error:put');
                dispatch(result, 'error');
                dispatch(tx, 'error');
                if (!tx.aborted) tx.abort();
                return;
              } else {
                if (kind === 'add' && values.has(key)) {
                  result.error = tx.error = Object.assign(new Error('Key exists'), { name: 'ConstraintError' });
                  dispatch(result, 'error');
                  dispatch(tx, 'error');
                  if (!tx.aborted) tx.abort();
                  return;
                }
                tx.staged.set(key, copy(value));
                result.result = key;
                state.writes++;
              }
              log.push('request_success:' + kind + ':' + mode);
              dispatch(result, 'success');
              tx.pending--;
              if (options.abortAfterPutSuccess && kind !== 'get' && !tx.aborted) tx.abort();
              if (options.abortReadback && kind === 'get' && mode === 'readonly' && state.writeCommitted && !tx.aborted) tx.abort();
              tx.maybeComplete();
            }, 0);
            return result;
          };
          return { get(key) { return request('get', key); }, put(value, key) { return request('put', key, value); }, add(value, key) { return request('add', key, value); } };
        },
        maybeComplete() {
          if (this.pending || this.aborted || this.finished || this.completing) return;
          this.completing = true;
          clock.setTimeout(() => {
            if (this.aborted || this.finished) return;
            if (options.commitHang && mode === 'readwrite') { this.completing = false; return; }
            for (const [key, value] of this.staged) values.set(key, copy(value));
            this.finished = true;
            log.push('tx_complete:' + mode);
            if (mode === 'readwrite') state.writeCommitted = true;
            if (mode === 'readwrite' && options.afterWriteCommit) options.afterWriteCommit(values);
            dispatch(this, 'complete');
          }, 0);
        },
      };
      state.transactions.push(tx);
      return tx;
    },
  };
  function open() {
    assert.equal(arguments[0], DB_NAME, 'Backend must use its independent database namespace');
    state.opens++;
    const request = { result: database, error: null };
    request.transaction = { aborted: false, abort() { this.aborted = true; } };
    state.openRequests.push(request);
    const fire = () => {
      if (options.openError) {
        request.error = Object.assign(new Error('Denied'), { name: 'SecurityError' });
        dispatch(request, 'error');
        return;
      }
      if (options.openBlocked) { dispatch(request, 'blocked'); return; }
      if (!stores.size) dispatch(request, 'upgradeneeded', { oldVersion: 0, newVersion: 1 });
      if (!request.transaction.aborted) dispatch(request, 'success');
    };
    request.fire = fire;
    if (!options.openHang) clock.setTimeout(fire, 0);
    return request;
  }
  const global = { console, JSON, Object, Array, String, Number, Boolean, Math, TextEncoder,
    setTimeout: clock.setTimeout.bind(clock), clearTimeout: clock.clearTimeout.bind(clock),
    indexedDB: options.noIndexedDB ? undefined : { open },
  };
  if (options.indexedDBGetterThrows) {
    Object.defineProperty(global, 'indexedDB', {
      get() {
        state.availabilityGetterCalls++;
        throw Object.assign(new Error('Storage access denied'), { name: 'SecurityError' });
      },
    });
  }
  global.window = global;
  // Keep the production root as an ordinary host object, not Node's special
  // context-global proxy: its property getters must retain real exceptions.
  const context = vm.createContext({
    console, TextEncoder,
    setTimeout: global.setTimeout, clearTimeout: global.clearTimeout,
    globalThis: global, window: global,
  });
  vm.runInContext(options.scriptOverride || script, context, { filename: sourcePath });
  const api = global.StairkeepChapterOneStorageV1;
  assert.equal(api?.contract, 1);
  function invoke(method, ...args) {
    const results = [];
    api[method](...args, text => { assert.equal(typeof text, 'string'); results.push(JSON.parse(text)); });
    assert.equal(results.length, 0, 'Callback must always be asynchronous');
    return results;
  }
  return { clock, values, log, state, api, invoke };
}

let count = 0;
function test(name, body) {
  body();
  count++;
  process.stdout.write('ok ' + count + ' - ' + name + '\n');
}

test('missing slot returns not_found only after readonly transaction completion', () => {
  const env = fixture();
  const results = env.invoke('read_slot', KEY);
  while (!env.log.includes('request_success:get:readonly')) assert.ok(env.clock.next());
  assert.equal(results.length, 0);
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'not_found');
  assert.equal(results[0].ok, true);
  assert.ok(env.log.includes('tx_complete:readonly'));
});

test('read returns exact opaque envelope text after completion', () => {
  const raw = '{"unchanged":"原字节"}\n';
  const env = fixture({ values: { [KEY]: { schema: 1, text: raw } } });
  const results = env.invoke('read_slot', KEY);
  env.clock.drain();
  assert.equal(results[0].ok, true);
  assert.equal(results[0].status, 'read');
  assert.equal(results[0].text, raw);
});

test('first commit waits for write transaction and independent readback transaction', () => {
  const env = fixture();
  const results = env.invoke('commit_slot', KEY, null, 'new envelope');
  while (!env.log.some(x => x.startsWith('request_success:put:') || x.startsWith('request_success:add:'))) assert.ok(env.clock.next());
  assert.equal(results.length, 0, 'Request success is not a commit acknowledgement');
  assert.equal(env.values.has(KEY), false, 'Staged write has not committed yet');
  while (!env.log.includes('tx_complete:readwrite')) assert.ok(env.clock.next());
  assert.equal(results.length, 0, 'Commit must still verify a readonly readback');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, true);
  assert.equal(results[0].status, 'saved_web');
  assert.ok(env.log.includes('tx_complete:readonly'));
  assert.deepEqual(env.values.get(KEY), { schema: 1, text: 'new envelope' });
});

test('compare-and-swap accepts the observed original text', () => {
  const env = fixture({ values: { [KEY]: { schema: 1, text: 'old' } } });
  const results = env.invoke('commit_slot', KEY, 'old', 'replacement');
  env.clock.drain();
  assert.equal(results[0].status, 'saved_web');
  assert.equal(env.values.get(KEY).text, 'replacement');
});

test('CAS race preserves another tab latest complete record', () => {
  const env = fixture({ values: { [KEY]: { schema: 1, text: 'other tab' } } });
  const results = env.invoke('commit_slot', KEY, 'observed old text', 'replacement');
  env.clock.drain();
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_conflict');
  assert.equal(env.values.get(KEY).text, 'other tab');
});

test('expected missing never overwrites a pre-existing slot', () => {
  const env = fixture({ values: { [KEY]: { schema: 1, text: 'exists' } } });
  const results = env.invoke('commit_slot', KEY, null, 'replacement');
  env.clock.drain();
  assert.equal(results[0].status, 'web_conflict');
  assert.equal(env.values.get(KEY).text, 'exists');
});

test('abort after request success does not acknowledge or change the prior record', () => {
  const env = fixture({ values: { [KEY]: { schema: 1, text: 'old' } }, abortAfterPutSuccess: true });
  const results = env.invoke('commit_slot', KEY, 'old', 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_transaction_aborted');
  assert.equal(env.values.get(KEY).text, 'old');
});

test('post-commit readback mismatch returns uncertain instead of saved', () => {
  const env = fixture({ afterWriteCommit(values) { values.set(KEY, { schema: 1, text: 'racing value' }); } });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_commit_unconfirmed');
  assert.equal(results[0].uncertain, true);
});

test('unknown record schema is rejected on read and not overwritten by CAS', () => {
  const invalid = { schema: 2, text: 'future' };
  const env = fixture({ values: { [KEY]: invalid } });
  const read = env.invoke('read_slot', KEY);
  env.clock.drain();
  assert.equal(read[0].status, 'web_invalid_record');
  const write = env.invoke('commit_slot', KEY, 'future', 'replacement');
  env.clock.drain();
  assert.equal(write[0].ok, false);
  assert.equal(write[0].status, 'web_invalid_record');
  assert.deepEqual(env.values.get(KEY), invalid);
});

test('non-string record text remains untouched', () => {
  const invalid = { schema: 1, text: { unexpected: true } };
  const env = fixture({ values: { [KEY]: invalid } });
  const results = env.invoke('read_slot', KEY);
  env.clock.drain();
  assert.equal(results[0].status, 'web_invalid_record');
  assert.deepEqual(env.values.get(KEY), invalid);
});

test('invalid keys and invalid expected payload are rejected before opening a database', () => {
  for (const key of ['stairkeep-fifty-slice/v1/classic_restart/../other', 'chapter3/classic_restart/first-chapter', KEY + '/extra', KEY + '\n', 'stairkeep-fifty-slice/v1/classic_restart/con']) {
    const env = fixture();
    const results = env.invoke('read_slot', key);
    env.clock.drain();
    assert.equal(results[0].status, 'web_invalid_request');
    assert.equal(env.state.opens, 0);
  }
  const env = fixture();
  const results = env.invoke('commit_slot', KEY, undefined, 'new');
  env.clock.drain();
  assert.equal(results[0].status, 'web_invalid_request');
  assert.equal(env.state.opens, 0);
});

test('classic and practice keys remain separate', () => {
  const env = fixture({ values: { [KEY]: { schema: 1, text: 'classic' } } });
  const results = env.invoke('commit_slot', PRACTICE, null, 'practice');
  env.clock.drain();
  assert.equal(results[0].status, 'saved_web');
  assert.equal(env.values.get(KEY).text, 'classic');
  assert.equal(env.values.get(PRACTICE).text, 'practice');
});

test('missing IndexedDB produces one failure callback', () => {
  const env = fixture({ noIndexedDB: true });
  const results = env.invoke('read_slot', KEY);
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
});

function checkThrowingAvailability(scriptOverride) {
  const env = fixture({ indexedDBGetterThrows: true, scriptOverride });
  const results = env.invoke('read_slot', KEY);
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_storage_unavailable');
  assert.equal(results[0].error_name, 'SecurityError');
  assert.equal(env.state.availabilityGetterCalls, 1, 'The actual throwing getter must have been invoked');
  assert.equal(env.state.opens, 0);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
}

test('IndexedDB availability getter SecurityError is reported asynchronously once', () => {
  checkThrowingAvailability();
});

test('getter regression check rejects an in-memory mutant without availability protection', () => {
  const unprotected = script.replace(/([ \t]*)try \{\r?\n([ \t]*)factory = root\.indexedDB;/,
    '$1factory = root.indexedDB;\n$1try {');
  assert.notEqual(unprotected, script, 'The mutation must actually remove the getter from the try block');
  assert.throws(() => checkThrowingAvailability(unprotected), { name: 'SecurityError' },
    'The same contract check must fail when the getter exception is unprotected');
});

test('database close exceptions do not lose an already verified commit callback', () => {
  const env = fixture({ closeThrows: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, true);
  assert.equal(results[0].status, 'saved_web');
  assert.equal(env.values.get(KEY).text, 'new');
  assert.equal(env.state.closes, 1);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
});

test('database open errors and blocked upgrades finish exactly once', () => {
  for (const [option, expected] of [['openError', 'web_open_failed'], ['openBlocked', 'web_open_blocked']]) {
    const env = fixture({ [option]: true });
    const results = env.invoke('read_slot', KEY);
    env.clock.drain();
    assert.equal(results.length, 1);
    assert.equal(results[0].status, expected);
    env.clock.advance(30000);
    env.state.openRequests[0].error = new Error('late error');
    dispatch(env.state.openRequests[0], 'error');
    env.clock.drain();
    assert.equal(results.length, 1);
  }
});

test('quota failure preserves the original committed record', () => {
  const env = fixture({ quota: true, values: { [KEY]: { schema: 1, text: 'old' } } });
  const results = env.invoke('commit_slot', KEY, 'old', 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(env.values.get(KEY).text, 'old');
});

test('open timeout and late success cannot start a transaction or produce a second callback', () => {
  const env = fixture({ openHang: true });
  const results = env.invoke('read_slot', KEY);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'web_timeout');
  assert.equal(results[0].uncertain, false);
  env.state.openRequests[0].fire();
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(env.state.transactions.length, 0);
});

test('uncommitted transaction timeout aborts and reports no confirmed save', () => {
  const env = fixture({ commitHang: true, values: { [KEY]: { schema: 1, text: 'old' } } });
  const results = env.invoke('commit_slot', KEY, 'old', 'new');
  env.clock.drain();
  assert.equal(results.length, 0);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(env.values.get(KEY).text, 'old');
  assert.ok(env.state.transactions[0].aborted);
});

test('timeout with unavailable abort is marked uncertain', () => {
  const env = fixture({ commitHang: true, abortThrows: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  env.clock.advance(30000);
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_commit_unconfirmed');
  assert.equal(results[0].uncertain, true);
});

test('strict durability may fall back without skipping transaction acknowledgement', () => {
  const env = fixture({ strictUnsupported: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.ok(env.state.strictAttempts >= 1);
  assert.equal(results[0].status, 'saved_web');
  assert.ok(env.log.includes('tx_complete:readwrite'));
  assert.ok(env.log.includes('tx_complete:readonly'));
});

test('security transaction failures do not use the unsupported-option fallback', () => {
  const env = fixture({ transactionThrow: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(env.state.strictAttempts, 1);
  assert.equal(env.state.transactions.length, 0);
  assert.equal(env.values.has(KEY), false);
});

test('readback transaction abort reports uncertain after write commit', () => {
  const env = fixture({ abortReadback: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results.length, 1);
  assert.equal(results[0].ok, false);
  assert.equal(results[0].status, 'web_commit_unconfirmed');
  assert.equal(results[0].uncertain, true);
  assert.equal(env.values.get(KEY).text, 'new');
});

test('readback timeout retains commit uncertainty and ignores later events', () => {
  const env = fixture({ readbackHang: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results.length, 0);
  assert.equal(env.state.writeCommitted, true);
  env.clock.advance(30000);
  assert.equal(results.length, 1);
  assert.equal(results[0].status, 'web_commit_unconfirmed');
  assert.equal(results[0].uncertain, true);
  assert.equal(env.values.get(KEY).text, 'new');
  const readonly = env.state.transactions[1];
  dispatch(readonly, 'complete');
  env.clock.drain();
  assert.equal(results.length, 1);
});

test('byte limit rejects empty and oversized UTF-8 values before opening storage', () => {
  const tooManyUtf8Bytes = '中'.repeat(Math.floor(8388608 / 3) + 1);
  for (const raw of ['', tooManyUtf8Bytes]) {
    const env = fixture();
    const results = env.invoke('commit_slot', KEY, null, raw);
    env.clock.drain();
    assert.equal(results[0].ok, false);
    assert.equal(results[0].status, 'web_invalid_request');
    assert.equal(env.state.opens, 0);
  }
});

test('records with unexpected fields are preserved rather than normalized away', () => {
  const invalid = { schema: 1, text: 'old', future: true };
  const env = fixture({ values: { [KEY]: invalid } });
  const results = env.invoke('commit_slot', KEY, 'old', 'replacement');
  env.clock.drain();
  assert.equal(results[0].status, 'web_invalid_record');
  assert.deepEqual(env.values.get(KEY), invalid);
});

test('first-open store creation works without touching a legacy namespace', () => {
  const env = fixture({ storeMissing: true });
  const results = env.invoke('commit_slot', KEY, null, 'new');
  env.clock.drain();
  assert.equal(results[0].status, 'saved_web');
  assert.equal(env.state.opens, 1);
});

process.stdout.write('1..' + count + '\n');
process.stdout.write('PURE_NODE_TRANSACTION_FIXTURE_ONLY: no real IndexedDB, browser, Godot, refresh or durable-storage acceptance\n');
