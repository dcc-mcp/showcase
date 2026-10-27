#!/usr/bin/env node
"use strict";
// Browser-independent lifecycle tests. Real decoded playback is tested by
// video_browser_smoke.py on the official Chromium CI runner.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../assets/detail.js"), "utf8");
const tests = [];
const test = (name, fn) => tests.push({name, fn});
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };
function node(values = {}) {
  const listeners = new Map(), attrs = new Map();
  return Object.assign({dataset: {}, children: [], isConnected: true, textContent: "",
    addEventListener(name, fn) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(fn); },
    removeEventListener(name, fn) { listeners.get(name)?.delete(fn); },
    handlers(name) { return [...(listeners.get(name) || [])]; },
    emit(name, value = {}) { const e = Object.assign({preventDefault() {}}, value); [...(listeners.get(name) || [])].forEach(fn => fn(e)); },
    setAttribute(name, value) { attrs.set(name, String(value)); },
    getAttribute(name) { return attrs.get(name) ?? null; },
    hasAttribute(name) { return attrs.has(name); },
    removeAttribute(name) { attrs.delete(name); },
    append(...items) { this.children.push(...items); },
    closest() { return this.hidden ? this : null; }
  }, values);
}
function fixture(options = {}) {
  const timers = new Map(); let serial = 0;
  const entries = Array.from({length: 2}, (_, index) => {
    const source = node(); source.setAttribute("src", "../../media/film-" + index + ".mp4");
    const host = node();
    const video = node({parentElement: host, dataset: {previewAudio: options.audio ?? "true"},
      paused: true, controls: true, currentTime: 0, requests: [], playCount: 0, loadCount: 0, loadWithSourceCount: 0, srcAssignments: 0, mode: options.mode || "resolve",
      rect: {width: 640, height: 360, top: 50, left: 0, bottom: 410, right: 640},
      querySelectorAll() { return [source]; },
      getBoundingClientRect() { return this.rect; },
      pause() { this.paused = true; },
      load() { this.loadCount++; if (this.hasAttribute("src") || source.hasAttribute("src")) this.loadWithSourceCount++; this.paused = true; this.currentTime = 0; },
      play() {
        this.playCount++;
        this.paused = false;
        if (!options.deferPlayEvent) this.emit("play");
        if (this.mode === "reject") return Promise.reject(new Error("blocked"));
        if (this.mode === "defer") return new Promise((resolve, reject) => this.requests.push({
          resolve: () => { this.paused = false; resolve(); }, reject
        }));
        this.paused = false;
        return Promise.resolve();
      }
    });
    Object.defineProperty(video, "src", {get() { return this.getAttribute("src"); }, set(v) { this.srcAssignments++; this.setAttribute("src", v); }});
    return {host, video, source};
  });
  const hover = node({matches: options.hover !== false}), reduced = node({matches: !!options.reduced}), connection = node({saveData: !!options.saveData});
  const document = node({hidden: false, baseURI: "https://example.com/showcase/cases/test/", documentElement: {lang: options.lang || "en"},
    querySelector() { return null; },
    querySelectorAll(selector) { return selector === ".detail-video video[data-hover-preview]" ? entries.map(e => e.video) : []; },
    createElement() { return node(); }
  });
  const window = node({innerWidth: 1280, innerHeight: 900,
    matchMedia(query) { return query.includes("reduced") ? reduced : hover; },
    setTimeout(fn) { timers.set(++serial, fn); return serial; }, clearTimeout(id) { timers.delete(id); }
  });
  vm.runInNewContext(source, {document, window, navigator: {connection}, URL, Promise});
  entries.forEach(e => { [e.button, e.status, e.audioNote] = e.host.children[0].children; });
  return {entries, document, window, hover, reduced, connection, timers};
}
const enter = e => e.host.emit("pointerenter", {pointerType: "mouse"});
const leave = e => e.host.emit("pointerleave", {pointerType: "mouse"});
const watch = e => e.button.emit("click");
const idle = e => {
  assert.equal(e.host.dataset.videoState, "idle");
  assert.equal(e.video.paused, true);
  assert.equal(e.video.muted, true);
  assert.equal(e.video.hasAttribute("src"), false);
  assert.equal(e.video.currentTime, 0);
};

