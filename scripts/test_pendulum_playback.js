"use strict";
// Synthetic pixels/receipts exercise rejection logic only. They are never
// counted as browser playback or evidence for the delivered artwork.
const assert = require("node:assert/strict");
const {test} = require("node:test");
const {readFileSync} = require("node:fs");
const vm = require("node:vm");
const {motionMask, compare, compareKeyframe, validateKeyframeRecords, validate, install} = require("./pendulum_playback.js");

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

// Exercise the actual observer installation/event handlers with synthetic
// images and a fake media element, never claiming a real browser decode.
async function observerFixture() {
  const listeners = new Map(), callbacks = [];
  const video = {readyState: 0, networkState: 2, videoWidth: 0, videoHeight: 0,
    currentTime: 0, currentSrc: "https://private.invalid/path/pendulum-oidn.mp4?private=hidden",
    paused: true, ended: false, seeking: false, playbackRate: 1, fixtureFrame: 0,
    addEventListener(name, fn, options) { listeners.set(name, {fn, once: options?.once}); },
    requestVideoFrameCallback(fn) { callbacks.push(fn); return callbacks.length; },
    cancelVideoFrameCallback() {},
    getVideoPlaybackQuality() { return {totalVideoFrames: 144, droppedVideoFrames: 0, corruptedVideoFrames: 0}; }};
  const sandbox = {module: {exports: {}}, window: {}, performance: {now: () => 0},
    Image: class {
      set src(url) { this.url = url; this.naturalWidth = url === "atlas" ? 1280 : 960;
        this.naturalHeight = url === "atlas" ? 2160 : 720; }
      async decode() {}
    },
    document: {createElement() {
      let drawn;
      return {getContext: () => ({
        drawImage(image, ...args) {
          const index = image === video ? video.fixtureFrame : image.url === "atlas" ?
            args[1] / 120 * 8 + args[0] / 160 : Number(image.url) - 1;
          drawn = references[index];
        },
        getImageData: () => ({data: drawn}),
      }), toDataURL: () => "data:image/png;base64,c3ludGhldGlj"};
    }},
  };
  vm.runInNewContext(readFileSync(require.resolve("./pendulum_playback.js"), "utf8"), sandbox);
  await sandbox.module.exports.install(video, {atlas: {url: "atlas"},
    keyframes: [1, 73, 144].map(frame => ({frame, url: String(frame)})), reference_basis: "synthetic test only"});
  return {video, callbacks, receipt: sandbox.window.__pendulumPlayback.receipt,
    pictures: sandbox.window.__pendulumPlayback.pictures,
    emit(name) { const item = listeners.get(name); if (!item) return;
      if (item.once) listeners.delete(name); item.fn(); },
    ready() { Object.assign(video, {readyState: 2, videoWidth: 960, videoHeight: 720}); },
    present(frame) { video.fixtureFrame = frame - 1; video.currentTime = (frame - 1) * 1001 / 24000;
      callbacks.at(-1)(0, {mediaTime: video.currentTime, presentedFrames: frame,
        width: 960, height: 720, expectedDisplayTime: 0}); },
  };
}

function receipt() {
  return {done: true, ended: 1, playEvents: 1, seeks: 0, rates: [1, 1], errors: [],
    width: 960, height: 720, duration: 6.006, elapsedMs: 6100, visibleChanges: 100,
    start: {passed: true}, end: {passed: true}, displayedEnd: {passed: true},
    samples: Array.from({length: 144}, (_, index) => ({frame: index + 1,
      passed: true, presentedFrames: index + 1, mediaTime: index * 1001 / 24000})),
    quality: {totalVideoFrames: 144, droppedVideoFrames: 0, corruptedVideoFrames: 0}};
}

test("observer arms only after loadeddata verifies and captures the actual first picture", async () => {
  const fixture = await observerFixture();
  assert.equal(fixture.callbacks.length, 0);
  fixture.emit("play");
  assert.equal(fixture.callbacks.length, 0);
  fixture.ready(); fixture.emit("loadeddata");
  assert.equal(fixture.receipt.start.passed, true);
  assert(fixture.pictures["first-decoded"]);
  assert.equal(fixture.callbacks.length, 1);
  fixture.present(2); // A legitimately already-presented first frame is still checked above.
  assert.equal(fixture.receipt.samples[0].frame, 2);
  assert.equal(fixture.receipt.samples[0].passed, true);
  assert.equal(fixture.callbacks.length, 2);
  assert.equal(fixture.receipt.observations.firstCallback.readyState, 2);
  assert.equal(fixture.receipt.observations.loadeddata.sourceName, "pendulum-oidn.mp4");
  assert(!JSON.stringify(fixture.receipt.observations).includes("private"));
});

test("unready wrong-sized late or mismatched initial picture fails without arming", async () => {
  for (const change of [f => { f.video.readyState = 1; }, f => { f.video.videoWidth = 640; },
                       f => { f.video.currentTime = 0.1; }, f => { f.video.fixtureFrame = 143; }]) {
    const fixture = await observerFixture();
    fixture.ready(); change(fixture); fixture.emit("loadeddata");
    assert.equal(fixture.callbacks.length, 0);
    assert.equal(fixture.receipt.done, true);
    assert(fixture.receipt.errors.length);
    assert.equal(fixture.receipt.observations.failure.stage, "loadeddata");
    assert.equal(validate(fixture.receipt).passed, false);
  }
});

