#!/usr/bin/env node
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../assets/preview.js"), "utf8");
const tests = [];
function test(name, action) { tests.push({name, action}); }
const flush = async () => { await Promise.resolve(); await Promise.resolve(); };

function emitter(values = {}) {
  const listeners = new Map();
  return Object.assign({
    addEventListener(name, action) {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name).add(action);
    },
    removeEventListener(name, action) { if (listeners.has(name)) listeners.get(name).delete(action); },
    emit(name, values = {}) {
      const event = Object.assign({preventDefault() {}, stopPropagation() {}}, values);
      for (const action of [...(listeners.get(name) || [])]) action(event);
      return event;
    },
    listenerCount() { return [...listeners.values()].reduce((sum, group) => sum + group.size, 0); }
  }, values);
}
function element(values = {}) {
  const attributes = new Map();
  return emitter(Object.assign({
    dataset: {}, hidden: false, textContent: "", parentElement: null, isConnected: true,
    style: {values: {}, setProperty(name, value) { this.values[name] = value; }},
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    hasAttribute(name) { return attributes.has(name); },
    removeAttribute(name) { attributes.delete(name); },
    querySelector() { return null; },
    closest() {
      for (let node = this; node; node = node.parentElement) {
        if (node.hidden || node.getAttribute("aria-hidden") === "true") return node;
      }
      return null;
    }
  }, values));
}
function fixture(options = {}) {
  const timers = new Map();
  let now = 0;
  let serial = 0;
  const intersectionObservers = [];
  const mutationObservers = [];
  const root = element({clientWidth: 1280, clientHeight: 900});
  const cards = Array.from({length: options.count ?? 2}, (_, index) => {
    const video = element({tagName: "VIDEO", currentTime: 0, duration: 20, paused: true,
      playCount: 0, pauseCount: 0, loadCount: 0, requests: [], mode: options.playMode || "resolve",
      play() {
        this.playCount++;
        if (this.mode === "throw") throw new Error("Unsupported media");
        if (this.mode === "undefined") { this.paused = false; return undefined; }
        if (this.mode === "reject") return Promise.reject(new Error("Autoplay blocked"));
        if (this.mode === "defer") {
          let resolve, reject;
          const promise = new Promise((yes, no) => { resolve = () => { this.paused = false; yes(); }; reject = no; });
          this.requests.push({resolve, reject});
          return promise;
        }
        this.paused = false;
        return Promise.resolve();
      },
      pause() { this.paused = true; this.pauseCount++; this.emit("pause"); },
      load() { this.paused = true; this.loadCount++; }
    });
    Object.defineProperty(video, "src", {get() { return this.getAttribute("src") || ""; }, set(value) { this.setAttribute("src", value); }});
    const label = options.labelSpan ? element() : null;
    const button = element({hidden: true, dataset: {playLabel: "Play preview", stopLabel: "Stop preview"},
      querySelector(selector) { return selector === ".preview-toggle-label" ? label : null; }});
    const progress = element();
    const status = element();
    const sound = element({hidden:true});
    const audioNote = element({hidden:true});
    const card = element({
      dataset: {previewSrc: "media/preview-" + index + ".mp4", previewKind: "video", errorLabel: "Preview unavailable. Open case for details."},
      rect: {width: 360, height: 260, left: 100, top: 100, right: 460, bottom: 360},
      parentElement: root, display: "block", visibility: "visible",
      querySelector(selector) { return {".card-preview": video, ".preview-toggle": button, ".preview-progress": progress, ".preview-status": status, '.preview-sound':sound, '.preview-audio-note':audioNote}[selector] || null; },
      getBoundingClientRect() { return this.rect; }
    });
    return Object.assign(card, {video, button, progress, status, label, sound, audioNote});
  });
  if (options.setup) options.setup(cards);
  const hover = emitter({matches: options.hover !== false});
  const reducedMotion = emitter({matches: Boolean(options.reducedMotion)});
  const connection = emitter({saveData: Boolean(options.saveData)});
  if (options.legacyMedia) for (const media of [hover, reducedMotion]) {
    const add = media.addEventListener.bind(media), remove = media.removeEventListener.bind(media);
    media.addListener = action => add("change", action);
    media.removeListener = action => remove("change", action);
    delete media.addEventListener; delete media.removeEventListener;
  }
  const document = emitter({hidden: false, baseURI: "https://example.com/showcase/", documentElement: root,
    querySelectorAll(selector) {
      assert.equal(selector, ".case-card[data-preview-src]");
      return cards;
    }
  });
  class Observer {
    constructor(callback, list) { this.callback = callback; this.targets = []; this.disconnected = false; list.push(this); }
    observe(target) { this.targets.push(target); }
    disconnect() { this.disconnected = true; }
  }
  const window = emitter({
    innerWidth: 1280, innerHeight: 900,
    matchMedia(query) { return query.includes("prefers-reduced-motion") ? reducedMotion : hover; },
    getComputedStyle(card) { return {display: card.display, visibility: card.visibility}; },
    setTimeout(action, delay) { const id = ++serial; timers.set(id, {action, at: now + delay}); return id; },
    clearTimeout(id) { timers.delete(id); },
    IntersectionObserver: options.noIntersection ? undefined : class extends Observer { constructor(callback) { super(callback, intersectionObservers); } },
    MutationObserver: class extends Observer { constructor(callback) { super(callback, mutationObservers); } }
  });
  if (options.noMatchMedia) delete window.matchMedia;
  vm.runInNewContext(source, {document, window, navigator: {connection}, URL, Promise});
  return {cards, document, window, hover, reducedMotion, connection, intersectionObservers, mutationObservers, timers,
    advance(ms) {
      const end = now + ms;
      while (true) {
        const next = [...timers].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        now = next[1].at; timers.delete(next[0]); next[1].action();
      }
      now = end;
    },
    intersect(card, value) { intersectionObservers[0].callback([{target: card, isIntersecting: value, intersectionRatio: value ? 1 : 0}]); },
    mutate() { mutationObservers[0].callback([]); }
  };
}
const enter = card => card.emit("pointerenter", {pointerType: "mouse"});
const click = card => card.button.emit("click");
const idle = card => {
  assert.equal(card.dataset.previewState, "idle");
  assert.equal(card.video.hasAttribute("src"), false);
  assert.equal(card.video.paused, true);
  assert.equal(card.video.muted, true);
  assert.equal(card.video.currentTime, 0);
  assert.equal(card.progress.value, 0);
  assert.equal(card.button.getAttribute("aria-pressed"), "false");
  assert.equal(card.sound.hidden, true);
};

