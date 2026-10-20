(() => {
  "use strict";
  const zh = document.documentElement.lang.toLowerCase().startsWith("zh");
  const labels = zh ? {title: "交互体验", opened: "体验页面已打开。点击其中的开始按钮加载游戏。", closed: "体验已关闭。"} :
    {title: "Interactive demo", opened: "Demo opened. Use its Start button to load the game.", closed: "Demo closed."};
  document.querySelectorAll("[data-playable]").forEach(section => {
    const start = section.querySelector("[data-play-start]");
    const exit = section.querySelector("[data-play-exit]");
    const holder = section.querySelector("[data-play-frame]");
    const status = section.querySelector("[data-play-status]");
    const standalone = section.querySelector("[data-play-link]");
    const actions = section.querySelector(".playable-actions");
    const viewportFit = section.dataset.playCase === "dawnkeep-defense";
    let stopFit = null;
    const fitFrame = frame => {
      const viewport = Math.min(window.innerHeight, window.visualViewport?.height || window.innerHeight);
      // scrollIntoView honors the site's root scroll-padding-top. Reserve that
      // inset as well as the toolbar so the bottom native controls stay visible.
      const inset = Math.max(0, parseFloat(window.getComputedStyle(document.documentElement).scrollPaddingTop) || 0);
      frame.style.height = Math.max(160, Math.floor(viewport - inset - actions.getBoundingClientRect().height - 24)) + "px";
      frame.style.maxHeight = "none";
      frame.style.minHeight = "0";
    };
    const destination = new URL(start.dataset.playUrl, window.location.href);
    if (destination.origin !== window.location.origin) return;
    destination.searchParams.set("lang", zh ? "zh" : "en");
    destination.searchParams.set("v", section.dataset.playRevision || "1");
    standalone.href = destination.href;
    window.addEventListener('message', event => {
      const frame=holder.querySelector('iframe');
      if(!frame || event.source!==frame.contentWindow || event.origin!==destination.origin || event.data?.type!=='showcase:resize')return;
      if(viewportFit){fitFrame(frame);return;}
      const height=event.data.height;
      if(Number.isInteger(height) && height>=160 && height<=10000){const border=frame.offsetHeight-frame.clientHeight;frame.style.height=Math.ceil(height+border)+'px';frame.style.maxHeight='none';}
    });
    start.hidden = false;
    start.addEventListener("click", () => {
      if (holder.querySelector("iframe")) return;
      const frame = document.createElement("iframe");
      frame.src = destination.href;
      frame.title = labels.title;
      frame.allow = "autoplay; fullscreen";
      frame.setAttribute("allowfullscreen", "");
      holder.append(frame);
      start.hidden = true;
      exit.hidden = false;
      status.textContent = labels.opened;
      if (viewportFit) {
        section.dataset.playOpen = "true";
        const fit = () => fitFrame(frame);
        fit();
        window.addEventListener("resize", fit);
        window.visualViewport?.addEventListener("resize", fit);
        const observer = window.ResizeObserver ? new window.ResizeObserver(fit) : null;
        observer?.observe(actions);
        stopFit = () => {
          window.removeEventListener("resize", fit);
          window.visualViewport?.removeEventListener("resize", fit);
          observer?.disconnect();
        };
        actions.scrollIntoView({block: "start", behavior: "instant"});
        frame.focus({preventScroll: true});
      } else frame.focus();
    });
    exit.addEventListener("click", () => {
      stopFit?.();
      stopFit = null;
      delete section.dataset.playOpen;
      holder.replaceChildren();
      exit.hidden = true;
      start.hidden = false;
      status.textContent = labels.closed;
      start.focus();
    });
  });
})();