test("a later unready callback still fails with exact stage and media metadata", async () => {
  const fixture = await observerFixture();
  fixture.ready(); fixture.emit("loadeddata");
  fixture.video.readyState = 1;
  fixture.present(2);
  assert.equal(fixture.callbacks.length, 1); // No silent retry or ignored bad callback.
  assert.equal(fixture.receipt.done, true);
  const failure = fixture.receipt.observations.failure;
  assert.equal(failure.stage, "rVFC");
  assert.equal(failure.readyState, 1);
  assert.equal(failure.width, 960);
  assert.equal(failure.callback.presentedFrames, 2);
  assert.equal(failure.callback.mediaTime, 1001 / 24000);
  assert.equal(validate(fixture.receipt).passed, false);
});

test("missing loadeddata or late callback coverage cannot pass", async () => {
  const fixture = await observerFixture();
  fixture.emit("play");
  assert.equal(fixture.callbacks.length, 0);
  assert.equal(validate(fixture.receipt).passed, false);
  const tooLate = receipt(); tooLate.samples = tooLate.samples.slice(2);
  assert.equal(validate(tooLate).passed, false);
});

test("same-source picture tolerates bounded codec/JPEG pixel differences", () => {
  const pixels = references[72].map((value, index) => index % 4 === 3 ? value : Math.min(255, value + 3));
  assert.equal(compare(pixels, 72, references, mask).passed, true);
});

test("sequence nearest-frame checks use one atlas encoding, not a mixed PNG baseline", () => {
  const atlas = references.map(frame => frame.map((value, index) => index % 4 === 3 ? value : value + 5));
  const atlasMask = motionMask(atlas, 160, 120);
  const keyframes = {1: references[0], 73: references[72], 144: references[143]};
  const actual = references[73]; // Adjacent source poses can legitimately be identical.
  assert.deepEqual(actual, keyframes[73]);
  assert.equal(compare(actual, 73, atlas, atlasMask).passed, true);
  const mixed = atlas.slice(); mixed[72] = keyframes[73];
  const wrongBaseline = compare(actual, 73, mixed, atlasMask);
  assert.equal(wrongBaseline.mean, 5);
  assert.equal(wrongBaseline.nearestMean, 0);
  assert.equal(wrongBaseline.passed, false);
  assert.equal(compareKeyframe(keyframes[73], 73, keyframes, atlasMask).passed, true);
  assert.equal(compare(references[0], 143, atlas, atlasMask).passed, false);
  assert.equal(compare(references[12], 143, atlas, atlasMask).passed, false);
  assert.equal(compare(actual, 73, atlas, atlasMask).passed, true);
});

test("independent PNG start middle and end checks reject wrong pictures and missing references", () => {
  const keyframes = {1: references[0], 73: references[72], 144: references[143]};
  for (const frame of [1, 73, 144]) {
    assert.equal(compareKeyframe(keyframes[frame], frame, keyframes, mask).passed, true);
    const wrong = frame === 1 ? references[143] : references[0];
    assert.equal(compareKeyframe(wrong, frame, keyframes, mask).passed, false);
  }
  assert.throws(() => compareKeyframe(references[72], 73, {}, mask), /Missing/);
  const result = receipt();
  result.keyframeSamples = [compareKeyframe(references[0], 73, keyframes, mask)];
  assert.equal(validate(result).passed, false);
  for (const field of ["start", "end", "displayedEnd"]) {
    const bad = receipt();
    bad[field] = compareKeyframe(references[12], field === "start" ? 1 : 144, keyframes, mask);
    assert.equal(validate(bad).passed, false);
  }
});

test("PNG keyframes must be the distinct actual frame numbers 1 73 and 144", () => {
  validateKeyframeRecords([1, 73, 144].map(frame => ({frame})));
  for (const values of [[], [1, 144], [1, 73, 73], [1, 2, 3], [1, 73, 145], [1, "73", 144]]) {
    assert.throws(() => validateKeyframeRecords(values.map(frame => ({frame}))), /keyframe numbers/);
  }
  assert.throws(() => compareKeyframe(references[0], 2, {2: references[0]}, mask), /Invalid/);
  const result = compareKeyframe(references[143], 144, {1: references[0], 73: references[72], 144: references[143]}, mask);
  assert.equal(result.frame, 144);
  assert.equal(result.nearestFrame, 144); // Actual source frame, not three-slot index 3.
  assert.throws(() => compareKeyframe(references[0], 1, {1: references[0]}, mask), /Missing/);
});

test("PNG same-set nearest limit rejects an absolute-tolerance target when another PNG is closer", () => {
  const actual = references[0];
  const offset = amount => actual.map((value, index) => index % 4 === 3 ? value : value + amount);
  const result = compareKeyframe(actual, 1, {1: offset(5), 73: actual, 144: offset(3)}, mask);
  assert.equal(result.mean, 5);
  assert.equal(result.p95, 5);
  assert.equal(result.nearestMean, 0);
  assert.equal(result.nearestFrame, 73);
  assert.equal(result.passed, false);
});

test("legal callback omission of exact middle keyframe keeps the complete atlas gate", () => {
  const result = receipt();
  result.samples = result.samples.filter(sample => sample.frame !== 73);
  result.keyframeSamples = [];
  result.middleKeyframe = {frame: 73, status: "not_observed"};
  assert.equal(validate(result).passed, true);
  result.samples[100] = {...result.samples[100], ...compare(references[0], result.samples[100].frame - 1, references, mask)};
  assert.equal(validate(result).passed, false);
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
