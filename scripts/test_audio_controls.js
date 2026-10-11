#!/usr/bin/env node
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../assets/detail.js"), "utf8");
let checks = 0;
function fixture(initial = {}) {
  const events = {};
  const audio = Object.assign({readyState: 0, duration: NaN, currentTime: 0, paused: true, error: null,
    addEventListener(name, action) { events[name] = action; },
    play() { throw new Error("Seeking must never start playback"); },
    pause() { throw new Error("Seeking must never stop playback"); }
  }, initial);
  const buttons = [-5, 5].map(delta => ({disabled: true, dataset: {audioSeek: String(delta)},
    addEventListener(name, action) { this[name] = action; }}));
  const player = {querySelector() { return audio; }, querySelectorAll() { return buttons; }};
  const document = {querySelector() { return null; }, querySelectorAll() { return [player]; }};
  vm.runInNewContext(source, {document});
  return {audio, buttons, events};
}
function test(name, action) { action(); checks++; console.log("PASS " + name); }

test("controls stay disabled and inactive until metadata is known", () => {
  const {audio, buttons} = fixture();
  assert.equal(buttons.every(button => button.disabled), true);
  buttons[1].click();
  assert.equal(audio.currentTime, 0);
  assert.equal(audio.paused, true);
});
test("metadata enables both controls without starting playback", () => {
  const {audio, buttons, events} = fixture();
  audio.duration = 28.6; audio.readyState = 1;
  events.loadedmetadata();
  assert.equal(buttons.some(button => button.disabled), false);
  assert.equal(audio.currentTime, 0);
  assert.equal(audio.paused, true);
});
test("explicit forward and backward activation preserves paused state", () => {
  const {audio, buttons} = fixture({duration: 28.6, readyState: 4, currentTime: 0.2});
  buttons[1].click(); assert.equal(audio.currentTime, 5.2);
  assert.equal(audio.paused, true);
  buttons[0].click(); assert.ok(Math.abs(audio.currentTime - 0.2) < 1e-9);
  assert.equal(audio.paused, true);
});
test("seeking preserves already-playing state without calling playback APIs", () => {
  const {audio, buttons} = fixture({duration: 28.6, readyState: 4, currentTime: 2, paused: false});
  buttons[1].click(); assert.equal(audio.currentTime, 7);
  assert.equal(audio.paused, false);
});
test("seek position is clamped at both endpoints", () => {
  const {audio, buttons} = fixture({duration: 28.6, readyState: 4, currentTime: 2});
  buttons[0].click(); assert.equal(audio.currentTime, 0);
  audio.currentTime = 27;
  buttons[1].click(); assert.equal(audio.currentTime, 28.6);
});
test("unknown duration, emptied media and errors disable seeking again", () => {
  for (const event of ["durationchange", "emptied", "error"]) {
    const {audio, buttons, events} = fixture({duration: 28.6, readyState: 4});
    if (event === "durationchange") audio.duration = Infinity;
    if (event === "emptied") audio.readyState = 0;
    if (event === "error") audio.error = {code: 4};
    events[event]();
    assert.equal(buttons.every(button => button.disabled), true);
    buttons[1].click(); assert.equal(audio.currentTime, 0);
  }
});
test("invalid seek values cannot write a nonfinite media position", () => {
  const {audio, buttons} = fixture({duration: 28.6, readyState: 4, currentTime: 1});
  buttons[1].dataset.audioSeek = "not a number";
  buttons[1].click(); assert.equal(audio.currentTime, 1);
});
console.log(checks + " audio control behavior tests passed");
