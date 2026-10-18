#!/usr/bin/env node
'use strict';
// Isolated lifecycle regressions. These fixtures do not prove native playability.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const source = fs.readFileSync(path.join(__dirname, '../play/minigame-shell.js'), 'utf8');

function fixture() {
  const elements = new Map(), timers = new Map();
  let reloads = 0, nextTimer = 1, instance, resolveStart;
  function element() {
    return {dataset: {}, style: {}, hidden: false, disabled: false, textContent: '', children: [], events: {},
      addEventListener(name, handler) { this.events[name] = handler; },
      append(child) { this.children.push(child); },
      querySelector(selector) { return this.children.find(child => selector.includes(child.dataset.command)); },
      focus() {}};
  }
  const get = id => { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); };
  get('game-config').textContent = JSON.stringify({title: {en: 'Signal Garden'}, instructions: {en: 'Rotate'},
    desktopSize: [1120, 780], mobileSize: [720, 1100],
    export: {executable: '../runtime/godot-4.6.3', fileSizes: {'../runtime/godot-4.6.3.wasm': 1}}});
  class Engine {
    constructor(config) { this.config = config; this.quitRequests = 0; instance = this; }
    static isWebGLAvailable() { return true; }
    static async load() {}
    startGame() { return new Promise(resolve => { resolveStart = resolve; }); }
    requestQuit() { this.quitRequests++; this.config.onExit(); }
  }
  class AudioNode { connect() {} }
  class AudioDestinationNode {}
  const document = {getElementById: get, createElement: element, documentElement: {},
    body: {dataset: {state: 'ready'}}, addEventListener() {}, head: {append(script) { script.onload(); }}};
  const window = {addEventListener() {}};
  const location = {search: '', origin: 'http://fixture.test', reload() { reloads++; }};
  vm.runInNewContext(source, {document, window, parent: window, location, Engine, AudioNode,
    AudioDestinationNode, URLSearchParams, matchMedia: () => ({matches: false}),
    setTimeout(handler) { const id = nextTimer++; timers.set(id, handler); return id; },
    clearTimeout(id) { timers.delete(id); }, console: {error() {}}});
  return {get, document, timers, start: () => get('start').events.click(),
    resolve: () => resolveStart(), engine: () => instance, reloads: () => reloads};
}

test('late startup after timeout preserves visible retry until explicit activation', async () => {
  const f = fixture(), starting = f.start();
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(f.engine());
  const timeout = [...f.timers.values()][0];
  timeout();
  assert.equal(f.document.body.dataset.state, 'error');
  assert.equal(f.get('start').textContent, 'Retry');
  assert.equal(f.get('start').hidden, false);
  assert.equal(f.get('start').disabled, false);
  f.resolve();
  await starting;
  assert.equal(f.engine().quitRequests, 1);
  assert.equal(f.reloads(), 0);
  assert.equal(f.document.body.dataset.state, 'error');
  await f.start();
  assert.equal(f.reloads(), 1);
});

test('ordinary successful exit still returns to the unloaded start page', async () => {
  const f = fixture(), starting = f.start();
  await new Promise(resolve => setImmediate(resolve));
  f.resolve();
  await starting;
  assert.equal(f.document.body.dataset.state, 'running');
  assert.equal(f.timers.size, 0);
  f.get('exit').events.click();
  assert.equal(f.engine().quitRequests, 1);
  assert.equal(f.reloads(), 1);
});
