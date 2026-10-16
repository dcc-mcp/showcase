"use strict";
// Synthetic pixels/receipts exercise rejection logic only. They are never
// counted as browser playback or evidence for the delivered artwork.
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {motionMask, compare, validate, install} = require("./pendulum_playback.js");

function frames() {
  return Array.from({length: 144}, (_, index) => {
    const pixels = new Uint8ClampedArray(160 * 120 * 4);
    for (let i = 0; i < pixels.length; i += 4) pixels[i + 3] = 255;
    const start = 44 + Math.round(index / 143 * 47);
    for (let y = 45; y < 58; y++) for (let x = start; x < start + 13; x++) {
      const offset = (y * 160 + x) * 4;
      pixels[offset] = pixels[offset + 1] = pixels[offset + 2] = 210;
    }
    return pixels;
  });
}
const references = frames();
const mask = motionMask(references, 160, 120);

function receipt() {
  return {done: true, ended: 1, playEvents: 1, seeks: 0, rates: [1, 1], errors: [],
    width: 960, height: 720, duration: 6.006, elapsedMs: 6100, visibleChanges: 100,
    start: {passed: true}, end: {passed: true}, displayedEnd: {passed: true},
    samples: Array.from({length: 144}, (_, index) => ({frame: index + 1,
      passed: true, presentedFrames: index + 1, mediaTime: index * 1001 / 24000})),
    quality: {totalVideoFrames: 144, droppedVideoFrames: 0, corruptedVideoFrames: 0}};
}

test("same-source picture tolerates bounded codec/JPEG pixel differences", () => {
  const pixels = references[72].map((value, index) => index % 4 === 3 ? value : Math.min(255, value + 3));
  assert.equal(compare(pixels, 72, references, mask).passed, true);
});

test("frozen picture fails even while mediaTime and presented count advance", () => {
  const result = receipt();
  result.samples[143] = {...result.samples[143], ...compare(references[0], 143, references, mask)};
  result.visibleChanges = 0;
  assert.equal(result.samples[143].passed, false);
  assert.equal(validate(result).passed, false);
});

test("wrong final decoded and displayed pictures fail independently", () => {
  for (const field of ["end", "displayedEnd"]) {
    const result = receipt();
    result[field] = compare(references[12], 143, references, mask);
    assert.equal(result[field].passed, false);
    assert.equal(validate(result).passed, false);
  }
});

test("large static background cannot hide a wrong moving-object image", () => {
  assert(mask.length >= 100);
  const result = compare(references[0], 143, references, mask);
  assert(result.mean > 6);
  assert.equal(result.passed, false);
});

test("complete receipt passes and limited genuine callback drops are tolerated", () => {
  assert.equal(validate(receipt()).passed, true);
  const result = receipt();
  result.samples = result.samples.filter((_, index) => index % 4 !== 2);
  result.quality.droppedVideoFrames = 36;
  assert.equal(result.samples.length, 108);
  assert.equal(validate(result).passed, true);
});

test("currentTime/duration/ended alone cannot pass", () => {
  assert.equal(validate({done: true, ended: 1, duration: 6.006, currentTime: 6.006,
    rates: [], samples: [], errors: []}).passed, false);
});

test("absent, fixed or malformed references fail closed", () => {
  assert.throws(() => motionMask([], 160, 120), /Missing/);
  assert.throws(() => motionMask(Array(144).fill(references[0]), 160, 120), /insufficient/);
  assert.throws(() => motionMask(references, 80, 60), /malformed/);
  assert.throws(() => compare(null, 0, references, mask), /Missing/);
});

test("missing decoder APIs fail rather than silently skipping acceptance", async () => {
  await assert.rejects(install({}, {}), /decoded-frame APIs unavailable/);
});

test("CORS, media decode, missing image and insufficient frame coverage fail closed", () => {
  for (const reason of ["SecurityError: tainted canvas", "Media decode/network error 3", "Reference image did not decode"]) {
    const result = receipt(); result.errors.push(reason);
    assert.equal(validate(result).passed, false);
  }
  for (const change of [
    result => { result.samples = result.samples.slice(0, 100); },
    result => { result.samples.splice(20, 10); },
    result => { result.samples[5].presentedFrames = 5; },
    result => { result.samples[5].mediaTime = 0; },
    result => { result.quality.totalVideoFrames = 23; },
    result => { result.quality.corruptedVideoFrames = 1; },
  ]) {
    const result = receipt(); change(result);
    assert.equal(validate(result).passed, false);
  }
});

test("seek, retime, replay, missing final screenshot and premature ended cannot pass", () => {
  for (const change of [
    result => { result.seeks = 1; }, result => { result.rates.push(4); },
    result => { result.playEvents = 2; }, result => { result.ended = 0; },
    result => { result.elapsedMs = 1000; }, result => { delete result.displayedEnd; },
    result => { result.duration = 1.001; }, result => { result.width = 640; },
  ]) {
    const result = receipt(); change(result);
    assert.equal(validate(result).passed, false);
  }
});
