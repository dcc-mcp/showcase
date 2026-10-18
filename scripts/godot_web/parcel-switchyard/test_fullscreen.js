'use strict';
// Host-free event wiring regressions; real Chromium acceptance is separate.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../../../play/parcel-switchyard/shell.js'), 'utf8');
for (const lang of ['en', 'zh']) {
  const elements = new Map(), events = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      textContent: id === 'game-config' ? '{}' : '', hidden: true, dataset: {}, style: {}, attrs: {},
      setAttribute(name, value) { this.attrs[name] = value; },
      addEventListener() {}, append() {}, focus() {}, querySelector() { return element('route'); },
      getBoundingClientRect() { return {height: 900}; }
    });
    return elements.get(id);
  }
  const document = {
    fullscreenElement: null, hidden: false, body: {dataset: {}}, documentElement: {clientWidth: 1280},
    getElementById: element, createElement: () => element('created'), querySelector: () => element('main'),
    addEventListener(name, handler) { events.set(name, handler); },
    exitFullscreen() { this.fullscreenElement = null; events.get('fullscreenchange')(); return Promise.resolve(); }
  };
  element('stage').requestFullscreen = () => {
    document.fullscreenElement = element('stage'); events.get('fullscreenchange')(); return Promise.resolve();
  };
  const window = {addEventListener() {}};
  vm.runInNewContext(source, {document, window, parent: window, location: {search: '?lang=' + lang, origin: 'http://localhost'},
    URLSearchParams, URL, matchMedia: () => ({matches: false}), ResizeObserver: class {observe() {}},
    setTimeout, clearTimeout, console});
  assert.equal(element('leave-fullscreen').textContent, lang === 'zh' ? '退出全屏' : 'Exit fullscreen');
  element('fullscreen').onclick();
  assert.equal(document.fullscreenElement, element('stage'));
  assert.equal(element('fullscreen-tools').hidden, false);
  assert.equal(element('fullscreen').attrs['aria-expanded'], 'true');
  element('leave-fullscreen').onclick();
  assert.equal(document.fullscreenElement, null);
  assert.equal(element('fullscreen-tools').hidden, true);
  element('fullscreen').onclick();
  let prevented = false;
  events.get('keydown')({key: 'Escape', preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(document.fullscreenElement, null);
  // Never consume Escape or exit another element outside our stage.
  document.fullscreenElement = element('other'); prevented = false;
  events.get('keydown')({key: 'Escape', preventDefault() { prevented = true; }});
  element('leave-fullscreen').onclick();
  assert.equal(prevented, false);
  assert.equal(document.fullscreenElement, element('other'));
}
console.log('Fullscreen exit button and keyboard wiring passed for EN/ZH.');