test("native fallback and preload none remain usable before any intent", () => {
  for (const e of fixture().entries) {
    idle(e); assert.equal(e.video.playCount, 0); assert.equal(e.video.preload, "none");
    assert.ok(e.source.getAttribute("src")); assert.equal(e.video.autoplay, false);
    assert.equal(e.video.loadCount, 0); assert.equal(e.video.srcAssignments, 0);
    assert.equal(e.video.tabIndex, 0); assert.equal(e.video.controls, true);
  }
});
test("hover immediately starts muted preview and leave releases decoder/source", async () => {
  const e = fixture().entries[0]; enter(e); assert.equal(e.video.playCount, 1);
  await flush(); assert.equal(e.host.dataset.videoState, "preview");
  assert.equal(e.video.muted, true); assert.equal(e.video.loop, true);
  e.video.currentTime = 5; leave(e); idle(e);
  assert.equal(e.source.hasAttribute("src"), false); assert.equal(e.video.controls, false);
  assert.equal(e.video.loadCount, 1); assert.equal(e.video.loadWithSourceCount, 0);
});
test("explicit watching enables native audio, seeking and survives pointer exit", async () => {
  const f = fixture(), [e, other] = f.entries; enter(e); await flush(); watch(e); await flush();
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.muted, false);
  assert.equal(e.video.controls, true); assert.equal(e.video.loop, false);
  leave(e); enter(other); assert.equal(e.video.paused, false); idle(other);
  e.video.currentTime = 4; e.video.pause(); e.video.emit("pointerdown"); e.video.emit("play");
  assert.equal(e.video.currentTime, 4); assert.equal(e.video.playCount, 2);
  watch(e); idle(e);
});
test("native controls play adopts the session without restarting or double play", () => {
  const e = fixture().entries[0];
  e.video.emit("pointerdown"); e.video.paused = false; e.video.currentTime = 2;
  e.video.emit("play"); e.video.emit("playing");
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.playCount, 0);
  assert.equal(e.video.currentTime, 2); assert.equal(e.video.muted, false);
  leave(e); assert.equal(e.video.paused, false);
});
test("released poster pointerdown stays inert and one click starts exactly once", async () => {
  const e = fixture().entries[0]; enter(e); await flush(); leave(e);
  assert.equal(e.source.hasAttribute("src"), false); assert.equal(e.video.src, null);
  assert.equal(e.video.controls, false);
  const plays = e.video.playCount, assignments = e.video.srcAssignments; let prevented = 0;
  e.video.emit("pointerdown"); e.video.emit("keydown", {key: "ArrowRight"});
  assert.equal(e.video.srcAssignments, assignments); assert.equal(e.video.playCount, plays);
  e.video.emit("click", {preventDefault() { prevented++; }}); await flush();
  assert.equal(prevented, 1); assert.equal(e.video.playCount, plays + 1);
  assert.equal(e.video.srcAssignments, assignments + 1); assert.equal(e.video.controls, true);
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.muted, false);
  // A later native click must not be intercepted or restart the source.
  e.video.currentTime = 3;
  e.video.emit("pointerdown"); e.video.emit("click", {preventDefault() { prevented++; }});
  assert.equal(prevented, 1); assert.equal(e.video.playCount, plays + 1);
  assert.equal(e.video.srcAssignments, assignments + 1); assert.equal(e.video.currentTime, 3);
  watch(e); idle(e); assert.equal(e.video.loadWithSourceCount, 0);
});
test("released-idle Space and Enter restart once and suppress the disabled native default", async () => {
  for (const key of [" ", "Enter"]) {
    const e = fixture().entries[0]; enter(e); await flush(); leave(e);
    const before = e.video.playCount; let prevented = 0;
    e.video.emit("keydown", {key, preventDefault() { prevented++; }});
    await flush();
    assert.equal(prevented, 1); assert.equal(e.video.playCount, before + 1);
    assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.muted, false);
    e.video.emit("keydown", {key, preventDefault() { prevented++; }});
    assert.equal(prevented, 1); assert.equal(e.video.playCount, before + 1);
  }
});
test("initial native play and active pause/seek keys keep their browser defaults", async () => {
  const e = fixture().entries[0]; let prevented = 0;
  e.video.emit("keydown", {key: " ", preventDefault() { prevented++; }});
  assert.equal(prevented, 0); assert.equal(e.video.playCount, 0);
  enter(e); await flush();
  for (const key of [" ", "ArrowRight", "ArrowUp"]) e.video.emit("keydown", {key, preventDefault() { prevented++; }});
  assert.equal(prevented, 0); assert.equal(e.video.playCount, 1);
});
test("native hover pause/seek gestures preserve mute and native control semantics", async () => {
  const e = fixture().entries[0]; enter(e); await flush();
  e.video.emit("pointerdown"); e.video.pause(); leave(e);
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.muted, true);
  assert.equal(e.video.paused, true); assert.equal(e.video.playCount, 1); assert.ok(e.video.src);
});
test("native pause during pending play is not misreported as a load failure", async () => {
  const e = fixture({mode: "defer"}).entries[0]; enter(e);
  e.video.emit("pointerdown"); e.video.pause();
  e.video.requests[0].reject(Object.assign(new Error("paused"), {name: "AbortError"}));
  await flush(); assert.equal(e.host.dataset.videoState, "watching"); assert.ok(e.video.src);
});
test("native pause before first playing clears only its watchdog and preserves seeking", () => {
  const f = fixture(), [e, other] = f.entries;
  e.video.emit("pointerdown"); e.video.paused = false; e.video.currentTime = 2;
  e.video.emit("play");
  assert.equal(f.timers.size, 1); assert.equal(e.host.dataset.videoState, "loading");
  e.video.pause(); e.video.emit("pause"); e.video.currentTime = 4;
  assert.equal(f.timers.size, 0); assert.equal(e.host.dataset.videoState, "watching");
  leave(e); enter(other);
  assert.equal(e.video.currentTime, 4); assert.equal(e.video.controls, true);
  assert.ok(e.source.hasAttribute("src")); assert.equal(e.video.playCount, 0);
  assert.equal(e.video.srcAssignments, 0); assert.equal(e.video.loadCount, 0);
  // Native resume keeps the source and arms a new load watchdog.
  e.video.paused = false; e.video.emit("play");
  assert.equal(f.timers.size, 1); assert.equal(e.host.dataset.videoState, "loading");
  e.video.handlers("pause")[0](); // A queued old pause cannot cancel an unpaused resume.
  assert.equal(f.timers.size, 1);
  e.video.emit("playing"); assert.equal(f.timers.size, 0);
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.currentTime, 4);
  assert.equal(e.video.playCount, 0); assert.equal(e.video.srcAssignments, 0);
});