test("manual playback owns its position across hover, pointer, matching filters and preference changes", async () => {
  for (const mode of ["button", "sound"]) for (const action of [
    f => f.cards[0].emit("pointerleave"),
    f => f.cards[0].emit("pointercancel"),
    f => enter(f.cards[1]),
    f => f.document.emit("gallery:filter"),
    f => { f.hover.matches = false; f.hover.emit("change"); },
    f => { f.reducedMotion.matches = true; f.reducedMotion.emit("change"); },
    f => { f.connection.saveData = true; f.connection.emit("change"); }
  ]) {
    const f = fixture({setup(cards) { cards[0].dataset.previewAudio = "true"; }}), card = f.cards[0];
    if (mode === "button") click(card); else enter(card);
    await flush();
    if (mode === "sound") card.sound.emit("click");
    card.video.currentTime = 5; card.video.emit("timeupdate");
    const source = card.video.src, loads = card.video.loadCount, plays = card.video.playCount;
    action(f); await flush();
    assert.equal(card.dataset.previewState, "playing");
    assert.equal(card.video.currentTime, 5); assert.equal(card.video.src, source);
    assert.equal(card.video.loadCount, loads); assert.equal(card.video.playCount, plays);
    assert.equal(card.video.muted, mode !== "sound");
    assert.equal(f.cards[1].video.playCount, 0);
  }
});

