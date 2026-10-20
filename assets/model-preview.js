/* Opt-in only. No network, model decoding, animation or sound before activation. */
(() => {
  'use strict';
  const scriptURL = document.currentScript.src;
  const moduleURL = new URL('vendor/model-viewer/model-viewer.min.js', scriptURL).href;
  let modulePromise;
  const zh = document.documentElement.lang.startsWith('zh');
  const words = zh ? {
    loading: '正在加载模型…', ready: '拖动旋转；双指缩放。也可使用方向与缩放按钮。',
    error: '无法加载交互模型。原图与源文件仍可查看。', idle: '模型仅在点击后加载。',
  } : {
    loading: 'Loading model…', ready: 'Drag to orbit; pinch to zoom. Direction and zoom buttons are also available.',
    error: 'Interactive model unavailable. The image and source file remain available.', idle: 'The model loads only after your click.',
  };
  document.querySelectorAll('[data-model-preview]').forEach(root => {
    const start = root.querySelector('[data-model-start]');
    const stop = root.querySelector('[data-model-stop]');
    const mount = root.querySelector('[data-model-mount]');
    const status = root.querySelector('[role="status"]');
    const controls = root.querySelector('[data-model-controls]');
    let viewer = null, generation = 0, timer = null;
    const clear = () => {
      generation++; clearTimeout(timer);
      if (viewer) { viewer.pause(); viewer.remove(); viewer = null; }
      mount.replaceChildren(); mount.hidden = true; controls.hidden = true;
      start.disabled = false; stop.hidden = true;
    };
    const fail = () => { clear(); status.textContent = words.error; };
    start.addEventListener('click', async () => {
      if (start.disabled) return;
      const token = ++generation;
      start.disabled = true; stop.hidden = false; status.textContent = words.loading;
      timer = setTimeout(() => { if (token === generation) fail(); }, 30000);
      try {
        modulePromise ||= import(moduleURL).catch(error => { modulePromise = null; throw error; });
        const module = await modulePromise;
        module.ModelViewerElement.modelCacheSize = 0; // Do not retain disconnected model assets.
        if (token !== generation) return;
        viewer = document.createElement('model-viewer');
        viewer.setAttribute('camera-controls', '');
        viewer.setAttribute('touch-action', 'pan-y');
        viewer.setAttribute('interaction-prompt', 'none');
        viewer.setAttribute('camera-orbit', '0deg 75deg 105%');
        viewer.setAttribute('camera-target', 'auto auto auto');
        viewer.setAttribute('alt', root.dataset.modelAlt);
        viewer.setAttribute('loading', 'eager');
        viewer.addEventListener('load', () => {
          if (token !== generation) return;
          clearTimeout(timer); controls.hidden = false; status.textContent = words.ready;
        }, {once: true});
        viewer.addEventListener('error', () => { if (token === generation) fail(); }, {once: true});
        mount.hidden = false; mount.append(viewer);
        // Only validated, same-origin, self-contained GLBs enter the generated markup.
        viewer.src = root.dataset.modelSrc;
      } catch (_) { if (token === generation) fail(); }
    });
    stop.addEventListener('click', () => { clear(); status.textContent = words.idle; start.focus(); });
    root.querySelectorAll('[data-model-action]').forEach(button => button.addEventListener('click', () => {
      if (!viewer || controls.hidden) return;
      const action = button.dataset.modelAction;
      if (action === 'reset') {
        viewer.cameraOrbit = '0deg 75deg 105%'; viewer.cameraTarget = 'auto auto auto'; viewer.fieldOfView = 'auto';
      } else if (action === 'in' || action === 'out') {
        const orbit = viewer.getCameraOrbit();
        viewer.cameraOrbit = `${orbit.theta}rad ${orbit.phi}rad ${orbit.radius * (action === 'in' ? 0.85 : 1.18)}m`;
      } else {
        const orbit = viewer.getCameraOrbit();
        const theta = orbit.theta + (action === 'left' ? -0.25 : action === 'right' ? 0.25 : 0);
        const phi = Math.max(0.1, Math.min(Math.PI - 0.1, orbit.phi + (action === 'up' ? -0.2 : action === 'down' ? 0.2 : 0)));
        viewer.cameraOrbit = `${theta}rad ${phi}rad ${orbit.radius}m`;
      }
      viewer.jumpCameraToGoal();
    }));
    document.addEventListener('visibilitychange', () => {
      if (document.hidden && viewer) viewer.pause();
    });
    window.addEventListener('pagehide', clear);
  });
})();
