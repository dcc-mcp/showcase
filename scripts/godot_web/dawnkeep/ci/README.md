# Dawnkeep actual-engine acceptance

These harnesses operate only on isolated copied source and preserve explicit
hash manifests, raw typed MCP receipts, logs and real rendered captures.
They do not change gameplay state through JavaScript, GDScript injection or a
writable bridge. See [CONTRACT.md](CONTRACT.md) for passive observer fields.

## Short preview first

The PR workflow runs the short native image/input gate and uploads actual
English and Chinese images before any longer capture. The default route also
exports the official hash-pinned single-threaded Godot Web runtime and tests
Chromium desktop plus portrait emulated touch. No video or full-combat run
starts unless workflow dispatch `full_acceptance` is explicitly enabled.

1. Install the exact Linux x86_64 / Python 3.12 DCC packages from
   `requirements-dcc.lock` with pip `--require-hashes --only-binary=:all:`.
   The 0.9.6 adapter and 0.20.42 Core pins intentionally match the previously
   exercised typed API; a newer package existing is not compatibility proof.
2. Use official Godot 4.6.3 with the executable hash in `common.py`.
3. Author a new isolated candidate:
   `xvfb-run -a python ci/author_native.py --source game --output /tmp/dawnkeep-author --godot godot`
4. Capture the fast real native gate:
   `xvfb-run -a -s '-screen 0 1280x720x24' python ci/capture_native.py --native /tmp/dawnkeep-author/native --output /tmp/dawnkeep-preview --godot godot`
5. Inspect the actual native images before requesting longer capture.
6. Fetch templates with the shared `scripts/godot_web/fetch_templates.py`, then
   use `ci/export_web.py --native ... --template ... --license-dir play/runtime --output ...`.
7. Use `ci/capture_browser.py --site .../site --output ...` against the exported
   bytes. The harness serves loopback HTTP itself. It never swaps in a web clone.

For an environment without a display, `author_native.py --headless` is genuine
MCP editor authoring/save/reopen, but proves no visible render or native input.
`diagnose_runtime.py` executes a bounded actual headless engine probe and
records currently installed tools. Missing daemons do not establish missing
capability. Sandbox/access denials must be reported, not worked around.

## Longer bounded acceptance

`--full` adds actual screen/browser movie capture, measured nonzero runtime
audio through a task-only PulseAudio sink, equipment purchase, support-tower
build/upgrade/repeated-invalid upgrade/sell/rebuild, hero level-three ultimate use,
and full eight-wave desktop victory including the boss. A restarted unattended
run must naturally lose the core, and terminal restart must restore the initial
state. Portrait includes the shorter touch route. These are observed real-input
routes, not proof of balance across every strategy.

The native movie is continuous ffmpeg X11 capture. Browser videos use the
actual Chromium page recording and audio is captured separately from the
actual sink. Every movie is fully decoded; captured PCM peak and RMS must be
nonzero. These measurements do not claim listening or subjective audiovisual
review. Listen to final sound and review composition, motion, Chinese glyphs,
mobile legibility, battle readability and input feel separately.

Web lifecycle coverage uses actual controls: fullscreen, `Engine.requestQuit`
and actual onExit, fresh engine restart, then a deliberately failed required
PCK request followed by visible Retry. Engine gameplay is observed through
console output only. Portrait results are emulated touch, not physical-device
compatibility. Source/download bytes, deployed pages, privacy, rights and
final victory/balance remain separate acceptance stages.

## Guard tests

Run `python -m unittest discover -s ci -p 'test_*.py' -v` and
`node ci/test_web_shell.js`. They validate harness behavior and fail-closed
inventory/lifecycle boundaries; they are not runtime gameplay evidence.

Run `python ci/verify_headless.py --source game --output /tmp/dawnkeep-headless`
for isolated mechanics, six-viewport bilingual layout, main-scene integration
and public-command balance fixtures. This explicitly separate synthetic stage
preserves logs and exact source hashes; it does not replace real input.