test("a media pause preserves the current frame and explicit resume continues at the same position", async () => {
  const f = fixture({setup(cards) { cards[0].dataset.previewAudio = "true"; }}), card = f.cards[0];
  click(card); await flush(); card.sound.emit("click");
  card.video.currentTime = 5; card.video.emit("timeupdate");
  const source = card.video.src, loads = card.video.loadCount, plays = card.video.playCount;
  card.video.pause();
  assert.equal(card.dataset.previewState, "paused");
  assert.equal(card.status.textContent, "Preview paused");
  assert.equal(card.button.getAttribute("aria-pressed"), "false");
  assert.equal(card.button.getAttribute("aria-label"), "Play preview");
  assert.equal(card.video.currentTime, 5); assert.equal(card.video.src, source);
  assert.equal(card.progress.value, 0.25); assert.equal(card.video.loadCount, loads);
  card.video.emit("playing");
  assert.equal(card.dataset.previewState, "paused"); assert.equal(card.video.playCount, plays);
  enter(f.cards[1]); card.emit("pointerleave"); card.emit("pointercancel");
  f.connection.saveData = true; f.connection.emit("change");
  assert.equal(card.dataset.previewState, "paused"); assert.equal(f.cards[1].video.playCount, 0);
  f.advance(12000); assert.equal(card.dataset.previewState, "paused");
  click(card); await flush();
  assert.equal(card.dataset.previewState, "playing"); assert.equal(card.video.currentTime, 5);
  assert.equal(card.video.src, source); assert.equal(card.video.loadCount, loads);
  assert.equal(card.video.playCount, plays + 1); assert.equal(card.video.muted, false);
});

test("unmuting an automatic preview keeps manual ownership on subsequent playing events", async () => {
  const f = fixture({setup(cards) { cards[0].dataset.previewAudio = "true"; }}), card = f.cards[0];
  enter(card); await flush(); card.sound.emit("click"); card.video.currentTime = 5;
  f.reducedMotion.matches = true; f.reducedMotion.emit("change");
  card.video.emit("playing");
  assert.equal(card.dataset.previewState, "playing");
  assert.equal(card.video.currentTime, 5); assert.equal(card.video.muted, false);
});

test("manual loading also survives hover and policy changes until its own first frame", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  click(card); enter(f.cards[1]); card.emit("pointerleave"); card.emit("pointercancel");
  f.reducedMotion.matches = true; f.reducedMotion.emit("change");
  f.document.emit("gallery:filter");
  assert.equal(card.dataset.previewState, "loading"); assert.equal(f.cards[1].video.playCount, 0);
  card.video.requests[0].resolve(); await flush();
  assert.equal(card.dataset.previewState, "playing"); assert.equal(f.timers.size, 0);
});

test("resuming a paused run cannot be failed by its superseded play request", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  click(card); card.video.currentTime = 5; card.video.pause();
  assert.equal(card.dataset.previewState, "paused");
  click(card); card.video.requests[1].resolve(); await flush();
  card.video.requests[0].reject(new Error("Old request interrupted by pause")); await flush();
  assert.equal(card.dataset.previewState, "playing");
  assert.equal(card.video.currentTime, 5); assert.equal(card.video.loadCount, 0);
});

test("pause-interrupted play rejection preserves a resumable frame instead of reporting a media error", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  click(card); card.video.currentTime = 5; card.video.pause();
  card.video.requests[0].reject(Object.assign(new Error("Playback was paused"), {name: "AbortError"})); await flush();
  assert.equal(card.dataset.previewState, "paused");
  assert.equal(card.video.currentTime, 5); assert.equal(card.video.hasAttribute("src"), true);
  assert.equal(card.video.loadCount, 0);
  click(card); card.video.requests[1].resolve(); await flush();
  assert.equal(card.dataset.previewState, "playing"); assert.equal(card.video.currentTime, 5);
});