test("a native resume that never plays still reaches the load timeout", () => {
  const f = fixture(), e = f.entries[0];
  e.video.emit("pointerdown"); e.video.paused = false; e.video.emit("play");
  e.video.pause(); e.video.emit("pause");
  assert.equal(f.timers.size, 0);
  e.video.paused = false; e.video.emit("play");
  assert.equal(f.timers.size, 1);
  [...f.timers.values()].forEach(fn => fn());
  assert.equal(e.host.dataset.videoState, "error"); assert.equal(e.video.controls, false);
  assert.equal(e.video.src, null); assert.equal(e.source.hasAttribute("src"), false);
});

test("native resume before queued pause gets a fresh deadline and ignores its old watchdog", () => {
  const f = fixture(), e = f.entries[0];
  e.video.emit("pointerdown"); e.video.paused = false; e.video.emit("play");
  const oldWatchdog = [...f.timers.keys()][0], oldTimeout = f.timers.get(oldWatchdog);
  e.video.pause(); // Its pause event is still queued when the user resumes.
  e.video.paused = false; e.video.emit("play");
  assert.equal(f.timers.size, 1); assert.equal(f.timers.has(oldWatchdog), false);
  const resumedWatchdog = [...f.timers.keys()][0];
  e.video.emit("pause"); oldTimeout();
  assert.equal(e.host.dataset.videoState, "loading");
  assert.equal(f.timers.has(resumedWatchdog), true);
  // Repeated buffering events cannot postpone the resumed attempt's deadline.
  e.video.emit("waiting"); e.video.emit("waiting");
  assert.equal(f.timers.size, 1); assert.equal(f.timers.has(resumedWatchdog), true);
  f.timers.get(resumedWatchdog)();
  assert.equal(e.host.dataset.videoState, "error");
});

test("queued pause AbortError cannot cancel native resume before or after its play event", async () => {
  for (const resumePlayFirst of [false, true]) {
    const f = fixture({mode: "defer", deferPlayEvent: true}), e = f.entries[0];
    watch(e); e.video.emit("play"); // The controller's first play event is asynchronous too.
    const source = e.video.src, assignments = e.video.srcAssignments;
    e.video.currentTime = 3; e.video.pause(); e.video.paused = false;
    if (resumePlayFirst) e.video.emit("play");
    const watchdog = [...f.timers.keys()][0];
    e.video.emit("pause");
    e.video.requests[0].reject(Object.assign(new Error("interrupted by pause"), {name: "AbortError"}));
    await flush();
    assert.equal(e.host.dataset.videoState, "loading"); assert.equal(f.timers.has(watchdog), true);
    if (!resumePlayFirst) e.video.emit("play");
    assert.equal(f.timers.size, 1); assert.equal(e.video.currentTime, 3);
    assert.equal(e.video.src, source); assert.equal(e.video.srcAssignments, assignments);
    assert.equal(e.video.playCount, 1);
    e.video.emit("playing");
    assert.equal(e.host.dataset.videoState, "watching"); assert.equal(f.timers.size, 0);
  }
});

