(() => {
"use strict";
const button = document.querySelector("#copy-prompt");
const prompt = document.querySelector("#reusable-prompt");
const status = document.querySelector("#copy-status");
if (!button || !prompt || !status) return;
button.hidden = false;
button.addEventListener("click",async () => {
try {await navigator.clipboard.writeText(prompt.textContent); status.textContent = document.documentElement.lang.startsWith("zh") ? "提示词已复制。" : "Prompt copied.";}
catch (_) {
const range = document.createRange(); range.selectNodeContents(prompt);
const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
status.textContent = document.documentElement.lang.startsWith("zh") ? "已选中提示词，请使用复制快捷键。" : "Prompt selected. Use your copy shortcut.";
}
});
})();

(() => {
"use strict";
document.querySelectorAll(".audio-player").forEach(player => {
const audio = player.querySelector("audio");
if (!audio) return;
const buttons = Array.from(player.querySelectorAll("[data-audio-seek]"));
const ready = () => audio.readyState >= 1 && Number.isFinite(audio.duration) && audio.duration > 0 && !audio.error;
const update = () => buttons.forEach(button => { button.disabled = !ready(); });
for (const event of ["loadedmetadata", "durationchange", "emptied", "error"]) audio.addEventListener(event, update);
buttons.forEach(button => button.addEventListener("click", () => {
const delta = Number(button.dataset.audioSeek);
if (button.disabled || !ready() || !Number.isFinite(delta)) return;
const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
// User activation changes position only; never call play() or pause().
audio.currentTime = Math.max(0, Math.min(audio.duration, current + delta));
}));
update();
});
})();