test("genuine play rejection while paused reports the error and releases resources", async () => {
  for (const name of ["NotAllowedError", "NotSupportedError", "Error"]) {
    const f = fixture({playMode: "defer"}), card = f.cards[0];
    click(card); card.video.currentTime = 5; card.video.pause();
    card.video.requests[0].reject(Object.assign(new Error("AbortError text is not an error name"), {name}));
    await flush();
    assert.equal(card.dataset.previewState, "error");
    assert.equal(card.video.hasAttribute("src"), false); assert.equal(card.video.currentTime, 0);
    assert.equal(card.video.listenerCount(), 0); assert.equal(f.timers.size, 0);
  }
});

test("AbortError is not suppressed when the current media is no longer paused", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  click(card); card.video.pause(); card.video.paused = false;
  card.video.requests[0].reject(Object.assign(new Error("Request aborted"), {name: "AbortError"}));
  await flush();
  assert.equal(card.dataset.previewState, "error"); assert.equal(card.video.hasAttribute("src"), false);
  assert.equal(card.video.listenerCount(), 0); assert.equal(f.timers.size, 0);
});

test("manual playing and paused previews still release resources on explicit replacement or hidden lifecycle", async () => {
  for (const paused of [false, true]) for (const cancel of [
    f => f.document.emit("keydown", {key: "Escape"}),
    f => { f.document.hidden = true; f.document.emit("visibilitychange"); },
    f => { f.cards[0].hidden = true; f.document.emit("gallery:filter"); },
    f => f.intersect(f.cards[0], false),
    f => f.window.emit("pagehide", {persisted: false}),
    f => click(f.cards[1])
  ]) {
    const f = fixture({setup(cards) { cards[0].dataset.previewAudio = "true"; }}), card = f.cards[0];
    click(card); await flush(); card.sound.emit("click"); card.video.currentTime = 5;
    if (paused) card.video.pause();
    cancel(f); await flush(); idle(card);
    assert.equal(card.video.listenerCount(), 0); assert.equal(f.timers.size, 0);
  }
});

test('sound only unmutes the current preview after explicit activation and resets on every stop', async () => {
  for (const cancel of [f=>click(f.cards[0]),f=>{f.cards[0].hidden=true;f.document.emit('gallery:filter');},
    f=>{f.document.hidden=true;f.document.emit('visibilitychange');},f=>click(f.cards[1])]) {
    const f=fixture({setup(cards){cards[0].dataset.previewAudio='true';}}),card=f.cards[0];
    enter(card);await flush();assert.equal(card.sound.hidden,false);assert.equal(card.video.muted,true);
    const plays=card.video.playCount;let prevented=0,stopped=0;
    card.sound.emit('click',{preventDefault(){prevented++;},stopPropagation(){stopped++;}});
    assert.equal(card.video.muted,false);assert.equal(card.video.playCount,plays);
    assert.equal(prevented,1);assert.equal(stopped,1);assert.equal(card.sound.getAttribute('aria-pressed'),'true');
    assert.equal(card.status.textContent,'Preview with sound');
    cancel(f);idle(card);
  }
});

test('verified silent and unknown audio are distinct, without engine loading', async () => {
  const f=fixture({setup(cards){cards[0].dataset.previewAudio='false';}});
  assert.equal(f.cards[0].audioNote.textContent,'No audio track');
  assert.equal(f.cards[1].audioNote.textContent,'Audio unverified');
  enter(f.cards[0]);await flush();assert.equal(f.cards[0].sound.hidden,true);
  f.cards[0].sound.emit('click');assert.equal(f.cards[0].video.muted,true);
  enter(f.cards[1]);await flush();assert.equal(f.cards[1].sound.hidden,false);
  f.cards[1].sound.emit('click');assert.equal(f.cards[1].video.muted,false);
  f.cards[1].sound.emit('click');assert.equal(f.cards[1].video.muted,true);
});