test("the first asynchronous play event does not suppress genuine promise failures", async () => {
  for (const name of ["AbortError", "NotAllowedError"]) {
    const f = fixture({mode: "defer", deferPlayEvent: true}), e = f.entries[0];
    watch(e); e.video.emit("play");
    e.video.requests[0].reject(Object.assign(new Error("genuine failure"), {name}));
    await flush();
    assert.equal(e.host.dataset.videoState, "error"); assert.equal(f.timers.size, 0);
  }
});

test("a paused controller promise cannot confirm playback for a pending native resume", async () => {
  const f = fixture({mode: "defer"}), e = f.entries[0];
  watch(e); e.video.pause(); e.video.paused = false; e.video.emit("play"); e.video.emit("pause");
  const watchdog = [...f.timers.keys()][0];
  e.video.requests[0].resolve(); await flush();
  assert.equal(e.host.dataset.videoState, "loading"); assert.equal(f.timers.has(watchdog), true);
  e.video.emit("playing");
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(f.timers.size, 0);
});

test("a paused controller promise never hides current errors or the resume deadline", async () => {
  for (const failure of ["promise", "media", "watchdog"]) {
    const f = fixture({mode: "defer"}), e = f.entries[0];
    watch(e); e.video.pause(); e.video.paused = false; e.video.emit("play"); e.video.emit("pause");
    e.video.requests[0].reject(Object.assign(new Error("play failure"), {
      name: failure === "promise" ? "NotSupportedError" : "AbortError"
    }));
    await flush();
    if (failure !== "promise") {
      assert.equal(e.host.dataset.videoState, "loading");
      if (failure === "media") e.video.emit("error");
      else [...f.timers.values()].forEach(fn => fn());
    }
    assert.equal(e.host.dataset.videoState, "error"); assert.equal(f.timers.size, 0);
  }
});

test("stale pause and timeout callbacks cannot clear a newer run's watchdog", () => {
  const f = fixture({mode: "defer"}), e = f.entries[0];
  e.video.emit("pointerdown"); e.video.paused = false; e.video.emit("play");
  const oldPause = e.video.handlers("pause")[0], oldTimeout = [...f.timers.values()][0];
  watch(e); watch(e);
  assert.equal(e.host.dataset.videoState, "loading"); assert.equal(f.timers.size, 1);
  e.video.paused = true; oldPause(); e.video.paused = false; oldTimeout();
  assert.equal(e.host.dataset.videoState, "loading"); assert.equal(f.timers.size, 1);
  [...f.timers.values()].forEach(fn => fn());
  assert.equal(e.host.dataset.videoState, "error");
});

test("a genuine manual buffering stall still fails after playing", () => {
  const f = fixture(), e = f.entries[0];
  e.video.emit("pointerdown"); e.video.paused = false; e.video.emit("play"); e.video.emit("playing");
  assert.equal(f.timers.size, 0);
  e.video.emit("waiting"); assert.equal(f.timers.size, 1);
  const watchdog = [...f.timers.keys()][0];
  e.video.emit("waiting"); assert.equal(f.timers.has(watchdog), true);
  [...f.timers.values()].forEach(fn => fn());
  assert.equal(e.host.dataset.videoState, "error");
});

test("released-error Space and Enter explicitly retry once without automatic replay", async () => {
  for (const key of [" ", "Enter"]) {
    const f = fixture({mode: "defer"}), e = f.entries[0]; enter(e);
    [...f.timers.values()].forEach(fn => fn());
    assert.equal(e.host.dataset.videoState, "error"); assert.equal(f.timers.size, 0);
    const plays = e.video.playCount, assignments = e.video.srcAssignments; let prevented = 0;
    e.video.mode = "resolve";
    assert.equal(e.video.playCount, plays);
    e.video.emit("keydown", {key, preventDefault() { prevented++; }}); await flush();
    assert.equal(prevented, 1); assert.equal(e.video.playCount, plays + 1);
    assert.equal(e.video.srcAssignments, assignments + 1);
    assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.controls, true);
    e.video.emit("keydown", {key, preventDefault() { prevented++; }});
    assert.equal(prevented, 1); assert.equal(e.video.playCount, plays + 1);
    assert.equal(e.video.srcAssignments, assignments + 1);
  }
});

