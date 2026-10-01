(() => {
  "use strict";
  const params = new URLSearchParams(window.location.search);
  let theme = params.get("theme") === "light" ? "light" : "dark";
  const themeGroups = Array.from(document.querySelectorAll("[data-brand-themes]"));
  const images = Array.from(document.querySelectorAll("[data-brand-image]"));
  const knownParams = ["family", "software", "q", "theme"];
  const safeParams = () => {
    const output = new URLSearchParams();
    knownParams.forEach(key => { if (params.get(key)) output.set(key, params.get(key)); });
    return output;
  };
  const navigation = () => {
    const query = safeParams().toString();
    document.querySelectorAll(".brand-detail-link, [data-brand-back]").forEach(link => {
      const original = link.dataset.originalHref || link.getAttribute("href");
      link.dataset.originalHref = original;
      const url = new URL(original, window.location.href);
      url.search = query;
      link.href = url.href;
    });
  };
  const applyTheme = () => {
    images.forEach(img => {
      const source = theme === "light" ? img.dataset.lightSrc : img.dataset.darkSrc;
      const alt = theme === "light" ? img.dataset.lightAlt : img.dataset.darkAlt;
      const dimensions = theme === "light" ? img.dataset.lightDimensions : img.dataset.darkDimensions;
      // Sources come from escaped, validated catalog data. No recoloring.
      if (img.getAttribute("src") !== source) img.setAttribute("src", source);
      img.alt = alt;
      ["width", "height"].forEach(attribute => {
        const match = dimensions.match(new RegExp(attribute + '="(\\d+)"'));
        if (match) img.setAttribute(attribute, match[1]);
        else img.removeAttribute(attribute);
      });
      const stage = img.closest(".brand-stage");
      if (stage) stage.dataset.background = theme;
    });
    themeGroups.forEach(group => {
      group.querySelectorAll("[data-brand-theme]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.brandTheme === theme)));
    });
    if (theme === "light") params.set("theme", "light");
    else params.delete("theme");
    navigation();
  };
  const saveURL = () => {
    const query = safeParams().toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
  };
  themeGroups.forEach(group => {
    group.hidden = images.length === 0;
    group.addEventListener("click", event => {
      const button = event.target.closest("[data-brand-theme]");
      if (!button || !group.contains(button)) return;
      theme = button.dataset.brandTheme;
      applyTheme();
      saveURL();
    });
  });
  applyTheme();
  const controls = document.querySelector("#brand-controls");
  if (controls) {
    const cards = Array.from(document.querySelectorAll("[data-brand-card]"));
    const search = document.querySelector("#brand-search");
    const family = document.querySelector("#brand-family");
    const software = document.querySelector("#brand-software");
    const count = document.querySelector("#brand-count");
    const empty = document.querySelector("#brand-empty");
    const selectValue = (select, raw) => Array.from(select.options).some(option => option.value === raw) ? raw : "all";
    family.value = selectValue(family, params.get("family"));
    software.value = selectValue(software, params.get("software"));
    search.value = (params.get("q") || "").slice(0, 200);
    const apply = () => {
      const query = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      cards.forEach(card => {
        const matches = (family.value === "all" || card.dataset.family === family.value) &&
          (software.value === "all" || JSON.parse(card.dataset.software).includes(software.value)) &&
          (!query || card.dataset.search.toLocaleLowerCase().includes(query));
        card.hidden = !matches;
        if (matches) visible += 1;
      });
      count.textContent = visible === cards.length ? "全部 " + visible + " 个品牌条目" : "显示 " + visible + " / " + cards.length + " 个品牌条目";
      empty.hidden = visible !== 0;
      [["family", family.value], ["software", software.value], ["q", search.value.trim()]].forEach(([key, value]) => {
        if (value && value !== "all") params.set(key, value);
        else params.delete(key);
      });
      navigation();
      saveURL();
    };
    const reset = () => {
      family.value = software.value = "all";
      search.value = "";
      apply();
    };
    family.addEventListener("change", apply);
    software.addEventListener("change", apply);
    search.addEventListener("input", apply);
    document.querySelector("#brand-reset").addEventListener("click", reset);
    const emptyReset = document.querySelector("#brand-empty-reset");
    emptyReset.hidden = false;
    emptyReset.addEventListener("click", reset);
    controls.hidden = false;
    apply();
  }
  const copy = document.querySelector("[data-brand-copy]");
  if (copy && navigator.clipboard && window.isSecureContext) {
    copy.hidden = false;
    copy.addEventListener("click", async () => {
      const status = document.querySelector(".brand-copy-status");
      try {
        await navigator.clipboard.writeText(document.querySelector("#brand-prompt").textContent);
        status.textContent = "提示词已复制。";
      } catch (_) {
        status.textContent = "复制失败，请选中提示词文本复制。";
      }
    });
  }
})();
