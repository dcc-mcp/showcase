# Tidal Sanctuary CI capture

Install this directory as `scripts/godot_web/tidal-sanctuary/ci/` and the separately authored game as `scripts/godot_web/tidal-sanctuary/game/`. The companion workflow is `.github/workflows/tidal-sanctuary-preview.yml`.

The workflow has read-only repository permissions, no saved checkout credentials, no deploy step, and no upload except the explicit Actions artifact. Every generated project, save, editor session, export and capture goes into new directories under `RUNNER_TEMP`. The original checkout is never opened in Godot. A final tracked-file diff checks for mutation.

## Evidence, kept distinct

- `authoring.json`, `mcp-raw.json`, `mcp-tool-schemas.json`: actual discovered typed MCP calls, returned responses, script creation/validation, Node3D scene creation, script attachment, save, editor process restart, reopen, scene-tree readback and unchanged saved scene hash. The original source is transferred through the typed script API. The output scene is created by Godot. This does not claim every generated mesh was individually authored through a tool.
- `native-validation.json`: an actual headless scene audit; W/E/R sent to the real native window with X11/XTest; actual player displacement and lamp activation read from the game's own save file. No save or game properties are injected. Failures stay failures.
- `native-input-before.png`, `native-input-after.png`: real X11 screenshots of the independent physical-input smoke.
- `scripted-traversal-18s.mp4`: continuous 24 fps X11 capture of the actual native game running `--demo`. Explicitly scripted traversal, not human gameplay, manual-input proof, or an audio demonstration. H.264 is fully decoded after capture.
- `scripted-traversal-frames/tidal-01.png` through `tidal-05.png`: actual Godot viewport captures, not marketing renders.
- `scripted-traversal-frames/hero-composition.png` and `hero-wide.png`: additional actual Godot fixed-camera composition studies after the fifth regular frame. They are not physical-input screenshots, do not replace any of the five traversal frames, and are not included in the 18-second traversal movie. Each requires its own successful `TIDAL_HERO_CAPTURE` save receipt and full PNG decoding.
- `site/`: standalone official Godot Web export, single-threaded, GL Compatibility, with runtime, font, and model/texture notices. The font is exported through Godot’s normal resource import/remapping; the game supports imported loading and a raw-file fallback for unimported native runs.
- `desktop-1280x720.png`, `portrait-390x844.png`: actual Chromium WebGL screenshots after the real Godot `TIDAL_FRAME_READY` event (emitted after `RenderingServer.frame_post_draw`), a browser compositor turn, and actual WASM/PCK loads. Desktop W/E must activate lantern I within 15 seconds. Desktop and portrait have independent result JSON files; a desktop failure does not skip portrait evidence. Portrait performs one two-second emulated touch gesture and requires a fresh read-only game receipt proving horizontal displacement greater than 0.25, actual drag/physics processing, and cleared input after release. Desktop then physically presses L and checks the actual rendered Chinese labels, including the temporary prompt, and reported font-codepoint coverage before saving `desktop-zh.png`.

Local unit tests only validate the harness's isolation and failure guards. They do not substitute for successful hosted native/Web steps. On an MCP/API mismatch the stage fails with a blocker and preserves exact receipts. On renderer/input/capture failure it keeps actual logs/screenshots and never substitutes generated imagery or claims success.

## Reproducible dependencies

- Godot official 4.6.3 Linux archive SHA-256: `d0bc2113065e481c9c2c2b2c37daa4e8be3fe9e27f0ab9ab0b6096e9a37907f3`
- Extracted binary SHA-256: `f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3`
- Official no-threads release template SHA-256: `1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9`
- `dcc-mcp-godot==0.9.6`, `dcc-mcp-core==0.20.42`
- Browser wheels use the repository's existing hash-pinned `requirements/browser-preview.lock`; the official template fetcher verifies member hashes.

This candidate is not published, deployed, merged, or added to a gallery by the workflow. Software-rendered CI and emulated portrait are not physical-device or subjective visual acceptance.

## Shared downloader provenance

The bounded 1 MiB range downloader and its tests are reused unchanged from the independently reviewed Showcase draft #42, commit `858e8e04c56811c9cff379249699911ba568af24`. Official archive/member pins and fail-closed range checks are retained. Native capture runs before Web template retrieval, so a transport outage does not suppress the visual preview. The source immutability check is scoped to this recipe and workflow; legacy gallery media have existing LFS normalization warnings.

## First-frame and error acceptance

`TIDAL_READY` only establishes scene initialization. Native capture/input and browser capture/input wait for `TIDAL_FRAME_READY`, with a 150-second first-frame deadline for software shader compilation. The native smoke allows up to 15 seconds of genuine W/E and exits early only on the actual lantern event. R is confirmed through the game’s own reset-save readback. Every `ERROR:` diagnostic is fatal; no Vulkan or missing-font errors are silently allowed. The editor explicitly selects `opengl3`, and the runner installs software Vulkan support for any editor-side device probes.

The workflow uploads `tidal-sanctuary-native-preview-<commit>` immediately after native capture, including diagnostics on input failure, before fetching Web templates. The final candidate bundle remains separate and includes both independent browser outcomes.

## Declared model assets and next-pass observers

The manifest explicitly includes four self-contained Kenney-derived text scenes plus `assets/KENNEY-LICENSE.txt` and `assets/SOURCE.json`. Nested paths are copied into the isolated authoring/runtime/export projects, and every declared source file except the deliberately MCP-created root scene retains its source SHA-256 check. The Web site includes `assets/KENNEY-LICENSE.txt` and `assets/SOURCE.json`; export receipts hash those nested notices too. Kenney models are CC0 assets, not original models authored through MCP.

`observers.py` validates fresh exact-prefix receipts from the game. It rejects stale IDs, malformed/nonfinite positions, vertical-only movement, cancellation, demo input, missing drag/physics activity, uncleared touch state, untranslated sampled labels, and missing glyph reports. This evidence covers one emulated gesture and one sampled English-to-Chinese UI transition. It does not establish physical-phone support, full-game completion, or comprehensive localization. These additions require a new hosted run; they do not change the results of the earlier successful acceptance run.


## Hero composition refinement and Poly Haven resources

The explicit source manifest adds four native `.res` fern mesh resources, five static image byte buffers under `assets/polyhaven/`, and `assets/POLYHAVEN-LICENSE.txt` / `assets/POLYHAVEN-SOURCE.json`. These CC0 assets remain attributed to Poly Haven. The game reads the image buffers into `Image`/`ImageTexture`; the native session therefore does not depend on an omitted editor import cache. Web export includes only the five declared `.bin` paths, without a broad binary-file wildcard. Both Poly Haven notice files are copied into the exported site's `assets/` directory and covered by the export's file hashes.

The two hero PNGs are actual rendered fixed-camera composition studies. The native report keeps them in `composition_studies`, separately from `actual_captures` (the five regular traversal PNGs) and the existing X11 physical-input evidence. Their successful save receipts must follow the fifth regular capture. The existing early native artifact already uploads this complete frame directory before Web template retrieval, including when a later input check fails. All existing MCP authoring, input, browser, crash, and strict error guards remain in place; this visual refinement adds no new gameplay acceptance claims.
