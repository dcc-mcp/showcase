# Original minigames: candidates awaiting acceptance

Signal Garden is a new, original rotating-network puzzle with three authored gardens, native procedural art, original PCM interaction tones, and native English/Chinese layouts. It is separate from Sonic Loom's sequencer, Prism Tide's optical puzzle, and previous courier games.

This directory is a production recipe, not a claim of completed quality acceptance. The candidate workflow creates the actual native scene through discovered DCC-MCP tools, restarts Godot, reopens the saved scene, runs native logic assertions, makes an official single-thread Compatibility Web export, and exercises it through real browser mouse, keyboard and emulated touch. All outputs and complete interaction recordings remain CI artifacts until reviewed. No collection entry or playable publication manifest is changed here.

The first local session connected the native plugin but did not complete gateway readiness. A second bounded session stopped at its 256 MiB process-tree limit (279.3 MiB observed). Neither is recorded as an authoring pass. CI does not share the production renderer's local resource budget.

Original game source, generated tones and procedural art: copyright 2026 dcc-mcp contributors, all rights reserved; this candidate does not grant a new license for those assets. Garden Subset is a renamed subset of Noto Sans CJK SC under SIL OFL; complete source license is FONT-LICENSE.txt. Godot's existing engine notices remain necessary when publishing the shared runtime. No externally sourced game artwork, recordings or level designs are included.

The research record is research.json. Pocket Pulse and Lunar Skipper remain planned; this candidate only creates Signal Garden. Do not advertise the other games as implemented.

Verification limits remain explicit: browser viewport touch simulation is not physical-phone acceptance; sampled audio is not subjective listening; CI staging is not a live public deployment. A green workflow still requires pixel/motion review and parent approval before adding a public case and manifest.

The downloadable CI candidate includes the complete `minigame-site/play` tree, shared runtime, shell, engine/font notices and a `README.txt` with local HTTP serving instructions. Keep that tree intact; opening only `signal-garden/index.html` without its sibling dependencies does not start the game. The native source bundle also includes the font license. The package validator rejects missing runtime, shell or notice files and mismatched PCK bytes. Browser acceptance separately checks both the bottom-row Resume control and the pause overlay's Continue control with actual mouse/emulated-touch input.

## Artifact-only entry and original-speed review

The candidate workflow now prepares a bilingual review desk at `minigame-site/index.html` and `minigame-site/zh/index.html`, served from the same local HTTP root. It links to the actual exported game, a curated native-source ZIP with notices, complete original-speed audiovisual recordings, clearly labelled 3× overviews and decoded original-speed PCM listening WAVs. No speed, pitch, gain or sample-rate adjustment is applied to the listening files. These files make a listening review possible; generating or playing them does not mark subjective listening as passed.

The generator binds native/export/browser/PCK/media bytes, fails on incomplete acceptance, fully decodes the original recordings and writes a bounded evidence record with exact commit, CI run, actual host versions and explicit unverified stages. Raw MCP receipts, editor logs and production host paths stay outside the desk. Artifacts expire after 14 days and are not permanent public resources. The real Chromium review-desk test covers EN/ZH × desktop/320px emulated touch, language/Back navigation, original-speed video/audio progression through real key gestures, source ZIP download hashes and launch/input in the actual exported game.

This preparatory change leaves `collection.json` and `play/manifest.json` unchanged. The public-game contract separately allows explicit `nativeTextLanguage: "en-zh"` so a future reviewed entry can state native bilingual support truthfully; existing `"en"` entries retain their original disclosure. Final visual/motion approval, subjective listening, physical-phone and Safari/Firefox acceptance remain unverified. No merge or deployment follows from this Draft.

MediaRecorder WebM captures can omit finite duration/cue metadata. The review desk uses a lossless stream-copy WebM remux with finite duration, while retaining each raw capture in `minigame-evidence`. Every encoded audio/video packet hash and order, PTS/DTS and every originally present packet duration must match by stream type; no re-encoding or retiming is permitted. Missing video packet-duration metadata may be populated. The bounded record retains both source and review-file hashes. Chromium must observe finite matching durations and exercise actual keyboard seek/return while paused, not just time progression. Final portal screenshots are captured only after real playback, pause and seek recovery.

The review desk's media host must support HTTP byte ranges. The acceptance server reuses the gallery's tested `QuietHandler` and verifies exact 206 responses and the browser's seekable range before keyboard seek/return. Plain `python -m http.server` can serve the game, but does not implement byte ranges and is not the certified media-seeking setup. To review a downloaded artifact from this repository checkout, replace `/path/to/minigame-site` below with the extracted site directory:

```sh
python -c 'import sys; sys.path.insert(0, "scripts"); from browser_preview import QuietHandler; from functools import partial; from http.server import ThreadingHTTPServer; ThreadingHTTPServer(("127.0.0.1", 8765), partial(QuietHandler, directory="/path/to/minigame-site")).serve_forever()'
```

Open `http://127.0.0.1:8765/` in the review browser. This is local review only, not deployment.
