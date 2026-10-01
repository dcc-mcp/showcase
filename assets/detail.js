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
