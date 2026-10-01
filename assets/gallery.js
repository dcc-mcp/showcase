(() => {
"use strict";
// Fixed IDs from the official site's former ShowcaseGallery component.
// Keep existing shared links useful without accepting arbitrary redirect targets.
const legacyTargets = {
  "#blender-designer-crate": "cases/crate-lookdev/",
  "#blender-lookdev": "https://dcc-mcp.github.io/examples#blender-lookdev",
  "#blender-stylized-red-swings": "https://dcc-mcp.github.io/examples#blender-stylized-red-swings",
  "#marmoset-lookdev": "https://dcc-mcp.github.io/examples#marmoset-lookdev",
  "#wwise-audio": "https://dcc-mcp.github.io/examples#wwise-audio",
  "#houdini-portal": "https://dcc-mcp.github.io/examples#houdini-portal",
  "#openscad-parametric-pipeline": "https://dcc-mcp.github.io/examples#openscad-parametric-pipeline",
  "#freecad-game-ready-pipeline": "https://dcc-mcp.github.io/examples#freecad-game-ready-pipeline",
  "#speedtree-to-unreal-engine": "https://dcc-mcp.github.io/examples#speedtree-to-unreal-engine",
  "#cinema4d-typed-scene": "https://dcc-mcp.github.io/examples#cinema4d-typed-scene",
  "#comfyui-typed-workflow": "https://dcc-mcp.github.io/examples#comfyui-typed-workflow",
  "#illustrator-typed-vector-workflow": "https://dcc-mcp.github.io/examples#illustrator-typed-vector-workflow",
  "#sketchup-typed-modeling": "https://dcc-mcp.github.io/examples#sketchup-typed-modeling",
  "#touchdesigner-typed-operator-workflow": "https://dcc-mcp.github.io/examples#touchdesigner-typed-operator-workflow",
  "#cache-inspection-workflow": "https://dcc-mcp.github.io/examples#cache-inspection-workflow",
  "#shogun-typed-mocap-workflow": "https://dcc-mcp.github.io/examples#shogun-typed-mocap-workflow",
  "#tiled-typed-map-workflow": "https://dcc-mcp.github.io/examples#tiled-typed-map-workflow",
  "#material-maker-typed-material-workflow": "https://dcc-mcp.github.io/examples#material-maker-typed-material-workflow",
  "#krita-typed-paint-workflow": "https://dcc-mcp.github.io/examples#krita-typed-paint-workflow",
  "#gimp-typed-image-workflow": "https://dcc-mcp.github.io/examples#gimp-typed-image-workflow",
  "#katana-typed-lookdev-workflow": "https://dcc-mcp.github.io/examples#katana-typed-lookdev-workflow",
  "#premiere-typed-edit-workflow": "https://dcc-mcp.github.io/examples#premiere-typed-edit-workflow",
  "#hunyuan3d": "https://dcc-mcp.github.io/examples#hunyuan3d",
  "#geospatial-city": "https://dcc-mcp.github.io/examples#geospatial-city",
  "#maya-architecture": "https://dcc-mcp.github.io/examples#maya-architecture",
  "#kenney-assets": "https://dcc-mcp.github.io/examples#kenney-assets",
  "#zbrush-fantasy-dragon": "https://dcc-mcp.github.io/examples#zbrush-fantasy-dragon",
  "#zbrush-maya-roundtrip": "https://dcc-mcp.github.io/examples#zbrush-maya-roundtrip",
  "#office-powerpoint-deck": "https://dcc-mcp.github.io/examples#office-powerpoint-deck"
};
const legacyTarget = legacyTargets[window.location.hash];
if (legacyTarget) {
window.location.replace(new URL(legacyTarget, window.location.href).href);
return;
}
const controls = document.querySelector("#gallery-controls");
if (!controls) return;
const cards = Array.from(document.querySelectorAll(".case-card"));
const search = document.querySelector("#search");
const count = document.querySelector("#result-count");
const empty = document.querySelector("#empty-state");
const wall = document.querySelector("#work-wall");
const state = {software:"all", capability:"all", query:""};
const params = new URLSearchParams(window.location.search);
const validFilter = (type,value) => Array.from(document.querySelectorAll('[data-filter="' + type + '"] button')).some(button => button.dataset.value === value);
["software","capability"].forEach(type => {
const value = params.get(type);
if (value && validFilter(type,value)) state[type] = value;
});
state.query = params.get("q") || "";
search.value = state.query;
const apply = () => {
const query = state.query.trim().toLocaleLowerCase();
let visible = 0;
cards.forEach(card => {
const software = JSON.parse(card.dataset.software);
const capabilities = JSON.parse(card.dataset.capabilities);
const match = (state.software === "all" || software.includes(state.software)) &&
(state.capability === "all" || capabilities.includes(state.capability)) &&
(!query || card.dataset.search.toLocaleLowerCase().includes(query));
card.hidden = !match;
if (match) visible += 1;
});
document.querySelectorAll("[data-filter]").forEach(group => {
group.querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed",String(state[group.dataset.filter] === button.dataset.value)));
});
wall.classList.toggle("has-many",visible >= 3);
empty.hidden = visible !== 0;
count.textContent = visible === cards.length ? "显示全部 " + visible + " 个案例" : "显示 " + visible + " / " + cards.length + " 个案例";
const next = new URLSearchParams();
if (state.software !== "all") next.set("software",state.software);
if (state.capability !== "all") next.set("capability",state.capability);
if (state.query.trim()) next.set("q",state.query.trim());
const queryString = next.toString();
window.history.replaceState(null,"",window.location.pathname + (queryString ? "?" + queryString : "") + window.location.hash);
};
document.querySelectorAll("[data-filter]").forEach(group => {
group.addEventListener("click",event => {
const button = event.target.closest("button");
if (!button || !group.contains(button)) return;
state[group.dataset.filter] = button.dataset.value; apply();
});
});
search.addEventListener("input",() => {state.query = search.value; apply();});
const reset = () => {state.software = state.capability = "all"; state.query = search.value = ""; apply();};
document.querySelector("#reset-filters").addEventListener("click",reset);
document.querySelector("#empty-reset").addEventListener("click",reset);
controls.hidden = false; apply();
})();
