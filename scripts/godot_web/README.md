# Reproduce the playable exports

## Inputs and scope

The source baseline is main commit 8ed8789, where Sonic Loom (#25) and Prism Tide (#26) are already merged and publicly downloadable. Original ZIP SHA-256 values and all adapted source hashes are recorded in play/export-provenance.json. Parcel Courier and cancelled Orbital work are excluded.

projects/ contains extracted native sources with a small web.gd adapter. The original drawing, puzzle logic and PCM synthesis remain native GDScript. Web additions provide local checkpoints, accessible touch buttons and a read-only state report used for acceptance checks. The only native Prism logic correction uses the incoming pointer event's position, supporting emulated touch reliably. No browser test calls the command bridge directly; tests use pointer, keyboard and touch input.

## Export

Use the official standard Linux x86_64 Godot 4.6.3 editor. The exporter pins the executable SHA-256 (f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3), independently matched to the binary extracted from the official Linux archive. Its archive SHA-256 is d0bc2113065e481c9c2c2b2c37daa4e8be3fe9e27f0ab9ab0b6096e9a37907f3, also verified against the upstream SHA512-SUMS.txt. Other platforms are not silently accepted by this reproduction script. Download the exact same version of the export templates from https://godotengine.org/download/archive/4.6.3-stable/ and extract templates/web_nothreads_release.zip plus templates/web_nothreads_debug.zip. Alternatively the helper downloads only these members with HTTP ranges, verifies ZIP CRC and pinned SHA-256, and never executes downloaded code:

    python scripts/godot_web/fetch_templates.py --output /tmp/godot-web-templates
    python scripts/godot_web/export.py --godot godot --template /tmp/godot-web-templates/web_nothreads_release.zip
    python scripts/godot_web/write_manifest.py
    python scripts/godot_web/verify_export.py
    python scripts/test_playable.py
    python scripts/build_site.py

The export runs in a temporary isolated XDG data/config/cache directory. It requires the official editor version string and pinned official template hashes. Runtime JS, WASM and audio worklets are copied byte-for-byte from the official release template; source PCKs are exported by Godot. Both examples share the runtime. Engine binaries are not checked into Git: each Pages/browser build materializes the four hash-pinned official runtime files, then serves those bytes from the same Pages origin. There is no third-party runtime fetch. Run python scripts/godot_web/materialize_runtime.py before building a fresh checkout.

The built-in project uses procedural drawing rather than imported compressed textures, so mobile texture compression is disabled. This avoids Godot's ETC2 import prerequisite without changing the Compatibility renderer or phone support.

## Browser acceptance

    python -m pip install --require-hashes --only-binary=:all: -r requirements/browser-preview.lock
    python -m playwright install --with-deps chromium
    python scripts/godot_web/browser_test.py --site _site --output /tmp/godot-web-evidence

The dedicated Godot Web acceptance workflow runs against the exact PR head. It tests real WASM startup without COOP/COEP, actual native canvas input, audible WebAudio graph nonzero samples after a user gesture, keyboard play/pause, touch controls, all three solved puzzle levels, local save/load/reset and persistence after engine exit/restart, iframe keyboard focus/unload/reopen, existing video preservation, delayed asset loading and cancellation during loading, visible recovery on a failed WASM request, and honest save failure when IndexedDB is denied. Evidence includes screenshots, interaction videos and JSON checks. It does not disable autoplay policy. Audio is measured from both actual destination-layout channels with separate analysers; this is technical signal verification, not subjective listening.

The cloud command sandbox used for preparation blocks Chromium's Unix process socket even after escalation; its separate cloud browser also cannot reach the isolated localhost server. Therefore local export success is not reported as browser acceptance. The PR workflow is the intended runnable browser verification route. Physical phone testing, Safari/Firefox, subjective sound quality, hardware audio latency and production Pages MIME/compression are separate, explicitly unverified until performed. No new hosting service or deployment is created.

## Hosting

The explicit play/manifest.json controls every published path, byte count and hash. No directory crawl. The build validates selected case ownership, same-origin paths, approved extensions, single-thread renderer and bilingual shell metadata. The gallery defers iframe creation; the iframe defers runtime loading until Start. Closing removes the iframe, releasing the runtime and audio graph.

No SharedArrayBuffer, PWA or service worker. No simulated security headers. Expected MIME types are application/wasm and application/octet-stream. GitHub Pages gzip behavior must be checked after an authorized deployment, not inferred from a local estimate. Resource budget: 40 MiB raw / 11 MiB gzip equivalent for all playable files together, under 32 KiB per native PCK, one shared engine. Test loading timings are localhost software-renderer measurements and are not phone performance claims.

## Diagnostic boundary

Chromium software WebGL can warn about GPU ReadPixels stalls. The official single-threaded engine also emits a PagedAllocator / WorkerThreadPool Group diagnostic when requestQuit tears down the runtime. These messages are retained in the JSON evidence; the run is not console-warning-free. Save persistence and clean iframe removal are tested independently. PCK builds are regenerated by Godot and are not claimed to be byte-reproducible; every published pack has an explicit SHA-256 and source provenance.

## Portrait and output headroom

The Web adapters have dedicated phone layouts instead of shrinking the desktop canvas: Sonic uses a voice selector and 4×4 step grid; Prism rotates its optical board into 6×10. Native labels have a 32-unit minimum at 720 units wide, and native touch targets are at least 88 units. Browser tests measure the resulting CSS sizes and exercise vertical finger scrolling, native taps and all three rotated puzzle paths. Completed taps are forwarded to native canvas mouse input so the official engine does not trap page scrolling; drags never call the game command bridge.

The official Web sample bus routes gain → solo → mute directly to AudioDestination, without a final limiter. The Web adapter uses -6 dB Master gain and explicit one-voice polyphony per player. Its --web-audio-test derives a per-channel conservative triangle bound from all seven quantized WAVs, using Godot’s actual /32767 decoder scale: 1.4967704910 dry and 0.7501622618 after gain. It also checks the stereo mix target. Browser regressions fill all 64 pads through real controls, meter each voice, and meter the full mix at 60 and 160 BPM.

The current meter inserts a unity-gain tap with explicit destination.channelCount and the destination’s speaker interpretation, then splits into one mono analyser per output channel. Its separate zero-gain analysis sink keeps analysers pulled without adding audio to the unchanged unity main path. Earlier evidence used one analyser on Godot’s six-channel container: its automatic 5.1-to-mono down-mix boosts identical L/R by sqrt(2), so the old 1.01969 reading alone did not establish stereo clipping. The dense-pattern case still justifies headroom. Historical readings remain historical and are not relabelled as per-channel measurements. See [Web Audio down-mixing](https://www.w3.org/TR/webaudio/#down-mix), [analyser time-domain conversion](https://www.w3.org/TR/webaudio/#time-domain-down-mixing) and [Godot WAV decoding](https://github.com/godotengine/godot/blob/4.6.3-stable/scene/resources/audio_stream_wav.cpp#L191-L196). The report records actual channel count, each channel peak and meter topology. These are sampled digital peaks, not hardware true-peak, loudness or subjective sound-quality certification.

    godot --headless --path scripts/godot_web/projects/sonic-loom -- --web-audio-test

Re-export one adapter without changing the other already-verified PCK:

    python scripts/godot_web/export.py --case sonic-loom --template /tmp/godot-web-templates/web_nothreads_release.zip

The browser meter uses periodic 2048-sample windows, and rendering stalls can leave gaps. Its headroom checks mean only that captured windows contain nonzero audio and no over-range samples. They do not establish continuous peak coverage. The separate native PCM triangle bound supplies the all-alignment guarantee. Increasing windows and measuring temporal coverage is a possible future test enhancement, not an acceptance claim of this PR.

## Live responsive reflow

The shell separates the canvas logical dimensions from its displayed contain-fit
rectangle. Below 720 CSS pixels of actual iframe width, or with a coarse touch pointer,
it selects the original portrait adapter; a wider fine-pointer view selects
the desktop composition. Touch orientation changes retain the legible phone
controls and vertical pan, rather than shrinking the desktop matrix. Resize,
orientation changes and fullscreen switch the native content scale in-place,
preserving pattern, tempo, puzzle state and the audio gate. Portrait dedicated
stages grow with their content and legacy case embeds report their natural
height, so the outer page owns scrolling. Accessible HTML controls remain a
44-pixel alternative, including narrow or short full-screen viewports.

`--web-layout-test` checks both native adapters round-trip without resetting state.
`responsive_games_browser.py` checks actual WASM at 320–2048 CSS-pixel widths,
portrait/landscape, CSS zoom and equivalent layout viewport changes, fullscreen,
state preservation and the older case-page embed. This is not physical-device,
OS browser-zoom, Safari or Firefox acceptance. The official Engine `preloadFile`
and `start` methods fetch a hash-versioned PCK into its stable virtual filename;
shell assets and generated page JS/CSS also use content-bound cache versions.