test("initialization is source-free, silent and progressive", () => {
  const {cards} = fixture();
  for (const card of cards) {
    idle(card);
    assert.equal(card.video.playCount, 0); assert.equal(card.video.loadCount, 0);
    assert.equal(card.video.preload, "none"); assert.equal(card.video.autoplay, false);
    assert.equal(card.video.loop, true); assert.equal(card.dataset.previewAutoplay, "true");
    assert.equal(card.video.muted, true); assert.equal(card.video.defaultMuted, true);
    assert.equal(card.video.playsInline, true); assert.equal(card.video.tabIndex, -1);
    assert.equal(card.video.getAttribute("aria-hidden"), "true");
    assert.equal(card.progress.getAttribute("aria-hidden"), "true");
    assert.equal(card.button.hidden, false);
  }
});

test("hover immediately requests playback and leaving during loading releases it", async () => {
  const f = fixture({playMode: "defer", setup(cards) {
    cards[0].dataset.loadingLabel = "Loading preview…";
    cards[0].dataset.playingLabel = "Muted preview playing";
  }}), card = f.cards[0];
  enter(card);
  assert.equal(card.dataset.previewState, "loading");
  assert.equal(card.video.playCount, 1); assert.equal(f.timers.size, 1);
  assert.equal(card.video.hasAttribute("src"), true);
  assert.equal(card.status.textContent, "Loading preview…");
  card.emit("pointerleave");
  card.video.requests[0].resolve(); await flush();
  idle(card); assert.equal(card.status.textContent, "");
  assert.equal(card.video.loadCount, 1);
});

test("loading feedback becomes a playing label only after the first frame can play", async () => {
  const f = fixture({playMode: "defer", setup(cards) {
    cards[0].dataset.loadingLabel = "Loading preview…";
    cards[0].dataset.playingLabel = "Muted preview playing";
  }}), card = f.cards[0];
  enter(card); assert.equal(card.dataset.previewState, "loading");
  card.video.requests[0].resolve(); await flush();
  assert.equal(card.dataset.previewState, "playing");
  assert.equal(card.status.textContent, "Muted preview playing");
  enter(card); assert.equal(card.video.playCount, 1);
});

test("stalled loading times out, preserves retry, and clears the deadline on success", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  enter(card); f.advance(11999);
  assert.equal(card.dataset.previewState, "loading");
  f.advance(1);
  assert.equal(card.dataset.previewState, "error");
  assert.equal(card.video.hasAttribute("src"), false);
  assert.equal(card.status.textContent, card.dataset.errorLabel);
  card.video.mode = "resolve"; click(card); await flush();
  assert.equal(card.dataset.previewState, "playing");
  assert.equal(f.timers.size, 0);
  f.advance(12000); assert.equal(card.dataset.previewState, "playing");
  card.video.requests[0].resolve(); await flush();
  assert.equal(card.dataset.previewState, "playing");
});

test("deliberate hover plays muted media then leave resets and releases it", async () => {
  const f = fixture(), card = f.cards[0];
  enter(card); f.advance(250); await flush();
  assert.equal(card.dataset.previewState, "playing");
  assert.equal(card.video.src, "https://example.com/showcase/media/preview-0.mp4");
  assert.equal(card.button.textContent, "Stop preview");
  card.video.currentTime = 5; card.video.emit("timeupdate");
  assert.equal(card.progress.value, 0.25);
  assert.equal(card.progress.style.values["--preview-progress"], "25%");
  card.emit("pointerleave"); idle(card);
  assert.equal(card.video.loadCount, 1); assert.equal(card.button.textContent, "Play preview");
});

