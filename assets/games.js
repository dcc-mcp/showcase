(() => {
  'use strict';
  const key = 'showcase:game-intent';
  // A one-use intent preserves the explicit gallery Start click across navigation.
  // Opening/bookmarking a game URL alone never starts the engine.
  document.querySelectorAll('[data-game-launch]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      try { sessionStorage.setItem(key, JSON.stringify({slug:link.dataset.gameLaunch, at:Date.now()})); } catch (_) {}
    });
  });
  const stage = document.querySelector('[data-game-stage]');
  if (!stage) return;
  const zh = document.documentElement.lang.startsWith('zh');
  const t = zh ? {
    title:'游戏画面', loading:'正在加载游戏…首次启动可能需要片刻。', running:'已启动。点击或轻触游戏画面即可操作。',
    closed:'游戏已退出，运行资源已释放。', error:'游戏加载失败。请检查网络及 WebGL 2 支持，然后重试。',
    retry:'重试', start:'开始游戏', sound:'点击开声', mute:'静音', fullscreen:'浏览器暂时无法进入全屏。',
  } : {
    title:'Game stage', loading:'Loading the game… The first launch may take a moment.', running:'Ready to play. Click or tap the game to focus it.',
    closed:'Game closed. Runtime resources released.', error:'The game could not load. Check your connection and WebGL 2 support, then retry.',
    retry:'Retry', start:'Start game', sound:'Enable sound', mute:'Mute', fullscreen:'Fullscreen is unavailable in this browser.',
  };
  const holder = stage.querySelector('[data-game-frame]');
  const poster = stage.querySelector('[data-game-poster]');
  const start = stage.querySelector('[data-game-start]');
  const status = document.querySelector('[data-game-status]');
  const exit = document.querySelector('[data-game-exit]');
  const reset = document.querySelector('[data-game-reset]');
  const full = document.querySelector('[data-game-fullscreen]');
  const sound = document.querySelector('[data-game-sound]');
  const destination = new URL(stage.dataset.gameUrl, location.href);
  if (destination.origin !== location.origin) return;
  destination.searchParams.set('lang', zh ? 'zh' : 'en');
  destination.searchParams.set('embed', '1');
  let frame = null, timeout = null, enabled = false;
  start.hidden = false;
  function send(type) { frame?.contentWindow?.postMessage({type:'showcase:' + type}, destination.origin); }
  function stop(message, failed = false) {
    clearTimeout(timeout);
    frame = null;
    holder.replaceChildren();
    poster.hidden = false;
    start.hidden = false;
    start.textContent = failed ? t.retry : t.start;
    [exit, reset, full, sound].forEach(button => { button.hidden = true; });
    stage.dataset.state = failed ? 'error' : 'idle';
    status.textContent = message;
    enabled = false;
  }
  function launch() {
    if (frame) return;
    poster.hidden = true;
    stage.dataset.state = 'loading';
    status.textContent = t.loading;
    exit.hidden = false;
    frame = document.createElement('iframe');
    frame.title = document.querySelector('h1').textContent + ' · ' + t.title;
    frame.allow = 'autoplay; fullscreen';
    frame.setAttribute('allowfullscreen', '');
    frame.src = destination.href;
    frame.addEventListener('error', () => stop(t.error, true));
    holder.append(frame);
    timeout = setTimeout(() => stop(t.error, true), 125000);
  }
  window.addEventListener('message', event => {
    if (!frame || event.source !== frame.contentWindow || event.origin !== destination.origin) return;
    if (event.data?.type === 'showcase:ready') send('start');
    if (event.data?.type !== 'showcase:state') return;
    if (event.data.state === 'error') { stop(t.error, true); start.focus(); }
    if (event.data.state === 'running') {
      clearTimeout(timeout);
      stage.dataset.state = 'running';
      status.textContent = t.running;
      reset.hidden = full.hidden = false;
      sound.hidden = event.data.audio !== true;
      sound.textContent = t.sound;
      sound.setAttribute('aria-pressed', 'false');
    }
  });
  start.addEventListener('click', launch);
  exit.addEventListener('click', () => { stop(t.closed); start.focus(); });
  reset.addEventListener('click', () => send('reset'));
  full.addEventListener('click', async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else if (stage.requestFullscreen) await stage.requestFullscreen(); else status.textContent = t.fullscreen; }
    catch (_) { status.textContent = t.fullscreen; }
  });
  sound.addEventListener('click', () => {
    enabled = !enabled;
    send(enabled ? 'sound-on' : 'sound-off');
    sound.textContent = enabled ? t.mute : t.sound;
    sound.setAttribute('aria-pressed', String(enabled));
  });
  window.addEventListener('pagehide', () => stop(t.closed));
  try {
    const intent = JSON.parse(sessionStorage.getItem(key) || 'null');
    sessionStorage.removeItem(key);
    if (intent?.slug === stage.dataset.gameSlug && Date.now() - intent.at >= 0 && Date.now() - intent.at < 30000) launch();
  } catch (_) {}
})();
