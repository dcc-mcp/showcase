/* Production Web audio. Public Web Audio APIs only; no engine internals or meters.
 * The Web export uses Godot's Dummy driver, leaving this as the sole context.
 * Native exports retain their AudioStreamPlayers in tide_audio.gd.
 */
(function (root) {
  'use strict';
  const NAMES = ['music', 'chart_read', 'key_pickup', 'pearl_pickup', 'beacon_resolve'];
  const DURATIONS = [32, .72, 1.05, 1.65, 4.8];
  const gainForDB = db => Math.pow(10, db / 20);

  function createWebAudio(host) {
    const document = host.document || null;
    let nativeFocus = true;
    let windowFocused = !document || typeof document.hasFocus !== 'function' || document.hasFocus();
    let documentVisible = !document || document.visibilityState === 'visible';
    let context = null, master = null, musicGain = null, cueGain = null;
    let buffers = null, music = null, cue = null, musicAt = 0, cueEnd = 0;
    let status = 'idle', error = '', muted = false;
    let focusActive = nativeFocus && windowFocused && documentVisible;
    let started = false, startPending = false, startCount = 0, trigger = '';
    let cueCounts = [0, 0, 0, 0], initialization = null, closing = null;
    let disposed = false, generation = 0, abort = null;
    let focusWork = Promise.resolve(), focusRevision = 0;
    let initAttempt = null, startAttempt = null;

    function deadline(operation, milliseconds, message, expire = () => {}) {
      let timer;
      const timeout = new Promise((_, reject) => {
        timer = host.setTimeout(() => {
          expire();
          reject(new Error(message));
        }, milliseconds);
      });
      return Promise.race([operation, timeout]).finally(() => host.clearTimeout(timer));
    }

    function fail(reason) {
      error = reason instanceof Error ? reason.message : String(reason);
      status = 'error';
      return false;
    }
    function ready() {
      return !!buffers && !!context && !disposed && context.state !== 'closed';
    }
    function applyMute() {
      // The value setter updates the intrinsic value immediately and schedules
      // the same current-time event. Suspension can precede the next quantum;
      // a queued-only event would leave the paused parameter at its old value.
      if (master && !disposed) master.gain.value = muted || !focusActive ? 0 : 1;
    }
    function stopSource(source) {
      if (!source) return;
      // stop() is harmless after natural completion; disconnect also removes the
      // old cue path immediately when a later story cue replaces it.
      try { source.stop(); } catch (_) { /* already stopped */ }
      source.disconnect();
    }
    function stopCue() {
      const previous = cue;
      cue = null;
      cueEnd = 0;
      stopSource(previous);
    }
    function reconcileFocus() {
      const revision = ++focusRevision;
      // Serialize suspend/resume so rapid focus changes cannot complete in the
      // opposite order. A stale request never resumes a pre-Begin context.
      focusWork = focusWork.then(async () => {
        if (disposed || !started || revision !== focusRevision) return;
        if (focusActive) {
          if (context.state !== 'running') {
            const resumed = context.resume();
            // An expired focus resume may still settle later. Preserve the
            // latest focus request, rather than allowing stale focus to win.
            Promise.resolve(resumed).then(() => {
              if (!disposed && revision !== focusRevision) reconcileFocus();
            }, () => {});
            await deadline(resumed, 10000, 'Audio focus resume timed out');
          }
          if (!disposed && revision === focusRevision && context.state !== 'running') {
            throw new Error('Audio context did not resume');
          }
        } else if (context.state !== 'suspended') {
          await context.suspend();
        }
        if (!disposed && revision === focusRevision && music) {
          status = 'ready';
          error = '';
        }
      }).catch(reason => { if (!disposed) fail(reason); });
      return focusWork;
    }

    function initialize(assetUrlMap) {
      if (disposed) return Promise.resolve(false);
      if (initialization) return initialization;
      if (ready()) {
        // A failed resume retains decoded assets. Retry returns to a usable
        // opening card but does not resume or create a source without Begin.
        if (!started || music) { status = 'ready'; error = ''; }
        return Promise.resolve(true);
      }
      status = 'loading';
      error = '';
      const version = generation;
      const attempt = {expired: false, abort: null};
      initAttempt = attempt;
      const work = (async () => {
        const urls = typeof assetUrlMap === 'string' ? JSON.parse(assetUrlMap) : assetUrlMap;
        if (!urls || NAMES.some(name => typeof urls[name] !== 'string' || !urls[name].trim())) {
          throw new Error('All five original audio URLs are required');
        }
        if (!context) {
          const Context = host.AudioContext || host.webkitAudioContext;
          if (!Context) throw new Error('Web Audio is unavailable');
          context = new Context({latencyHint: 'interactive'});
        }
        if (!master) {
          try {
            master = context.createGain();
            musicGain = context.createGain();
            cueGain = context.createGain();
            musicGain.gain.setValueAtTime(gainForDB(-40), context.currentTime);
            cueGain.gain.setValueAtTime(gainForDB(-3), context.currentTime);
            musicGain.connect(master);
            cueGain.connect(master);
            applyMute();
            master.connect(context.destination);
          } catch (reason) {
            // Even graph-construction retries reuse the already-created context.
            for (const node of [musicGain, cueGain, master]) if (node) node.disconnect();
            master = musicGain = cueGain = null;
            throw reason;
          }
        }
        // Initializing, restoring preferences and decoding must never activate
        // playback, even if the document had unrelated prior user activation.
        if (context.state !== 'suspended') await context.suspend();
        if (disposed || version !== generation || attempt.expired || initAttempt !== attempt) return false;
        abort = new host.AbortController();
        attempt.abort = abort;
        const decoded = await Promise.all(NAMES.map(async (name, index) => {
          const response = await host.fetch(urls[name], {signal: attempt.abort.signal});
          if (!response.ok) throw new Error('Audio fetch failed: ' + name + ' (' + response.status + ')');
          const buffer = await context.decodeAudioData(await response.arrayBuffer());
          if (!Number.isFinite(buffer.duration) || Math.abs(buffer.duration - DURATIONS[index]) > .02) {
            throw new Error('Unexpected original audio duration: ' + name);
          }
          return buffer;
        }));
        if (disposed || version !== generation || attempt.expired || initAttempt !== attempt) return false;
        buffers = decoded;
        status = 'ready';
        return true;
      })();
      initialization = deadline(work, 15000, 'Audio initialization timed out', () => {
        attempt.expired = true;
        if (attempt.abort) attempt.abort.abort();
      }).catch(reason => disposed || initAttempt !== attempt ? false : fail(reason)).finally(() => {
        if (initAttempt === attempt) initialization = null;
      });
      return initialization;
    }

    function quarantineExpiredResume(attempt) {
      const otherLiveAttempt = startAttempt !== attempt && startPending && !startAttempt.expired;
      if (disposed || !attempt.expired || started || otherLiveAttempt || context.state !== 'running') return;
      // resume() cannot be cancelled. If an expired request later unlocks the
      // empty context, suspend it again; only another actual Begin can start it.
      Promise.resolve(context.suspend()).catch(reason => { if (!disposed) fail(reason); }).finally(() => {
        if (!disposed && started && focusActive) reconcileFocus();
      });
    }

    function start(sourceTrigger) {
      if (!ready() || startPending || typeof sourceTrigger !== 'string' || !sourceTrigger.trim()) return false;
      // Only a real Begin callback may unlock audio. No timer, focus handler,
      // decoding completion or preference restore can create the first source.
      if (!host.navigator || !host.navigator.userActivation || !host.navigator.userActivation.isActive) {
        return fail('Begin requires an active user gesture');
      }
      if (!focusActive) return fail('Begin requires the focused game');
      if (started && !music) return fail('Original looping music is unavailable');
      if (started && context.state === 'running') {
        // A late focus resume may already have restored the original voice.
        // Its explicit Retry gesture acknowledges the error without a new
        // resume, source, fade, or logical start.
        if (status !== 'error') return false;
        status = 'ready';
        error = '';
        return true;
      }
      const version = generation;
      const attempt = {expired: false};
      startAttempt = attempt;
      startPending = true;
      error = '';
      if (!started) trigger = sourceTrigger;
      let resume;
      try {
        // Deliberately called before any await, in the actual game input callback.
        resume = context.resume();
      } catch (reason) {
        startPending = false;
        return fail(reason);
      }
      Promise.resolve(resume).then(() => quarantineExpiredResume(attempt), () => {});
      deadline(resume, 10000, 'Audio resume timed out', () => {
        attempt.expired = true;
        quarantineExpiredResume(attempt);
      }).then(() => {
        if (disposed || version !== generation || attempt.expired || startAttempt !== attempt) return;
        if (context.state !== 'running') throw new Error('Audio context did not resume');
        if (!started) {
          const source = context.createBufferSource();
          source.buffer = buffers[0];
          source.loop = true;
          source.loopStart = 0;
          source.loopEnd = 32;
          source.connect(musicGain);
          musicAt = context.currentTime;
          musicGain.gain.cancelScheduledValues(musicAt);
          musicGain.gain.setValueAtTime(gainForDB(-40), musicAt);
          // Linear dB fade, scheduled on the audio clock, independent of frames.
          musicGain.gain.exponentialRampToValueAtTime(gainForDB(-5), musicAt + 1.5);
          try { source.start(musicAt, 0); }
          catch (reason) { source.disconnect(); throw reason; }
          music = source;
          started = true;
          startCount += 1;
          source.onended = () => {
            if (music !== source) return;
            music = null;
            source.disconnect();
            if (!disposed) fail('Looping music ended unexpectedly');
          };
        }
        status = 'ready';
        applyMute();
        // Focus may have changed while resume was pending. The shared gain was
        // muted synchronously and suspension now freezes the original source.
        reconcileFocus();
      }).catch(reason => { if (!disposed && startAttempt === attempt) fail(reason); }).finally(() => {
        if (startAttempt === attempt) startPending = false;
      });
      return true;
    }

    function setMuted(value) {
      muted = !!value;
      applyMute();
      return muted;
    }
    function setFocusActive(value) {
      nativeFocus = !!value;
      return updateFocus();
    }
    function updateFocus() {
      const effective = nativeFocus && windowFocused && documentVisible;
      if (focusActive === effective) return focusWork;
      focusActive = effective;
      applyMute();
      return reconcileFocus();
    }
    function onWindowFocus() {
      windowFocused = true;
      documentVisible = !document || document.visibilityState === 'visible';
      updateFocus();
    }
    function onWindowBlur() {
      windowFocused = false;
      updateFocus();
    }
    function onVisibilityChange() {
      documentVisible = document.visibilityState === 'visible';
      if (typeof document.hasFocus === 'function') windowFocused = document.hasFocus();
      updateFocus();
    }
    // Canvas focus notifications alone do not cover switching tabs or windows.
    // These are ordinary production DOM listeners, never dispatched by the game.
    if (typeof host.addEventListener === 'function') {
      host.addEventListener('focus', onWindowFocus);
      host.addEventListener('blur', onWindowBlur);
    }
    if (document) document.addEventListener('visibilitychange', onVisibilityChange);
    function playCue(index) {
      if (!ready() || !started || !Number.isInteger(index) || index < 0 || index >= 4 || cueCounts[index]) return false;
      stopCue();
      let source;
      try {
        source = context.createBufferSource();
        source.buffer = buffers[index + 1];
        source.connect(cueGain);
        source.start(context.currentTime, 0);
      } catch (reason) {
        if (source) source.disconnect();
        return fail(reason);
      }
      cue = source;
      cueEnd = context.currentTime + source.buffer.duration;
      cueCounts[index] += 1;
      source.onended = () => {
        if (cue === source) cue = null;
        source.disconnect();
      };
      return true;
    }
    function resetCues() {
      cueCounts = [0, 0, 0, 0];
      stopCue();
    }
    function getState() {
      const running = !!context && context.state === 'running' && !disposed;
      const cueAlive = !!cue && context.currentTime < cueEnd && !disposed;
      return JSON.stringify({backend: 'web_audio', status, ready: ready(), error,
        started, start_pending: startPending, start_count: startCount, trigger,
        muted, focus_active: focusActive, cue_counts: cueCounts.slice(),
        native_focus_active: nativeFocus, window_focused: windowFocused, document_visible: documentVisible,
        music_playing: !!music && running, cue_playing: cueAlive && running,
        music_paused: !!music && !running, cue_paused: cueAlive && !running,
        music_position: music && !disposed ? Math.max(0, context.currentTime - musicAt) % 32 : 0,
        bus_muted: muted || !focusActive, music_loop: !!music && music.loop,
        context_state: context ? context.state : 'unavailable'});
    }
    function close() {
      if (closing) return closing;
      disposed = true;
      generation += 1;
      focusRevision += 1;
      if (typeof host.removeEventListener === 'function') {
        host.removeEventListener('focus', onWindowFocus);
        host.removeEventListener('blur', onWindowBlur);
      }
      if (document) document.removeEventListener('visibilitychange', onVisibilityChange);
      status = 'closing';
      startPending = false;
      if (abort) abort.abort();
      const previousMusic = music;
      music = null;
      stopSource(previousMusic);
      stopCue();
      for (const node of [musicGain, cueGain, master]) if (node) node.disconnect();
      closing = (async () => {
        if (context && context.state !== 'closed') await context.close();
        status = 'closed';
        return true;
      })().catch(fail);
      return closing;
    }
    return {initialize, start, setMuted, setFocusActive, playCue, resetCues, getState, close};
  }
  root.TidalWebAudio = createWebAudio(root);
  if (typeof module !== 'undefined') module.exports = {createWebAudio};
}(typeof window === 'undefined' ? globalThis : window));
