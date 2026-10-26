(() => {
  "use strict";
  // Only opt-in video elements are managed here. Interactive demos remain links;
  // hovering a card never creates an iframe or starts an application/engine.
  const cards = Array.from(document.querySelectorAll(".case-card[data-preview-src]"));
  if (!cards.length) return;

  const hover = window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : null;
  const reducedMotion = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const entries = [];
  const disposers = [];
  let active = null;
  let destroyed = false;
  const zh = String(document.documentElement.lang || '').startsWith('zh');
  const audioLabels = zh ? {on:'开启声音', off:'静音', silent:'无音轨', unknown:'音轨未核验', playing:'有声预览中'}
    : {on:'Enable sound', off:'Mute', silent:'No audio track', unknown:'Audio unverified', playing:'Preview with sound'};

  function updateSound(entry) {
    if (entry.sound) {
      const enabled = !entry.video.muted;
      entry.sound.textContent = enabled ? audioLabels.off : audioLabels.on;
      entry.sound.setAttribute('aria-label', entry.sound.textContent);
      entry.sound.setAttribute('aria-pressed', String(enabled));
      entry.sound.hidden = entry.hasAudio === 'false' || entry.card.dataset.previewState !== 'playing';
    }
    if (entry.status && entry.card.dataset.previewState === 'playing') {
      entry.status.textContent = entry.video.muted ? entry.playingLabel : audioLabels.playing;
    }
  }

  function listen(target, event, action, options) {
    target.addEventListener(event, action, options);
    disposers.push(() => target.removeEventListener(event, action, options));
  }

  function setState(entry, state) {
    entry.card.dataset.previewState = state;
    const busy = state === "loading" || state === "playing";
    const label = busy ? entry.button.dataset.stopLabel : entry.button.dataset.playLabel;
    if (label) {
      (entry.button.querySelector(".preview-toggle-label") || entry.button).textContent = label;
      entry.button.setAttribute("aria-label", label);
      entry.button.title = label;
    }
    entry.button.setAttribute("aria-pressed", String(busy));
    if (entry.status) entry.status.textContent = state === "error" ? entry.errorLabel
      : state === "loading" ? entry.loadingLabel : state === "playing" ? entry.playingLabel
      : state === "paused" ? entry.pausedLabel : "";
    updateSound(entry);
  }

  function progress(entry) {
    if (!entry.progress) return;
    const {duration, currentTime} = entry.video;
    const value = Number.isFinite(duration) && duration > 0 && Number.isFinite(currentTime)
      ? Math.max(0, Math.min(1, currentTime / duration)) : 0;
    entry.progress.max = 1;
    entry.progress.value = value;
    entry.progress.style.setProperty("--preview-progress", (value * 100) + "%");
  }

  function resetProgress(entry) {
    if (!entry.progress) return;
    entry.progress.max = 1;
    entry.progress.value = 0;
    entry.progress.style.setProperty("--preview-progress", "0%");
  }

  function available(entry) {
    if (destroyed || document.hidden || entry.card.hidden || entry.card.isConnected === false || !entry.inViewport) return false;
    if (entry.card.closest("[hidden], [aria-hidden='true']")) return false;
    if (window.getComputedStyle) {
      const style = window.getComputedStyle(entry.card);
      if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return false;
    }
    const rect = entry.card.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 &&
      rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
      rect.left < (window.innerWidth || document.documentElement.clientWidth);
  }

  const canAutoplay = () => Boolean(hover && hover.matches && !(reducedMotion && reducedMotion.matches) && !(connection && connection.saveData));

  function stop(entry, state = "idle") {
    if (active && active.entry === entry) {
      const previous = active;
      active = null; // Invalidate callbacks before pause/load dispatch media events.
      previous.removeListeners();
    }
    entry.video.pause();
    entry.video.muted = true;
    try { entry.video.currentTime = 0; } catch (_) { /* Metadata may not exist yet. */ }
    // Removing src then load() releases the decoder and cancels pending fetches.
    // Never assign src="", which could fetch the page itself in some browsers.
    if (entry.video.hasAttribute("src")) {
      entry.video.removeAttribute("src");
      entry.video.load();
    }
    resetProgress(entry);
    setState(entry, state);
  }

  function stopAll() {
    if (active) stop(active.entry);
  }

  function stopUnavailable() {
    if (active && !available(active.entry)) stop(active.entry);
  }

  function start(entry, automatic) {
    if (!available(entry) || (automatic && !canAutoplay())) { stop(entry); return; }
    const resuming = active && active.entry === entry && entry.card.dataset.previewState === "paused";
    if (resuming) {
      active.removeListeners();
      active = null;
    } else stopAll();
    const video = entry.video;
    const run = {entry, automatic, loadingTimer: null, removeListeners: () => {}};
    let pauseObserved = false;
    active = run;
    setState(entry, "loading");

    const failed = () => { if (active === run) stop(entry, "error"); };
    const armWatchdog = () => {
      window.clearTimeout(run.loadingTimer);
      const timer = window.setTimeout(() => { if (run.loadingTimer === timer) failed(); }, 12000);
      run.loadingTimer = timer;
    };
    const paused = event => {
      if (active !== run) return;
      // A queued pause may be delivered after native playback already resumed.
      if (event) pauseObserved = true;
      if (!video.paused) return;
      window.clearTimeout(run.loadingTimer);
      run.loadingTimer = null;
      setState(entry, "paused");
      progress(entry);
    };
    const loading = () => {
      if (active !== run || video.paused) return;
      setState(entry, "loading");
      armWatchdog();
    };
    const playing = () => {
      if (active !== run) {
        // A late play() fulfillment must not resurrect an abandoned card, nor
        // pause a newer request that happens to reuse the same video element.
        if (!active || active.entry !== entry) video.pause();
        return;
      }
      if (!available(entry) || (run.automatic && !canAutoplay())) { stop(entry); return; }
      if (video.paused) { paused(); return; }
      window.clearTimeout(run.loadingTimer);
      run.loadingTimer = null;
      setState(entry, "playing");
      progress(entry);
    };
    const update = () => { if (active === run) progress(entry); };
    const ended = () => { if (active === run) stop(entry); };
    const listeners = {playing, play: loading, pause: paused, error: failed, timeupdate: update, durationchange: update, ended};
    Object.entries(listeners).forEach(([event, action]) => video.addEventListener(event, action));
    run.removeListeners = () => {
      window.clearTimeout(run.loadingTimer);
      Object.entries(listeners).forEach(([event, action]) => video.removeEventListener(event, action));
    };
    // A stalled network or unresolved play promise must not leave a card busy
    // forever. Manual retry remains available and starts a fresh bounded request.
    armWatchdog();

    // Source assignment happens only after a deliberate hover or button press.
    if (!resuming) {
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.src = entry.source;
    }
    try {
      const promise = video.play();
      if (promise && typeof promise.then === "function") Promise.resolve(promise).then(() => {
        // Native playing events own completion after a pause/resume interruption.
        if (active !== run || !pauseObserved) playing();
      }, error => {
        if (active !== run) return;
        if (pauseObserved && error?.name === "AbortError") return;
        failed();
      });
      // Browsers without a play promise are handled by the playing event.
    } catch (_) { failed(); }
  }

  function hoverStart(entry, event) {
    if (event.pointerType === "touch" || !canAutoplay() || !available(entry)) return;
    if (active && (!active.automatic || active.entry === entry)) return;
    // The whole card is the hover target. Request the first frame immediately;
    // retain the poster and show loading feedback until playback really starts.
    start(entry, true);
  }

  cards.forEach(card => {
    const video = card.querySelector(".card-preview");
    const button = card.querySelector(".preview-toggle");
    if (card.dataset.previewKind !== "video" || !video || video.tagName !== "VIDEO" || !button) return;
    if (!card.dataset.previewSrc || !card.dataset.previewSrc.trim()) return;
    let source;
    try {
      const url = new URL(card.dataset.previewSrc, document.baseURI);
      if (url.protocol !== "https:" && url.protocol !== "http:") return;
      source = url.href;
    } catch (_) { return; }
    const status = card.querySelector(".preview-status");
    const entry = {card, video, button, source, status, progress: card.querySelector(".preview-progress"),
      sound:card.querySelector('.preview-sound'), hasAudio:card.dataset.previewAudio || 'unknown',
      inViewport: true,
      loadingLabel: card.dataset.loadingLabel || "", playingLabel: card.dataset.playingLabel || "",
      pausedLabel: card.dataset.pausedLabel || (zh ? "预览已暂停" : "Preview paused"),
      errorLabel: card.dataset.errorLabel || button.dataset.errorLabel || (status && status.dataset.errorLabel) || ""};
    entries.push(entry);
    card.dataset.previewAutoplay = String(canAutoplay());
    video.autoplay = false;
    video.loop = true;
    video.preload = "none";
    video.muted = true;
    video.defaultMuted = true;
    video.playsInline = true;
    video.tabIndex = -1;
    video.setAttribute("aria-hidden", "true");
    if (entry.progress) entry.progress.setAttribute("aria-hidden", "true");
    // The static template leaves controls hidden, so failed/disabled JS keeps
    // ordinary poster and detail links usable with no dead preview button.
    button.hidden = false;
    const audioNote = card.querySelector('.preview-audio-note');
    if (audioNote && entry.hasAudio !== 'true') {
      audioNote.textContent = entry.hasAudio === 'false' ? audioLabels.silent : audioLabels.unknown;
      audioNote.hidden = false;
    }
    setState(entry, "idle");
    resetProgress(entry);
    listen(card, "pointerenter", event => hoverStart(entry, event));
    listen(card, "pointerleave", event => {
      // Touch dispatches pointerleave when contact ends, often around click.
      // Lifting the finger must not undo explicit mobile playback immediately.
      if (event.pointerType === "touch") return;
      if (active && active.entry === entry && active.automatic) stop(entry);
    });
    listen(card, "pointercancel", () => {
      if (active && active.entry === entry && active.automatic) stop(entry);
    });
    listen(button, "click", event => {
      event.preventDefault();
      event.stopPropagation();
      if (active && active.entry === entry && entry.card.dataset.previewState !== "paused") stop(entry);
      else start(entry, false); // Explicit activation also works on touch/reduced-motion/data-saving devices.
    });
    if (entry.sound) listen(entry.sound, 'click', event => {
      event.preventDefault();
      event.stopPropagation();
      // Only this explicit click can unmute the currently playing preview.
      // Do not restart video or navigate the card when toggling sound.
      if (!active || active.entry !== entry || entry.card.dataset.previewState !== 'playing' || entry.hasAudio === 'false') return;
      video.muted = !video.muted;
      if (!video.muted) active.automatic = false;
      updateSound(entry);
    });
  });
  if (!entries.length) return;

  function policyChange() {
    if (active && active.automatic) stopAll();
    entries.forEach(entry => { entry.card.dataset.previewAutoplay = String(canAutoplay()); });
  }
  [hover, reducedMotion, connection].forEach(target => {
    if (!target) return;
    if (target.addEventListener) listen(target, "change", policyChange);
    else if (target.addListener) {
      target.addListener(policyChange);
      disposers.push(() => target.removeListener(policyChange));
    }
  });
  listen(document, "visibilitychange", () => { if (document.hidden) stopAll(); });
  listen(document, "gallery:filter", () => {
    if (active && active.automatic) stopAll();
    else stopUnavailable();
  });
  listen(document, "keydown", event => { if (event.key === "Escape") stopAll(); });

  if (window.IntersectionObserver) {
    const observer = new window.IntersectionObserver(changes => {
      changes.forEach(change => {
        const entry = entries.find(item => item.card === change.target);
        if (!entry) return;
        // With threshold 0 an edge-touching entry can report ratio 0 before
        // moving inside without another callback. Geometry is checked on start.
        entry.inViewport = change.isIntersecting;
        if (!entry.inViewport) stop(entry);
      });
    }, {threshold: 0});
    entries.forEach(entry => observer.observe(entry.card));
    disposers.push(() => observer.disconnect());
  } else {
    // Scroll capture covers nested scroll containers as well as the page.
    listen(document, "scroll", stopUnavailable, {capture: true, passive: true});
    listen(window, "resize", stopUnavailable, {passive: true});
  }

  if (window.MutationObserver) {
    const observer = new window.MutationObserver(stopUnavailable);
    // Visibility can change through the card or an ancestor. Child-list
    // changes also catch removal while a play promise is still pending.
    observer.observe(document.documentElement, {childList: true, subtree: true,
      attributes: true, attributeFilter: ["hidden", "class", "style", "aria-hidden"]});
    disposers.push(() => observer.disconnect());
  }

  listen(window, "pagehide", event => {
    stopAll();
    // Preserve the controller for Back/Forward Cache restores, without resuming
    // playback. A real unload disposes observers and all registered listeners.
    if (!event.persisted) {
      destroyed = true;
      disposers.splice(0).forEach(dispose => dispose());
    }
  });
})();
