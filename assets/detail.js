(() => {
"use strict";
const button = document.querySelector("#copy-prompt");
const prompt = document.querySelector("#reusable-prompt");
const status = document.querySelector("#copy-status");
if (!button || !prompt || !status) return;
button.hidden = false;
button.addEventListener("click",async () => {
try {await navigator.clipboard.writeText(prompt.textContent); status.textContent = "提示词已复制。";}
catch (_) {
const range = document.createRange(); range.selectNodeContents(prompt);
const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
status.textContent = "已选中提示词，请使用复制快捷键。";
}
});
})();

(() => {
"use strict";
document.querySelectorAll(".audio-player").forEach(player => {
const audio = player.querySelector("audio");
if (!audio) return;
const buttons = Array.from(player.querySelectorAll("[data-audio-seek]"));
const ready = () => audio.readyState >= 1 && Number.isFinite(audio.duration) && audio.duration > 0 && !audio.error;
const update = () => buttons.forEach(button => { button.disabled = !ready(); });
for (const event of ["loadedmetadata", "durationchange", "emptied", "error"]) audio.addEventListener(event, update);
buttons.forEach(button => button.addEventListener("click", () => {
const delta = Number(button.dataset.audioSeek);
if (button.disabled || !ready() || !Number.isFinite(delta)) return;
const current = Number.isFinite(audio.currentTime) ? audio.currentTime : 0;
// User activation changes position only; never call play() or pause().
audio.currentTime = Math.max(0, Math.min(audio.duration, current + delta));
}));
update();
});
})();