test("entering a new card immediately cancels the previous loading preview", async () => {
  const f = fixture({playMode: "defer"}), [first, second] = f.cards;
  enter(first); enter(second);
  idle(first); assert.equal(first.video.playCount, 1);
  assert.equal(second.video.playCount, 1);
  first.video.requests[0].resolve(); await flush(); idle(first);
  second.video.requests[0].resolve(); await flush();
  assert.equal(second.dataset.previewState, "playing");
  click(first); idle(second);
  assert.equal(first.dataset.previewState, "loading");
  assert.equal(second.video.listenerCount(), 0);
});

test("automatic previews honor pointer, reduced-motion and data-saving preferences", async () => {
  for (const options of [{hover: false}, {reducedMotion: true}, {saveData: true}, {noMatchMedia: true}]) {
    const f = fixture(options), card = f.cards[0];
    assert.equal(card.dataset.previewAutoplay, "false");
    enter(card); f.advance(1000); idle(card); assert.equal(card.video.playCount, 0);
    click(card); await flush();
    assert.equal(card.dataset.previewState, "playing"); assert.equal(card.video.muted, true);
    click(card); idle(card);
  }
  const f = fixture();
  f.cards[0].emit("pointerenter", {pointerType: "touch"}); f.advance(1000);
  idle(f.cards[0]); assert.equal(f.cards[0].video.playCount, 0);
});

test("lifting a touch pointer does not cancel explicit mobile playback", async () => {
  const f = fixture({hover: false}), card = f.cards[0];
  click(card); await flush(); card.emit("pointerleave", {pointerType: "touch"});
  assert.equal(card.dataset.previewState, "playing"); assert.equal(card.video.paused, false);
  click(card); idle(card);
});

test("explicit button activation stops propagation and preserves a label span", async () => {
  const f = fixture({labelSpan: true}), card = f.cards[0];
  let prevented = 0, stopped = 0;
  card.button.emit("click", {preventDefault() { prevented++; }, stopPropagation() { stopped++; }});
  await flush();
  assert.equal(prevented, 1); assert.equal(stopped, 1);
  assert.equal(card.label.textContent, "Stop preview"); assert.equal(card.button.textContent, "");
  assert.equal(card.button.getAttribute("aria-label"), "Stop preview");
});

test("motion, pointer and network policy changes cancel automatic playback and refresh manual-control visibility", async () => {
  for (const target of ["hover", "reducedMotion", "connection"]) {
    const f = fixture(), [first, second] = f.cards;
    enter(first); await flush(); enter(second);
    f[target].emit("change");
    idle(first); idle(second); assert.equal(f.timers.size, 0);
    f.advance(1000); assert.equal(second.video.playCount, 1);
  }
});

test("legacy media-query listeners also stop playback and detach on unload", async () => {
  const f = fixture({legacyMedia: true}), card = f.cards[0];
  enter(card); await flush(); f.reducedMotion.emit("change"); idle(card);
  f.window.emit("pagehide", {persisted: false});
  assert.equal(f.hover.listenerCount(), 0); assert.equal(f.reducedMotion.listenerCount(), 0);
});

test("offscreen, filtered, removed and CSS-hidden cards stop and cannot restart", async () => {
  for (const hide of [
    (f, card) => f.intersect(card, false),
    (f, card) => { card.hidden = true; f.mutate(); },
    (f, card) => { card.isConnected = false; f.mutate(); },
    (f, card) => { card.display = "none"; f.mutate(); },
    (f, card) => { card.visibility = "hidden"; f.mutate(); },
    (f, card) => { card.parentElement.hidden = true; f.mutate(); }
  ]) {
    const f = fixture(), card = f.cards[0];
    click(card); await flush(); hide(f, card); idle(card);
    click(card); enter(card); f.advance(1000); idle(card); assert.equal(card.video.playCount, 1);
  }
});

