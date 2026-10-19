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
3. Author a new isolated candidate through the actual headless editor:
   `python ci/author_native.py --headless --source game --output /tmp/dawnkeep-author --godot godot`
4. Capture the fast real native gate:
   `xvfb-run -a -s '-screen 0 1280x720x24' python ci/capture_native.py --native /tmp/dawnkeep-author/native --output /tmp/dawnkeep-preview --godot godot`
5. Inspect the actual native images before requesting longer capture.
6. Fetch templates with the shared `scripts/godot_web/fetch_templates.py`, then
   use `ci/export_web.py --native ... --template ... --license-dir play/runtime --output ...`.
7. Use `ci/capture_browser.py --site .../site --output ...` against the exported
   bytes. The harness serves loopback HTTP itself. It never swaps in a web clone.

CI uses `author_native.py --headless` for genuine typed MCP editor authoring,
validation, save and restart/reopen. This avoids graphical editor thumbnail
reimports overlapping script-creation scans; it proves no visible render or
native input. Engine-error checks remain strict, and the separate rendered X11
native image/input gate remains mandatory before Web export and browser tests.
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
and actual onExit, fresh engine restart, then a required-PCK download outage held through the loader's internal retries
until the actual failure UI appears. The route is restored before clicking the
visible Retry control. A one-request interruption is insufficient because the
official loader can recover it without showing an error. Engine gameplay is observed through
console output only. Portrait results are emulated touch, not physical-device
compatibility. Source/download bytes, deployed pages, privacy, rights and
final victory/balance remain separate acceptance stages.

## Guard tests

Run `python -m unittest discover -s ci -p 'test_*.py' -v` and
`node ci/test_web_shell.js`. They validate harness behavior and fail-closed
inventory/lifecycle boundaries; they are not runtime gameplay evidence.

Run `python ci/verify_headless.py --source game --output /tmp/dawnkeep-headless`
for isolated mechanics, eight-viewport bilingual layout, bundled-font glyph
coverage without system fallback, main-scene integration, separate active/paused/
locked-audio shutdown processes and public-command balance fixtures. This explicitly separate synthetic stage
preserves logs and exact source hashes; it does not replace real input.

### Browser security capability boundary

Chromium's sandbox stays enabled. The pinned Playwright defaults inject
`--enable-unsafe-swiftshader`; the harness explicitly excludes that default,
not just omits it from its own launch arguments. The exclusion is regression
checked and recorded in `browser.json`.

The hosted Ubuntu 24.04 run on `9a086ff` stopped at browser launch with
`No usable sandbox`. MCP, headless, rendered native input and official Web
export had passed. Do not disable the sandbox, change AppArmor/user-namespace
policy or mark browser gameplay accepted to make the job green. A supported
sandbox-capable browser must be established before that browser stage can pass.

The Dawnkeep workflow now explicitly selects the Ubuntu runner's preinstalled
stable Google Chrome at `/opt/google/chrome/chrome`, the standard path covered
by Ubuntu's shipped Chrome sandbox profile. It requires that exact canonical,
executable file and prints its installed version. The harness also validates and
records the resolved path and actual `--version` output before launch. Missing
or invalid Chrome fails without falling back to bundled Chromium. This does not
change AppArmor, user namespaces, sandbox policy or browser security flags.
Unlike the hash-pinned Playwright package, the runner's installed Chrome version
can change; every result must therefore retain its actual version receipt.

References: [Chromium's Ubuntu sandbox documentation](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md)
and the [official Ubuntu 24.04 runner inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md).
Browser launch, WebGL2 capability and actual gameplay acceptance remain separate
checks; selecting a supported executable alone proves none of them.

### Release-quality regressions found by actual Web review

The native font fallback hid four missing Chinese characters in the new focus
instructions. The shipped renamed Noto subset now includes them, and the actual
Godot UI fixture checks all 391 required UI characters on a test-only FontFile
copy with system fallback disabled. Browser capture includes the intro screen.

Normal desktop/Web close requests now stop audio, release stream references and
wait for AudioServer's playback weak references to clear before exiting. Three
separate fixed-fps process fixtures cover active, paused and locked audio plus
repeated close requests. A retained-playback mutation verified that the two-second
bound remains fatal; no shutdown diagnostic is ignored. Headless process results
are separate from actual rendered/browser close acceptance.

Portrait movement uses observed world projection to known empty terrain. The
old fixed screen fraction could select a build platform instead; that was not a
valid movement test. The same actual touch route and movement assertion remain.
