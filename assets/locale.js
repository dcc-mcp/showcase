(() => {
  "use strict";
  // Ordinary anchors are the no-JavaScript fallback. No automatic redirects or
  // storage preferences: an explicitly opened language URL always wins.
  document.querySelectorAll("[data-locale-link]").forEach(link => {
    link.addEventListener("click", () => {
      const target = new URL(link.getAttribute("href"), window.location.href);
      target.search = window.location.search;
      target.hash = window.location.hash;
      link.href = target.href;
    });
  });
})();
