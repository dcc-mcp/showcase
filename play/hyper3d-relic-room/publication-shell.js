/* Same-origin Showcase integration. Game commands and game assets are unchanged. */
(function (root) {
  'use strict';
  function attach(config, environment) {
    const env = environment || {
      window: window, parent: parent, origin: location.origin,
      reload: () => location.reload(),
      listen: callback => window.addEventListener('message', callback),
    };
    const embedded = env.parent !== env.window;
    const notify = data => { if (embedded) env.parent.postMessage(data, env.origin); };
    const originalPrint = config.onPrint;
    let ready = false;
    config.onPrint = function (...args) {
      if (originalPrint) originalPrint(...args); else console.log(...args);
      if (args.join(' ').startsWith('RELIC_FRAME_READY ')) {
        ready = true;
        // SFX use the native on/off control; no second unsynchronized parent mute.
        notify({type: 'showcase:state', state: 'running', audio: false});
      }
    };
    env.listen(event => {
      if (!embedded || event.source !== env.parent || event.origin !== env.origin) return;
      // A user-requested outer reset reloads the whole real engine. No state is
      // injected into the native game, and stale audio/resources are discarded.
      if (ready && event.data?.type === 'showcase:reset') env.reload();
    });
    return {failed() { notify({type: 'showcase:state', state: 'error', audio: false}); }};
  }
  root.RelicCourierPublication = {attach};
  if (typeof module !== 'undefined') module.exports = {attach};
}(typeof window === 'undefined' ? globalThis : window));