test("edge-touching intersection observations do not lock a visible card out", async () => {
  const f = fixture(), card = f.cards[0];
  f.intersectionObservers[0].callback([{target: card, isIntersecting: true, intersectionRatio: 0}]);
  click(card); await flush();
  assert.equal(card.dataset.previewState, "playing");
});

test("filter notifications and hidden documents cancel automatic loading previews", async () => {
  for (const notify of [f => f.document.emit("gallery:filter"), f => { f.document.hidden = true; f.document.emit("visibilitychange"); }]) {
    const f = fixture(), [first, second] = f.cards;
    enter(first); await flush(); enter(second); notify(f);
    idle(first); idle(second); f.advance(1000); assert.equal(second.video.playCount, 1);
  }
});

test("viewport checks protect starts and scroll fallback stops nested-scroll previews", async () => {
  const f = fixture({noIntersection: true}), card = f.cards[0];
  card.rect.top = 1000; card.rect.bottom = 1260;
  click(card); enter(card); f.advance(500); idle(card); assert.equal(card.video.playCount, 0);
  card.rect.top = 100; card.rect.bottom = 360;
  click(card); await flush();
  card.rect.bottom = -1; card.rect.top = -261;
  f.document.emit("scroll"); idle(card);
});

test("rejected autoplay and thrown play keep poster/details available for retry", async () => {
  for (const mode of ["reject", "throw"]) {
    const f = fixture({playMode: mode}), card = f.cards[0];
    enter(card); f.advance(250); await flush();
    assert.equal(card.dataset.previewState, "error"); assert.equal(card.video.hasAttribute("src"), false);
    assert.equal(card.video.paused, true); assert.equal(card.button.hidden, false);
    assert.equal(card.status.textContent, card.dataset.errorLabel);
    assert.equal(card.button.getAttribute("aria-pressed"), "false");
    card.video.mode = "resolve"; click(card); await flush();
    assert.equal(card.dataset.previewState, "playing"); assert.equal(card.status.textContent, "");
  }
});

test("media errors release resources; missing error text is harmless", async () => {
  const f = fixture({setup(cards) { cards[0].dataset.errorLabel = ""; }}), card = f.cards[0];
  click(card); await flush(); card.video.emit("error");
  assert.equal(card.dataset.previewState, "error"); assert.equal(card.status.textContent, "");
  assert.equal(card.video.hasAttribute("src"), false); assert.equal(card.video.listenerCount(), 0);
});

test("late automatic play fulfillment after leave cannot resurrect abandoned media", async () => {
  const f = fixture({playMode: "defer"}), card = f.cards[0];
  enter(card); assert.equal(card.dataset.previewState, "loading");
  card.emit("pointerleave"); card.video.requests[0].resolve(); await flush(); idle(card);
});

test("cancelled loading previews ignore late fulfillment or rejection after lifecycle changes", async () => {
  for (const cancel of [
    f => f.intersect(f.cards[0], false),
    f => { f.cards[0].hidden = true; f.mutate(); },
    f => { f.document.hidden = true; f.document.emit("visibilitychange"); },
    f => f.reducedMotion.emit("change"),
    f => f.document.emit("gallery:filter")
  ]) for (const completion of ["resolve", "reject"]) {
    const f = fixture({playMode: "defer"}), card = f.cards[0];
    enter(card); cancel(f);
    card.video.requests[0][completion](new Error("Cancelled")); await flush();
    idle(card); assert.equal(card.status.textContent, ""); assert.equal(card.video.listenerCount(), 0);
  }
});

test("a stale same-card play promise cannot pause or fail a newer session", async () => {
  for (const completion of ["resolve", "reject"]) {
    const f = fixture({playMode: "defer"}), card = f.cards[0];
    click(card); click(card); click(card);
    card.video.requests[1].resolve(); await flush();
    const pauses = card.video.pauseCount;
    card.video.requests[0][completion](new Error("Superseded")); await flush();
    assert.equal(card.dataset.previewState, "playing"); assert.equal(card.video.paused, false);
    assert.equal(card.video.pauseCount, pauses); assert.equal(card.video.listenerCount(), 6);
  }
});

