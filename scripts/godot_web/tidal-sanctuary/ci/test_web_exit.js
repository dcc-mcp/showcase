'use strict';
const assert = require('node:assert/strict');
const {attach} = require('./web_exit.js');
const originalLog = console.log, originalError = console.error;
console.log = () => {}; console.error = () => {};
function fixture() {
  const config = {}, events = [], ui = {
    ready: x => events.push(['ready', x]), label: x => events.push(['label', x]),
    show: (text, ok) => events.push(['show', text, ok]), click: fn => {ui.press = fn;}
  };
  let quit = 0;
  const state = attach(config, () => {quit++;}, ui);
  return {config, ui, events, state, quits: () => quit};
}
function save(f, persistent = true, reason = 'exit') {
  f.config.onPrint('TIDAL_SAVE ' + JSON.stringify({schema: 1, quest_stage: 4,
    treasures: [true, true], completed: true, position: [0, 4, -12], language: 'en', persistent, reason}));
}
try {
  const f = fixture(); save(f);
  f.config.onPrint('TIDAL_FRAME_READY {}');
  f.ui.press({isTrusted: true});
  assert.equal(f.quits(), 1);
  assert.equal(f.state.isFinished(), false);
  assert.deepEqual(f.events.at(-1), ['show', 'Saving...', false]);
  save(f); f.config.onExit(0);
  assert.equal(f.state.isFinished(), true);
  assert.deepEqual(f.events.at(-1), ['show', 'Saved. Safe to leave.', true]);
  f.ui.press({isTrusted: true}); assert.equal(f.quits(), 1);
  for (const mode of ['old-save', 'auto-save', 'error', 'storage', 'exit-code', 'untrusted', 'unsolicited']) {
    const t = fixture(); save(t);
    if (mode !== 'unsolicited') t.ui.press({isTrusted: mode !== 'untrusted'});
    if (mode !== 'old-save') save(t, mode !== 'storage', mode === 'auto-save' ? 'auto' : 'exit');
    if (mode === 'error') t.config.onPrintError('Failed to save IDB file system: quota');
    t.config.onExit(mode === 'exit-code' ? 1 : 0);
    assert.equal(t.state.isFinished(), false, mode);
    assert.equal(t.events.at(-1)[2], false, mode);
  }
  const oldTimer = global.setTimeout, oldClear = global.clearTimeout;
  try {
    let timeout;
    global.setTimeout = fn => {timeout = fn; return 1;}; global.clearTimeout = () => {};
    const late = fixture(); late.ui.press({isTrusted: true}); save(late);
    timeout(); late.config.onExit(0);
    assert.equal(late.state.isFinished(), false, 'late success cannot erase a timeout');
  } finally { global.setTimeout = oldTimer; global.clearTimeout = oldClear; }
} finally { console.log = originalLog; console.error = originalError; }
console.log('Web save/return public-callback guards passed (no browser or storage simulation claim).');
