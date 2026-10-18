# Real Godot Web demos / Godot 浏览器试玩

These are release exports of the native Sonic Loom and Prism Tide projects already published with the showcase. The canvas runs Godot WebAssembly and GDScript; it is not a video player. Existing videos and source ZIPs remain available unchanged.

这是已公开原生 Sonic Loom 与 Prism Tide 工程的真实 Web release 导出。画布运行 Godot WebAssembly 与 GDScript，不是视频播放器；原视频和源码 ZIP 继续保留。

## Run / 运行

Open either index.html through HTTP(S), not file://. Use Start to download and launch; click or tap the canvas for keyboard focus. The shell supports ?lang=en or ?lang=zh. The original in-game artwork and labels remain English. Phones use a separate native portrait layout with large touch controls and vertical scrolling.

通过 HTTP(S) 打开 index.html，再点击启动；点击画布后可用键盘操作。使用 ?lang=en 或 ?lang=zh 切换操作区语言，原生作品文字保留英文。手机采用独立原生竖版布局，提供大号触控按钮并支持上下滚动。

- Sonic Loom: tap steps, mute voices, play/pause, change tempo; Save/Load persists a pattern locally when browser storage is available. Runtime synthesis produces original PCM samples played by Godot Web Audio.
- Prism Tide: rotate mirrors, open gates and solve three levels. Save/Load adds an explicit local checkpoint; this original puzzle has no audio.
- Reset restores the default pattern/current puzzle. Exit stops the engine. Unsaved edits are discarded. Saves are browser-local and may be unavailable or evicted in private/blocked storage. No login, remote saves, analytics, network game service or permissions for microphone/camera are used.

Sonic Loom 支持编辑步进、声部静音、播放暂停、变速和本地保存读取，音色由原始算法产生 PCM 并经 Godot Web Audio 播放。Prism Tide 有三关镜面与闸门谜题，新增明确的本地存档按钮，原作没有声音。重置恢复初始节奏或当前关卡，退出停止引擎，未保存编辑会丢失。持久化存储被禁用时保存会明确失败；存档可能受到隐私浏览、存储权限或浏览器清理影响，无需登录，不上传存档。

## Hosting and budget / 托管和预算

Godot 4.6.3, Compatibility/WebGL 2, single-threaded. No SharedArrayBuffer, COOP/COEP requirements, service workers or PWA caching. The site must serve .wasm as application/wasm and .pck as application/octet-stream. HTTPS is recommended; localhost is suitable for tests. Existing GitHub Pages hosting is used; no new hosting service is needed.

The shared official WASM runtime is 37,700,666 bytes; it is reused by both demos, while each project pack is under 32 KiB. The explicit asset manifest enforces a 40 MiB raw / 11 MiB gzip-equivalent combined budget. Gzip-equivalent is a local measurement, not proof of production transfer encoding. Loading is user-triggered. No runtime bytes are fetched by merely opening a case page or the unloaded demo shell.

同版本官方引擎共享一份 WASM，两个案例不重复下载引擎。清单约束原始总资源不超过 40 MiB、gzip 等效总量不超过 11 MiB。实际线上 MIME 和压缩编码须在授权部署后验证。仅浏览案例页或未启动的试玩壳不会加载运行时。

## Rebuild and verification

See scripts/godot_web/README.md in the repository for matching official templates, reproducible export commands, browser acceptance tests and known verification limits. runtime/COPYRIGHT.txt and runtime/LICENSE.txt preserve the engine's upstream notices. manifest.json is an explicit path/size/SHA-256 publication allowlist, not a directory crawl.

## Verification limits / 验证边界

The browser evidence covers Chromium desktop and mobile touch emulation, not physical phones, Safari/Firefox, subjective listening or hardware audio latency. Official engine shutdown emits a PagedAllocator diagnostic; the JSON report preserves it. Source and published pack hashes bind the tested native exports. Production MIME and Content-Encoding remain unverified until an authorized deployment.

浏览器证据覆盖 Chromium 桌面与手机触控模拟，不代表实体手机、Safari/Firefox、主观听评或硬件音频延迟已验收。官方引擎退出时会输出 PagedAllocator 诊断，JSON 报告保留该记录。源文件和发布资源包均绑定哈希；生产站点的 MIME 与压缩编码仍待授权部署后核验。

