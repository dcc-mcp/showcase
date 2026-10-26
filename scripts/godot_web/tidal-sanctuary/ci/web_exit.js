/* Task-owned Web save/return UI using Godot's public Engine callbacks only. */
(function (root) {
  function attach(config, requestQuit, ui, audio = null) {
    let language = 'en', requested = false, finished = false, hadError = false;
    let trusted = false, finalSave = null, timer = null;
    const emit = (name, value) => console.log(name + ' ' + JSON.stringify(value));
    const words = () => language === 'zh' ? {
      button: '保存 · 返回', saving: '保存...', saved: '已保存，可返回',
      failed: '保存: Save failed', resume: '返回'
    } : {button: 'Save & return', saving: 'Saving...', saved: 'Saved. Safe to leave.',
      failed: 'Save failed. Progress may be lost.', resume: 'Return to island'};
    function fail() {
      hadError = true;
      ui.show(words().failed, false);
    }
    config.onPrint = function (...args) {
      const line = args.join(' ');
      console.log(...args);
      try {
        if (line.startsWith('TIDAL_FRAME_READY ')) ui.ready(words().button);
        if (line.startsWith('TIDAL_SAVE ')) {
          const save = JSON.parse(line.slice('TIDAL_SAVE '.length));
          language = save.language === 'zh' ? 'zh' : 'en';
          ui.label(words().button);
          if (requested && save.reason === 'exit') finalSave = save;
        }
      } catch (_) { fail(); }
    };
    config.onPrintError = function (...args) {
      console.error(...args);
      hadError = true;
      if (requested) fail();
    };
    config.onExit = async function (code) {
      let audioClosed = null;
      if (audio) {
        try {
          const closed = await audio.close();
          const state = JSON.parse(audio.getState());
          audioClosed = closed === true && state.context_state === 'closed' &&
            state.music_playing === false && state.cue_playing === false;
          if (!audioClosed) hadError = true;
        } catch (_) { audioClosed = false; hadError = true; }
      }
      clearTimeout(timer);
      const ok = requested && trusted && code === 0 && !hadError &&
        finalSave !== null && finalSave.persistent === true;
      finished = ok;
      ui.show(ok ? words().saved : words().failed, ok, words().resume);
      emit('TIDAL_WEB_EXIT', {schema: 1, code, requested, trusted, ok,
        save_after_request: finalSave !== null, saved: finalSave, audio_closed: audioClosed});
    };
    ui.click(function (event) {
      if (requested || finished) return;
      requested = true;
      trusted = event.isTrusted === true;
      ui.show(words().saving, false);
      emit('TIDAL_WEB_EXIT_REQUEST', {schema: 1, source: 'save_return_button', trusted, language});
      // Public Godot requestQuit -> normal scene quit -> final asynchronous FS
      // synchronization -> onExit. Never write or synthesize browser storage.
      timer = setTimeout(fail, 120000);
      requestQuit();
    });
    return {isFinished: () => finished};
  }
  function browserUI() {
    const style = document.createElement('style');
    style.textContent = '@font-face{font-family:Tidal;src:url(sanctuary-font.otf)}#tidal-save-return,#tidal-exit-panel{font-family:Tidal,sans-serif;color:#fff1d2}#tidal-save-return{position:fixed;left:16px;bottom:32px;width:148px;height:50px;border:1px solid #cdb887;border-radius:12px;background:#0e2b30;z-index:5;font-size:14px}#tidal-exit-panel{position:fixed;inset:0;z-index:8;background:#102c30;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:24px;text-align:center;padding:24px}#tidal-exit-panel[hidden],#tidal-save-return[hidden]{display:none}#tidal-exit-resume{font:inherit;color:inherit;background:#24474a;border:1px solid #cdb887;border-radius:10px;padding:14px 24px}';
    document.head.append(style);
    const button = document.createElement('button');
    button.id = 'tidal-save-return'; button.hidden = true; button.type = 'button';
    const panel = document.createElement('section'); panel.id = 'tidal-exit-panel'; panel.hidden = true;
    const message = document.createElement('p'); message.id = 'tidal-exit-message'; message.setAttribute('role', 'status');
    const resume = document.createElement('button'); resume.id = 'tidal-exit-resume'; resume.hidden = true;
    resume.addEventListener('click', () => location.reload());
    panel.append(message, resume); document.body.append(button, panel);
    return {
      ready: text => { button.textContent = text; button.hidden = false; },
      label: text => { button.textContent = text; },
      click: callback => button.addEventListener('click', callback),
      show: (text, ok, label) => {
        button.disabled = true; panel.hidden = false; message.textContent = text;
        panel.dataset.saved = String(ok); resume.hidden = !ok;
        if (label) resume.textContent = label;
      }
    };
  }
  root.TidalSaveExit = {attach: (config, requestQuit) => attach(config, requestQuit, browserUI(), root.TidalWebAudio)};
  if (typeof module !== 'undefined') module.exports = {attach};
}(typeof window === 'undefined' ? globalThis : window));