test("assistive click activation adopts native playback but hidden players cannot start", () => {
  const e = fixture().entries[0]; e.video.emit("click"); e.video.emit("play"); e.video.emit("playing");
  assert.equal(e.host.dataset.videoState, "watching");
  const hidden = fixture().entries[0]; hidden.host.hidden = true;
  hidden.video.emit("pointerdown"); hidden.video.paused = false; hidden.video.emit("play");
  assert.equal(hidden.video.paused, true); assert.equal(hidden.video.muted, true);
});
test("touch, reduced motion and data saving require explicit playback", async () => {
  for (const options of [{hover: false}, {reduced: true}, {saveData: true}]) {
    const e = fixture(options).entries[0]; enter(e); idle(e); watch(e); await flush();
    e.host.emit("pointerleave", {pointerType: "touch"}); assert.equal(e.host.dataset.videoState, "watching");
  }
  const e = fixture().entries[0]; e.host.emit("pointerenter", {pointerType: "touch"}); idle(e);
});
test("keyboard native activation and explicit button support no-hover devices", () => {
  const e = fixture({hover: false}).entries[0];
  e.video.emit("keydown", {key: " "}); e.video.emit("play"); e.video.emit("playing");
  assert.equal(e.host.dataset.videoState, "watching"); assert.equal(e.video.controls, true);
});
test("silent evidence stays silent and unknown is never labeled no audio", async () => {
  const silent = fixture({audio: "false"}).entries[0]; watch(silent); await flush();
  assert.equal(silent.video.muted, true); assert.equal(silent.audioNote.textContent, "No audio track");
  const unknown = fixture({audio: "unknown"}).entries[0];
  assert.equal(unknown.audioNote.textContent, "Audio unverified");
  const zh = fixture({lang: "zh-CN", audio: "false"}).entries[0]; assert.equal(zh.audioNote.textContent, "无音轨");
});
test("late fulfillment cannot resume an exited preview or interrupt newer watching", async () => {
  const f = fixture({mode: "defer"}), [e, other] = f.entries;
  enter(e); leave(e); e.video.requests[0].resolve(); await flush(); idle(e);
  enter(e); watch(e); e.video.requests[1].resolve(); await flush();
  assert.equal(e.host.dataset.videoState, "loading");
  e.video.requests[2].resolve(); await flush(); assert.equal(e.host.dataset.videoState, "watching");
  watch(other); idle(e);
  const next = fixture({mode: "defer"}), [old, current] = next.entries;
  enter(old); watch(current); old.video.requests[0].resolve(); await flush(); idle(old);
  assert.equal(current.host.dataset.videoState, "loading");
});
test("stalled/rejected media releases resources and allows explicit retry", async () => {
  const f = fixture({mode: "defer"}), e = f.entries[0]; enter(e);
  [...f.timers.values()].forEach(fn => fn());
  assert.equal(e.host.dataset.videoState, "error"); assert.equal(e.button.textContent, "Retry video"); assert.equal(e.video.src, null);
  e.video.mode = "reject"; watch(e); await flush(); assert.equal(e.host.dataset.videoState, "error");
  e.video.mode = "resolve"; watch(e); await flush(); assert.equal(e.host.dataset.videoState, "watching");
});
test("visibility, Escape, offscreen and pagehide stop playback and reset mute", async () => {
  for (const end of [f => { f.document.hidden = true; f.document.emit("visibilitychange"); },
    f => f.document.emit("keydown", {key: "Escape"}), f => f.window.emit("pagehide", {persisted: false}),
    f => { f.entries[0].video.rect.top = 950; f.document.emit("scroll"); }]) {
    const f = fixture(), e = f.entries[0]; enter(e); await flush(); end(f); idle(e);
  }
  const f = fixture(), e = f.entries[0]; watch(e); await flush();
  f.document.hidden = true; f.document.emit("visibilitychange"); idle(e);
});
test("preference changes stop only automatic previews and bfcache stays reusable", async () => {
  const f = fixture(), e = f.entries[0]; enter(e); await flush(); f.reduced.matches = true; f.reduced.emit("change"); idle(e);
  watch(e); await flush(); f.hover.emit("change"); assert.equal(e.host.dataset.videoState, "watching");
  f.window.emit("pagehide", {persisted: true}); idle(e); watch(e); await flush(); assert.equal(e.host.dataset.videoState, "watching");
});
(async () => {
  for (const {name, fn} of tests) { await fn(); console.log("PASS " + name); }
  console.log(tests.length + " detail video control tests passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
