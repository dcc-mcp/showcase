(() => {
"use strict";
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