test("late completion of a different card never interrupts the current card", async () => {
  const f = fixture({playMode: "defer"}), [first, second] = f.cards;
  click(first); click(second); second.video.requests[0].resolve(); await flush();
  first.video.requests[0].resolve(); await flush(); idle(first);
  assert.equal(second.dataset.previewState, "playing"); assert.equal(second.video.paused, false);
});

test("old browsers without play promises wait for the playing event", () => {
  const f = fixture({playMode: "undefined"}), card = f.cards[0];
  click(card); assert.equal(card.dataset.previewState, "loading");
  card.video.emit("playing"); assert.equal(card.dataset.previewState, "playing");
  card.video.emit("ended"); idle(card);
});

test("progress is finite and clamped for unknown or invalid media times", async () => {
  const f = fixture(), card = f.cards[0];
  click(card); await flush();
  for (const [time, duration, value] of [[-2, 10, 0], [12, 10, 1], [1, Infinity, 0], [NaN, 10, 0], [1, 0, 0]]) {
    card.video.currentTime = time; card.video.duration = duration; card.video.emit("timeupdate");
    assert.equal(card.progress.value, value);
  }
});

test("Escape and automatic pointer cancellation restore the poster", async () => {
  for (const [begin, cancel] of [[click, f => f.document.emit("keydown", {key: "Escape"})],
    [enter, f => f.cards[0].emit("pointercancel")]]) {
    const f = fixture(), card = f.cards[0]; begin(card); await flush(); cancel(f); idle(card);
  }
});

test("pagehide releases media, removes listeners, and rejects late completions", async () => {
  const f = fixture({playMode: "defer"}), [first, second] = f.cards;
  click(first); click(second); f.window.emit("pagehide", {persisted: false});
  idle(first); idle(second); assert.equal(f.timers.size, 0);
  for (const node of [first, second, first.button, second.button, f.document, f.window, f.hover, f.reducedMotion, f.connection]) {
    assert.equal(node.listenerCount(), 0);
  }
  assert.ok(f.intersectionObservers.every(observer => observer.disconnected));
  assert.ok(f.mutationObservers.every(observer => observer.disconnected));
  first.video.requests[0].resolve(); await flush(); idle(first);
  click(second); assert.equal(second.video.playCount, 1);
});

test("back-forward cache restores remain stopped but explicitly reusable", async () => {
  const f = fixture(), card = f.cards[0]; click(card); await flush();
  f.window.emit("pagehide", {persisted: true}); idle(card);
  assert.equal(f.intersectionObservers[0].disconnected, false);
  click(card); await flush(); assert.equal(card.dataset.previewState, "playing");
});

test("nonvideo previews and unsafe/invalid sources remain untouched static cards", () => {
  for (const setup of [
    cards => { cards[0].dataset.previewKind = "godot"; },
    cards => { cards[0].video.tagName = "IFRAME"; },
    cards => { cards[0].dataset.previewSrc = "javascript:alert(1)"; },
    cards => { cards[0].dataset.previewSrc = "  "; },
    cards => { cards[0].dataset.previewSrc = "https://[invalid"; }
  ]) {
    const f = fixture({count: 1, setup}), card = f.cards[0];
    enter(card); click(card); f.advance(500);
    assert.equal(card.video.playCount, 0); assert.equal(card.video.hasAttribute("src"), false);
    assert.equal(card.button.hidden, true); assert.equal(card.dataset.previewState, undefined);
  }
  fixture({count: 0});
});

(async () => {
  for (const {name, action} of tests) { await action(); console.log("PASS " + name); }
  console.log(tests.length + " preview control behavior tests passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