Recorded acceptance / 已记录验收: [verification.json](verification.json). Desktop and touch screenshots: [Sonic desktop](evidence/sonic-loom-desktop-edited.png), [Sonic touch](evidence/sonic-loom-touch-edited.png), [Prism desktop](evidence/prism-tide-desktop-solved.png), [Prism touch](evidence/prism-tide-touch-solved.png); full interaction videos are retained in the linked CI artifact until its recorded expiry. These captures verify operation, not an artistic quality score.

桌面与触控截图已保存在 evidence/；完整交互录屏位于报告所链接的 CI 附件，在所记录的到期时间前可取。画面记录用于验证操作，不代表美术品质评分。

Current portrait and bilingual iframe acceptance: [verification-portrait.json](verification-portrait.json), with 40 real-browser checks, separate per-channel audio measurements and new phone screenshots. The e43fc55 record above remains a historical functional baseline; its older scaled-desktop captures do not verify the new phone layout.

新版竖屏与中英内嵌验收见 [verification-portrait.json](verification-portrait.json)，包含40项真实浏览器检查、分声道音频测量及新手机截图。上方 e43fc55 记录保留为历史功能基线，旧版整屏缩小的截图不代表新手机布局验收。

The phone layouts are separately arranged native canvases, with readable labels and large native touch targets. Sonic shows one selected voice with all16 steps; Prism’s portrait board scrolls vertically. Alternative browser controls stay collapsed until requested.

手机采用独立原生竖版布局，提供可读文字和大号原生触区。Sonic 同时显示所选声部的16个步进；Prism 竖版棋盘可上下滚动，备用浏览器控件默认折叠。

Web-only audio uses -6 dB Master headroom. The seven-player PCM triangle bound is 0.750163 per output channel, including Godot’s 16-bit decoder scale. Browser tests meter both destination channels after speaker-layout conversion using a unity-gain tap; dense patterns and every solo voice are checked. The older single analyser folded Godot’s six-channel container to mono, boosting identical L/R by sqrt(2); its 1.01969 reading did not itself establish stereo output clipping. See the [Web Audio down-mixing rules](https://www.w3.org/TR/webaudio/#down-mix). No professional loudness, hardware true-peak or subjective listening acceptance is claimed.

Web 版 Master 音量保留 -6 dB 混音余量。计入 Godot 的16位解码比例后，七个播放器叠加的每输出声道保守 PCM 上界为0.750163。浏览器通过单位增益采样支路，在扬声器声道转换后分别测量两个声道，并覆盖密集节奏和每个独奏声部。旧版单 analyser 将 Godot 的六声道容器下混为单声道，相同左右声道被放大 sqrt(2) 倍；旧1.01969读数本身不能证明立体声输出削波。不据此宣称完成专业响度、硬件真峰值或主观听评。

## This Web round / 本轮 Web 工作

On 2026-10-12, the requested and accepted configuration for this Web adaptation/review round was gpt-6-astra / ultra. Backend model routing was not independently verified. The review covers both examples’ desktop and phone screenshots and 40 real-browser checks; it is not an artistic-quality score. This records the new Web work, not the original creation model, whose historical identity remains unknown. Subjective listening, physical phones, Safari and Firefox were not accepted in this round.

2026-10-12 本轮 Web 适配与复审请求并接受的配置为 gpt-6-astra / ultra，未独立核验后台模型路由。复审覆盖两例的桌面与手机截图及40项真实浏览器检查，不是美术品质评分。该记录仅属于新增 Web 工作，原始创作模型的历史身份仍为未知。本轮未完成主观听评、实体手机、Safari 或 Firefox 验收。

The browser analyser reads periodic 2048-sample windows. Busy rendering can leave gaps between them, so its pass means nonzero audio and no over-range samples in the captured windows, not continuous peak coverage. The separate 0.750162 per-channel PCM bound covers arbitrary alignment of the seven players.

浏览器 analyser 定期读取2048样本窗口，渲染繁忙时窗口之间可能有空档。因此浏览器通过仅代表采到非零音频且所采窗口内未超幅，不代表连续峰值覆盖。七个播放器任意相位叠加的余量依据是独立的每声道0.750162保守 PCM 上界。