(() => {
  "use strict";
  // The static HTML remains an ordinary native player without JavaScript.
  // Enhanced videos use on-demand, silent hover; an explicit watch action
  // switches to normal native controls and is never interrupted by hover.
  const videos = Array.from(document.querySelectorAll(".detail-video video[data-hover-preview]"));
  if (!videos.length) return;
  const hover = window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : null;
  const reduced = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const zh = String(document.documentElement.lang || "").startsWith("zh");
  const labels = zh ? {
    watch: "观看视频", stop: "停止观看", hover: "悬停即静音预览，点击观看", tap: "点击观看视频", loading: "正在加载视频…",
    preview: "静音预览中，点击观看", watching: "使用播放器控制声音与进度", error: "视频暂不可用，请重试或使用下载链接。",
    silent: "无音轨", unknown: "音轨未核验"
  } : {
    watch: "Watch video", stop: "Stop watching", hover: "Hover for muted preview; click to watch", tap: "Click to watch video", loading: "Loading video…",
    preview: "Muted preview; click to watch", watching: "Use player controls for sound and seeking", error: "Video unavailable. Retry or use the download link.",
    silent: "No audio track", unknown: "Audio unverified"
  };
  const entries = [], disposers = [];
  let active = null, destroyed = false;
  const automaticAllowed = () => Boolean(hover && hover.matches && !(reduced && reduced.matches) && !(connection && connection.saveData));
  function listen(target, event, action, options) {
    target.addEventListener(event, action, options);
    disposers.push(() => target.removeEventListener(event, action, options));
  }
  function state(entry, value) {
    entry.host.dataset.videoState = value;
    const watching = active && active.entry === entry && !active.automatic;
    entry.button.textContent = watching ? labels.stop : labels.watch;
    entry.button.setAttribute("aria-pressed", String(Boolean(watching)));
    entry.status.textContent = value === "error" ? labels.error : value === "loading" ? labels.loading :
      value === "preview" ? labels.preview : value === "watching" ? labels.watching : automaticAllowed() ? labels.hover : labels.tap;
  }
  function available(entry) {
    if (destroyed || document.hidden || entry.host.isConnected === false || entry.host.closest("[hidden], [aria-hidden='true']")) return false;
    if (window.getComputedStyle) {
      const style = window.getComputedStyle(entry.host);
      if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return false;
    }
    const rect = entry.video.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 &&
      rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
      rect.left < (window.innerWidth || document.documentElement.clientWidth);
  }
  function stop(entry, value = "idle") {
    if (active && active.entry === entry) {
      const old = active;
      active = null;
      old.dispose();
    }
    const video = entry.video;
    video.pause();
    video.muted = true;
    video.controls = false; // Empty native controls swallow clicks; show a clickable poster instead.
    video.loop = false;
    entry.nativeIntent = false;
    try { video.currentTime = 0; } catch (_) { /* Metadata may not exist yet. */ }
    video.removeAttribute("src");
    entry.sources.forEach(item => item.removeAttribute("src"));
    // load() ignores the preload hint in Chromium. Detach every source first
    // so releasing the old decoder cannot start a fresh background download.
    video.load();
    state(entry, value);
  }
  const stopAll = () => { if (active) stop(active.entry); };
  function start(entry, automatic, adoptNativePlayback = false) {
    if (!available(entry) || (automatic && !automaticAllowed())) return;
    // Passing another video must not interrupt intentional viewing or seeking.
    if (automatic && active && (!active.automatic || active.entry === entry)) return;
    stopAll();
    const video = entry.video;
    const run = {entry, automatic, timer: null, dispose() {}};
    let nativePauseObserved = false;
    active = run;
    const failed = error => {
      if (active !== run) return;
      // Pausing native controls while play() is pending is an intentional
      // interruption, not a failed video. Keep its source and seek position.
      if (!run.automatic && video.paused && error && error.name === "AbortError") {
        window.clearTimeout(run.timer);
        run.timer = null;
        state(entry, "watching");
      } else stop(entry, "error");
    };
    const armWatchdog = () => {
      window.clearTimeout(run.timer);
      const timer = window.setTimeout(() => { if (run.timer === timer) failed(); }, 12000);
      run.timer = timer;
    };
    const playing = () => {
      if (active !== run) {
        if (!active || active.entry !== entry) video.pause();
        return;
      }
      if (document.hidden || (run.automatic && (!automaticAllowed() || !available(entry)))) { stop(entry); return; }
      window.clearTimeout(run.timer);
      run.timer = null;
      state(entry, run.automatic ? "preview" : "watching");
    };
    const paused = () => {
      if (active !== run || run.automatic) return;
      nativePauseObserved = true;
      if (!video.paused) return;
      window.clearTimeout(run.timer);
      run.timer = null;
      state(entry, "watching");
    };
    const loading = (restart = false) => {
      if (active !== run || run.automatic || video.paused || (!restart && run.timer !== null)) return;
      state(entry, "loading");
      armWatchdog();
    };
    const handlers = {playing, pause: paused, play: () => loading(true), waiting: () => loading(), error: failed};
    Object.entries(handlers).forEach(([name, callback]) => video.addEventListener(name, callback));
    run.dispose = () => {
      window.clearTimeout(run.timer);
      Object.entries(handlers).forEach(([name, callback]) => video.removeEventListener(name, callback));
    };
    video.muted = automatic || entry.hasAudio === "false";
    video.controls = true;
    video.loop = automatic;
    if (!adoptNativePlayback) video.src = entry.source;
    state(entry, "loading");
    armWatchdog();
    if (adoptNativePlayback) return; // The native play action is already underway.
    try {
      const promise = video.play();
      if (promise && typeof promise.then === "function") Promise.resolve(promise).then(() => {
        if (active !== run || !nativePauseObserved) playing();
      }, error => {
        // A queued pause may reject this sole play promise after native resume.
        if (nativePauseObserved && error && error.name === "AbortError") return;
        failed(error);
      });
    } catch (_) { failed(); }
  }
  videos.forEach(video => {
    const host = video.parentElement;
    const sources = Array.from(video.querySelectorAll("source[src]"));
    const raw = video.getAttribute("src") || (sources[0] && sources[0].getAttribute("src"));
    if (!raw || !host) return;
    let source;
    try {
      const url = new URL(raw, document.baseURI);
      if (!["http:", "https:"].includes(url.protocol)) return;
      source = url.href;
    } catch (_) { return; }
    const toolbar = document.createElement("div");
    toolbar.className = "detail-video-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "video-watch";
    const status = document.createElement("span");
    status.className = "video-status";
    status.setAttribute("aria-live", "polite");
    toolbar.append(button, status);
    const hasAudio = video.dataset.previewAudio || "unknown";
    if (hasAudio !== "true") {
      const note = document.createElement("span");
      note.className = "video-audio-note";
      note.textContent = hasAudio === "false" ? labels.silent : labels.unknown;
      toolbar.append(note);
    }
    host.append(toolbar);
    // Keep the initial static SOURCE for native controls and no-JS fallback.
    // Do not load() during initialization: real Chromium downloads media after
    // an explicit load() even with preload=none and an offscreen poster.
    video.pause();
    video.muted = video.defaultMuted = true;
    video.autoplay = false;
    video.preload = "none";
    video.playsInline = true;
    video.tabIndex = 0;
    video.controls = true;
    video.loop = false;
    const entry = {host, video, button, status, source, sources, hasAudio, nativeIntent: false};
    entries.push(entry);
    state(entry, "idle");
    listen(host, "pointerenter", event => {
      if (event.pointerType !== "touch") start(entry, true);
    });
    listen(host, "pointerleave", event => {
      if (event.pointerType !== "touch" && active && active.entry === entry && active.automatic) stop(entry);
    });
    listen(host, "pointercancel", () => {
      if (active && active.entry === entry && active.automatic) stop(entry);
    });
    listen(button, "click", () => {
      if (active && active.entry === entry && !active.automatic) stop(entry);
      else start(entry, false);
    });
    const nativeIntent = () => {
      // Released posters are handled on click, never pointerdown: preparing a
      // source here would make that click download/restart the same media twice.
      if (!video.controls || !available(entry)) return;
      entry.nativeIntent = true;
      // A stopped player has no live sources. Restore one synchronously before
      // the native control's default action; never issue a second play() here.
      if (!video.hasAttribute("src") && !sources.some(item => item.hasAttribute("src"))) video.src = source;
      if (active && active.entry === entry && active.automatic) {
        // Native pause/seek/volume gestures keep their browser meaning. Merely
        // pressing pause must not make a muted hover preview suddenly audible.
        active.automatic = false;
        video.loop = false;
        state(entry, "watching");
      }
    };
    listen(video, "pointerdown", nativeIntent, {capture: true});
    const released = () => !video.controls && !video.hasAttribute("src") && !sources.some(item => item.hasAttribute("src"));
    listen(video, "click", event => {
      if (released() && available(entry)) {
        event.preventDefault();
        start(entry, false); // One poster click restores the source and native controls.
        return;
      }
      nativeIntent(); // Preserve every active native pause/seek/volume gesture.
    }, {capture: true});
    listen(video, "keydown", event => {
      if ([" ", "Enter"].includes(event.key) && released() && available(entry)) {
        // With no source, Chromium disables its native play control. Handle
        // this one restart ourselves; otherwise preserve native key behavior.
        event.preventDefault();
        start(entry, false);
        return;
      }
      if ([" ", "Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) nativeIntent();
    }, {capture: true});
    listen(video, "play", () => {
      if (active && active.entry === entry) return;
      if (!entry.nativeIntent || !available(entry)) { video.muted = true; video.pause(); return; }
      // Native controls start playback themselves. Adopt that session without
      // restarting it or fighting the browser's play/pause default action.
      start(entry, false, true);
    });
  });
  if (!entries.length) return;
  function stopOffscreen() {
    if (active && active.automatic && !available(active.entry)) stop(active.entry);
  }
  function policyChange() {
    if (active && active.automatic) stop(active.entry);
    entries.forEach(entry => {
      if (!active || active.entry !== entry) state(entry, "idle");
    });
  }
  [hover, reduced, connection].forEach(target => {
    if (!target) return;
    if (target.addEventListener) listen(target, "change", policyChange);
    else if (target.addListener) {
      target.addListener(policyChange);
      disposers.push(() => target.removeListener(policyChange));
    }
  });
  listen(document, "visibilitychange", () => { if (document.hidden) stopAll(); });
  listen(document, "keydown", event => { if (event.key === "Escape" && !document.fullscreenElement) stopAll(); });
  listen(document, "scroll", stopOffscreen, {capture: true, passive: true});
  listen(window, "resize", stopOffscreen, {passive: true});
  if (window.IntersectionObserver) {
    const observer = new window.IntersectionObserver(stopOffscreen, {threshold: 0});
    entries.forEach(entry => observer.observe(entry.video));
    disposers.push(() => observer.disconnect());
  }
  listen(window, "pagehide", event => {
    stopAll();
    if (!event.persisted) {
      destroyed = true;
      disposers.splice(0).forEach(dispose => dispose());
    }
  });
})();
