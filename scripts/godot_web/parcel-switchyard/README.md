# Parcel Switchyard Web preparation

This is an additive candidate for existing PR #23, based on commit
`943ee722deeec46d64890370fd813498eeebb01c`. It is not a merged, published or
accepted playable. Original assets and evidence are preserved byte-for-byte;
`original-baseline.json` binds them to that commit. Existing historical native
input, nine logic checks and the original silent movie remain historical.
The new adaptation has no new typed MCP receipt. Dated README, manifest and
validation additions describe this adaptation separately from original evidence.

## What changes

- Native GDScript adapter in `scripts/godot_web/projects/parcel-switchyard/`
  inherits the unchanged original rules and procedural visual vocabulary.
- Real standard Godot 4.6.3 single-thread Web export, using the existing shared
  official runtime. No JavaScript game simulation, screenshot UI or state
  injection stands in for the game.
- A dedicated 720 × 1320 phone presentation, primary text ≥40 logical units,
  seven touch targets ≥128 × 128 units, live desktop/phone reflow, pause/resume,
  reset and auto-send. Small numbers on moving decorative parcels are excluded
  from the primary-text minimum.
- English and Simplified Chinese shell instructions, controls, errors, rights
  and limitations, plus fully translated desktop and phone game labels. A
  renamed Noto Sans CJK SC subset supplies checked Chinese glyph coverage.
- Tap/pan normalization follows the existing Showcase Web pattern: real
  browser finger taps become native canvas mouse input, while drags scroll.
  Godot ScreenTouch handling also has separate synthetic-event regressions.

## Reproduce

From the repository root, use the existing official template fetch helper:

    python scripts/godot_web/fetch_templates.py --output /tmp/parcel-web-templates
    python scripts/godot_web/materialize_runtime.py
    python scripts/godot_web/parcel-switchyard/export.py --godot godot --template /tmp/parcel-web-templates/web_nothreads_release.zip
    python scripts/godot_web/parcel-switchyard/test_package.py
    node --check play/parcel-switchyard/shell.js
    python scripts/godot_web/parcel-switchyard/browser_test.py --site . --output /tmp/parcel-web-browser

The exporter validates the pinned official Linux editor, both official Web
export templates, the already-materialized shared runtime, and retained original
case assets/evidence before writing only `play/parcel-switchyard/`. It uses isolated
HOME and XDG directories, copies the project to a temporary directory, imports
it, runs its regressions, and invokes `--export-release Web`. Dated publication-metadata additions are allowed; original asset hashes remain pinned.
Shared runtime
bytes and shared publication manifests are verified/read, never rewritten.

The browser runner requires the repository's pinned Playwright requirements
and installed Chromium. It tests the real WASM/PCK at desktop 1280 × 900 and
emulated touch 320 × 568 / 390 × 844 in both languages. All gameplay is through
keyboard, mouse, touchscreen taps or accessible HTML buttons. Its read-only
state observer is used for assertions and native target coordinates. Test code
never calls the command bridge or sets game state. It checks correct/wrong
routes, all destinations, capacity, pause/resume, auto, repeated reset,
responsive state preservation, phone panning, desktop fullscreen, exit/restart,
language Back/Forward, deferred loading, failure/retry and cancellation.
It writes screenshots, videos and a JSON report. Inspect those actual images
and videos before visual acceptance; a passing report does not score design.

For CI, the dedicated workflow independently re-exports a temporary source copy,
then tests the untouched tracked package and generated site at the exact PR head.
Use `--site _site --expected-head <sha> --require-integration` to require all
twelve generated case/game iframe combinations as well as six standalone input
scenarios and two loading-error scenarios. Re-exported PCK bytes are a distinct
artifact, never substituted for the tracked package under browser acceptance.
Do not report a deployed-site check unless the actual production URL was tested.

## Current evidence

- Pinned editor/template/runtime identity and standard Web export: passed
- Original 9 rule checks rerun through inherited rules: passed
- Adapter's 118 headless rule/layout/geometry/text-fit/glyph/synthetic-event checks:
  passed (includes one aggregate check for the original 9)
- Python package integrity checks: 6 passed
- JavaScript syntax and Python byte compilation: passed
- Local actual browser input, rendering and screenshots: blocked before browser
  startup because Chromium's process singleton socket is denied by the sandbox
- Browser runner scenarios, visual acceptance, native GUI adapter input,
  physical devices, Safari/Firefox and production deployment: not established

`play/parcel-switchyard/export-provenance.json` binds the pack to source hashes
and contains the actual headless test measurements. Its browser status remains
`not-tested`; the separate local attempt reports `blocked`. Neither lower-level
success nor this README promotes the candidate to browser/visual acceptance.

## Integration boundary

Publication uses the existing collection and explicit play manifest. Original
case files and shared runtime bytes are not replaced by adapter export. The
manifest proposal is a derived inventory, not an approval or a replacement for
the validated publication manifest. Font provenance and complete OFL notices
accompany the renamed Parcel Interface subset. `prepare_font.py` accepts only
the pinned original Noto collection and regenerates the selected glyphs.

The original case rights are preserved; the optional Web runtime uses its
existing complete upstream notices. No additional license grant is introduced.
