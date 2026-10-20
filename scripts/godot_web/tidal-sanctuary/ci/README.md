# Tidal Sanctuary CI acceptance

Install this directory as `scripts/godot_web/tidal-sanctuary/ci/` and the authored game as `scripts/godot_web/tidal-sanctuary/game/`. The companion workflow is `.github/workflows/tidal-sanctuary-preview.yml`.

The workflow has read-only repository permissions, no saved checkout credentials, no deploy step, and no upload except the explicit Actions artifact. Every generated project, save, browser profile, editor session, export and capture goes into a new directory under `RUNNER_TEMP`. The original checkout is never opened in Godot. The final tracked-file diff checks for mutation. Native rendering is run only in the approved hosted Xvfb job; local unit tests do not establish rendered acceptance.

### Retained browser failure and safe-renderer candidate (2026-10-19)

Head `3ff0eb1` [run 39089394037](https://github.com/dcc-mcp/showcase/actions/runs/39089394037) passed native authoring/input/save but failed both Web viewports immediately after real Begin. Audible samples exist, but the main-thread meter has multi-second gaps and cannot satisfy sustained-output evidence. The retained desktop failure snapshot additionally shows the first 32-second music source ending at audio clock 32.182857 and its replacement starting at 33.750204, a real 1.567-second source gap. The failure snapshot was collected after a diagnostic screenshot and is not relabeled as the earlier rejected window.

The candidate now uses the runner's explicitly verified `/opt/google/chrome/chrome`, with the Chromium sandbox enabled, no forced graphics backend, and both Playwright's mute and unsafe-SwiftShader defaults excluded. Missing browser/WebGL capability fails; the harness never opts into unsafe rendering. Chrome may select its own software fallback; the actual context renderer is retained as diagnostic metadata. Runtime, source/PCM identity, strict meter density, cue/loop seam, actual-input and fresh-process restoration gates are unchanged. This configuration change is not a rendered performance or audio-success claim; exact-head hosted evidence must establish the result.

### Exact-rendering optimization candidate

The safe-browser head `ad1865e`, [run 39271590853](https://github.com/dcc-mcp/showcase/actions/runs/39271590853), passed the stronger native rendered-state/input/save checks but still failed fresh after-Begin audio-meter evidence in both Web sizes. Changing browser selection alone did not repair the stalls. That failed run and its real frames remain retained.

The next water candidate reuses the lattice hashes shared by the five existing finite-difference samples. It preserves the same scene, topology, two ripple octaves, original sample-coordinate and interpolation order, displacement and normals; the vertex stage computes 18 sine hashes instead of 40. Deterministic arithmetic fixtures are not a GPU-speed or rendered-equivalence claim. No audio, input, physics, resolution or quality threshold is relaxed. Passive `render_diagnostics` values retain actual draw-frame counters and monotonic microseconds; they are informational and never replace the acceptance gates.

The actual restored native image exposed full-width English curly apostrophes in the shared CJK font. English story punctuation now uses compact ASCII quotes/apostrophes; Chinese punctuation and the font remain unchanged. New rendered images are still required.

### Owned Web audio candidate

Head `a08ccc3`, [run 39280668738](https://github.com/dcc-mcp/showcase/actions/runs/39280668738), still failed both Web fresh-meter checks and the native chart-contact probe. These failures remain the baseline; fixture or export success does not replace actual-input acceptance.

The Web-only candidate selects Godot's registered Dummy driver with a positive mix rate and uses the public JavaScriptBridge to own one browser AudioContext for all five unchanged original assets. Desktop audio retains its Godot players, buses and fade. The browser music source loops natively over the full 32-second buffer; its fade runs on the audio clock. Initialization decodes silently, Begin is the only initial activation, mute preserves the source, and focus suspends/resumes that same context. Initialization/resume have bounded retryable failures, shown in native Godot cards. The export copies only manifest-owned original audio/helper files and records their hashes and licenses.

The pinned official shell now silently predecodes these assets before `Engine.startGame`, preventing heavy first-frame setup from consuming the bounded audio preparation window. Failed preparation remains visible through the native Retry card and actual error receipts. Touch Begin/Retry arms inside the enabled native button and activates on matching release, when browser transient activation is available; cancellation, dragging outside, focus loss and card/action replacement disarm it. Emulated mouse edges for that button are deduplicated while ordinary body scrolling and physical mouse/keyboard remain native. These changes still require actual browser qualification.

The observer now counts every constructed context, including unused ones, and rejects source-loop/pitch changes or automation. Existing running, mute, cue, seam, PCM and real-input thresholds remain. Added tab-focus acceptance requires fresh observations of the same suspended clock, source IDs and zero genuine terminal gain, then actual resumed PCM. Suspended AnalyserNode data is retained unchanged because the Web Audio specification freezes that buffer; it is not relabeled as fresh silence. Save & return additionally awaits real context closure, and the live recording continues through focus and normal exit. Browser qualification of this candidate is still required. No lower-resolution or reduced-quality CI mode is enabled.

## Evidence, kept distinct

- `authoring.json`, `mcp-raw.json`, `mcp-tool-schemas.json`: actual discovered typed MCP calls and responses. All four gameplay scripts are created and validated through the typed script API. Godot creates the Node3D root, attaches the main script and saves the scene. A different editor process reopens the saved scene, reads its tree and verifies its unchanged hash. This does not claim every generated mesh was individually authored through a tool.
- `native-validation.json`: actual headless swim/treasure regressions and scene audit, full physical X11/XTest WASD/E treasure route, five rendered milestone images, actual version-2 save-file readback, new Godot-process save restoration and physical R reset. There are no game-property writes, position teleports, synthesized saves or demo flags in the physical-input process.
- `native-input-route.json`: emitted OS input events, every passive actual physics sample and reached route milestone, including failures. Camera-relative steering reads positions and camera basis from logs; it never sets them.
- `tidal-01.png` through `tidal-05.png`: real X11 screenshots while physically playing the route: fresh beach, inland treasure, first wading, first swimming, and treasure returned to the ring. They use the normal player-follow camera. No hero-camera shortcut is accepted. Each PNG is fully decoded and hashed.
- `native-restored.png`: the actual new Godot process after loading completed treasure progress and its saved position.
- `scripted-treasure-swim.mp4`: continuous 24 fps X11 capture of actual native `--demo` gameplay, explicitly scripted and separate from input/completion proof. Passive demo observations must establish that sea swimming occurred during the recording interval. Recording lasts at least 36 wall seconds and four seconds after swimming is observed, with a 120-second acceptance deadline. The measured duration is reported rather than claiming an exact clip length. The 1280×720 H.264 output is fully decoded. It has no audio stream.
- `physical-input-treasure-swim.mp4`: separate, continuous, unretimed X11 recording of the real WASD/E acceptance route. The driver starts only after ffmpeg reports an actual captured frame. Passive `demo=false` observations inside the recording interval must establish the full water crossing and completed quest. The recorder must remain alive through completion, stop cleanly, and fully decode; the 600-second recording ceiling is a failure bound, not a claimed duration. Its measured duration, hash and observations are retained.
- `site/`: standalone official Godot Web export, single-threaded GL Compatibility, including runtime, font and model/texture notices.
- `desktop-1280x720.png` and `portrait-390x844.png`: real Chromium WebGL screenshots after the actual `TIDAL_FRAME_READY` event (after `RenderingServer.frame_post_draw`), a browser compositor turn, and verified WASM/PCK loads.
- Each viewport has independent `*-result.json`, `*-initial-console.json`, `*-restored-console.json`, `*-input-route.json` and five `*-tidal-NN.png` route screenshots. Desktop failure does not skip portrait. Desktop completes the full route through actual WASD/E browser events. Portrait completes the same route with one continuous primary touch gesture and second-finger taps on the actual rendered action button. A fresh release receipt must prove real drag/physics activity, displacement and cleared input.
- Desktop also physically presses L at the fresh quest start, validates the actual rendered Chinese labels and font-codepoint coverage, and captures `desktop-zh.png`. A second physical L returns to English. This is one sampled language transition, not comprehensive localization coverage.
- Each Web viewport physically clicks/taps the shipped Save & return control after completion. The game explicitly closes its final save, and the public Godot normal-exit API awaits pending and final asynchronous filesystem synchronization. The host waits for actual onExit(0), rejects engine/save errors and requires a real persistent final save after the input request before showing Saved. It then fully closes its Chromium process. An entirely new process opens the same isolated browser profile and origin; it must load matching quest flags, language and horizontal position from the game's persisted save. `*-restored.png` records that state. No IndexedDB or save data is injected.

## Authored route and passive contract

`gameplay.py` declares the actual navigable route explicitly: beach map `(1.3,7.8)`, inland cache `(-3.8,3.4)`, sheltered bay entry `(1.5,6.2)`, sea treasure `(8.2,5.5)`, exit beach `(7,.5)`, inner path `(2,-3)`, and return ring `(0,-11.7)`. The map, land cache, sea cache and return interaction advance quest stages 1–4. The two treasure flags and final completion must all be true.

`TIDAL_STATE` is a passive schema-1 receipt emitted after physics, with increasing sample ID and physics frame, actual position, `walk`/`wade`/`swim` mode and finite water depth, normalized horizontal camera axes, rendered action-button rectangle, quest stage, two treasure flags and completion. It also identifies whether demo input is active. Observers reject malformed/nonfinite data, stale frames, impossible horizontal jumps, progress regression and demo evidence in physical-input routes. The route requires `walk → wade → swim → wade → walk`, including at least one uninterrupted physics second of swimming. Observer silence, crashed runtime, failed waypoint, missing screenshot or partial quest completion fails acceptance.

Quest stages must advance exactly one at a time, match the treasure/completion flags, and follow a completed physical-action callback at the correct authored target. Each milestone gets one action, then waits for its actual receipt. The advancing sample must be inside the game's 1.55 m interaction range; acknowledgement does not require returning to the smaller 0.8 m navigation radius after callback latency. Ordinary path turns retain shared held keys instead of releasing and immediately re-pressing them.

Portrait keeps touch ID 0 held. A secondary action sends `touchStart` with only changed ID `[1]`, then `touchEnd` with only `[1]`; final release uses `touchEnd` with no points. This matches the default Chromium `DispatchWebTouchEvent`/`CreateWebTouchEvents` implementation in [input_handler.cc](https://raw.githubusercontent.com/chromium/chromium/153.0.8010.12/content/browser/devtools/protocol/input_handler.cc). The optional `SyntheticPointerActions` path has different active-set semantics and is not enabled here. A premature primary release fails immediately, and the final receipt must still prove one uninterrupted gesture.

Required browser PNG captures use an explicit finite 120-second deadline, with measured duration retained. Diagnostic failure captures have a separate 30-second ceiling and never substitute for required images. Capture overhead is excluded from the 75-second movement budget; passive observations are re-read after capture and the 10-second observation-silence guard remains. Screenshot-associated state is labeled as the passive sample before the request, rather than claiming exact framebuffer synchronization.

The completion-save observer retains only real saves emitted after this route's `TIDAL_COMPLETE` boundary, validates completed flags/language/finite position against the actual route, and then tests restoration in a completely new browser process. It does not require another periodic save after slow screenshot overhead or synthesize a receipt.

`TIDAL_LOAD` and `TIDAL_SAVE` use schema-1 observer envelopes. The actual disk file `tidal-sanctuary-v2.json` uses save schema 2. Restore validates matching quest stage, treasures, completion, language and horizontal position against the earlier actual save. `TIDAL_LOAD.found` must be true in the fresh process. Native additionally reads the actual save file independently.

Unit fixtures in `test_ci.py` and `test_gameplay.py` validate isolation and fail-closed guards. They never substitute for hosted native/Web acceptance. The retained legacy fixed-camera collector has isolated unit coverage only; it is not invoked by this route and its images cannot satisfy any current visual or input check.

## Reproducible dependencies and source ownership

- Official Godot 4.6.3 Linux archive SHA-256: `d0bc2113065e481c9c2c2b2c37daa4e8be3fe9e27f0ab9ab0b6096e9a37907f3`
- Extracted binary SHA-256: `f64d4ed19fc9df9440321653fcc80df8c6e365ba7b6de0a29e2cfa9fa71bfeb3`
- Official no-threads release template SHA-256: `1446f79dc12f60ce5d244c39fb6628ec298337ca5c4f91a16491feea72aa1bc9`
- `dcc-mcp-godot==0.9.6`, `dcc-mcp-core==0.20.42`
- Browser wheels use the existing hash-pinned `requirements/browser-preview.lock`; the official template fetcher verifies member hashes.

The source manifest explicitly includes `main.gd`, `swim_controller.gd`, `water.gdshader`, three headless regression scripts, scene/project configuration, font, four self-contained Kenney-derived scenes, four Poly Haven fern mesh resources, five exact static image-byte paths and all asset notices. Nested paths are copied into isolated authoring/runtime/export projects. Every declared source file except the deliberately MCP-created root scene retains its source SHA-256 check. All four gameplay scripts are created and validated through typed MCP. Export retains only the five declared `.bin` buffers, without a binary wildcard, and copies all seven model/texture notices byte-for-byte.

The bounded 1 MiB range downloader and tests are reused unchanged from independently reviewed Showcase draft #42, commit `858e8e04c56811c9cff379249699911ba568af24`. Official archive/member pins and fail-closed range checks remain. Native capture precedes Web template retrieval, and the early native artifact preserves useful real previews and input diagnostics even if a later stage fails.

## Strict runtime boundaries

Dependent headless regression scripts are excluded from the initial editor project and copied only into the stopped native package. A small non-shipping, read-only @tool probe is invoked through the official typed editor API to observe filesystem scan completion and resource types on advancing editor frames before dependent authoring operations. Its source, hash and actual responses are retained; it is not an editor plugin or a substitute for successful authoring.

`TIDAL_READY` establishes only scene initialization. Native and browser input wait up to 150 seconds for the actual post-draw `TIDAL_FRAME_READY` boundary. Every `ERROR:`, script/parse/shader error and crash diagnostic is fatal; no missing-font or Vulkan errors are silently allowed. The editor explicitly selects `opengl3`, and the runner installs software Vulkan support for editor-side probes. Runtime liveness is checked before accepting evidence and before deliberate shutdown. Only normal exit or the harness's own SIGTERM is accepted for input-test termination.

This candidate is not published, deployed, merged or added to a gallery by CI. Software-rendered CI, emulated touch and screenshots do not establish physical-device performance or subjective visual acceptance. On a tool, renderer, input, capture or persistence failure the stage remains failed, preserves exact evidence and never substitutes generated imagery.

## Web shutdown boundary

The earlier d9d453cc abrupt-close desktop run restored stage 3 instead of completed stage 4. That failed evidence remains retained. A virtual FileAccess write is not proof of IndexedDB completion; the in-game completion message therefore no longer claims that progress is already durable. Players should use **Save & return** and wait for the saved confirmation before leaving. The current acceptance verifies that explicit normal-exit flow and then starts an entirely new browser process. Immediate tab/browser termination, browser storage eviction, private browsing and power-loss durability remain unverified.

The host uses only the public EngineConfig onPrint/onPrintError/onExit callbacks and Engine.requestQuit API. It does not call private GodotFS synchronization functions, inspect or write IndexedDB, inject save data or synthesize game progress. A zero exit code alone is insufficient: missing final save, unavailable persistent storage or any engine error prevents the saved UI. Fresh-process LOAD validation remains the ultimate restore check. Fixed reference: [Godot 4.6.3 final sync](https://raw.githubusercontent.com/godotengine/godot/4.6.3-stable/platform/web/js/libs/library_godot_os.js).


### Single-thread physics lifecycle

The b42e72fe run completed both actual-input treasure routes but refused Save & return because the official engine reported an unreclaimed WorkerThreadPool Group at shutdown. The failure and its original logs remain retained; the error is not ignored or relabeled as harmless.

This pure 3D project explicitly uses the official built-in **Jolt Physics** backend and the unused 2D **Dummy** backend on both native and Web. In the pinned 4.6.3 no-threads source, [Group completion cleanup](https://github.com/godotengine/godot/blob/4.6.3-stable/core/object/worker_thread_pool.cpp#L725-L758) is excluded by THREADS_ENABLED, while Godot Physics [3D constraint steps](https://github.com/godotengine/godot/blob/4.6.3-stable/modules/godot_physics_3d/godot_step_3d.cpp#L344-L368) and 2D constraint steps still allocate groups. Jolt uses [ordinary tasks with explicit completion/reclamation](https://github.com/godotengine/godot/blob/4.6.3-stable/modules/jolt_physics/spaces/jolt_job_system.cpp), and Dummy has no 2D simulation. These are [public project settings](https://github.com/godotengine/godot/blob/4.6.3-stable/doc/classes/ProjectSettings.xml#L2529-L2534), not patched engine binaries or custom plugins. Control-based UI does not need 2D physics.

This is a source-grounded configuration repair, not proof by itself. The unchanged official binary/template hashes, all runtime-error guards, actual native and two-viewport Web routes, and strict fresh-process save restoration must pass again. Negative fixtures explicitly keep the observed Group error fatal.

### Blender tropical asset candidate

The native/export copy manifest additionally owns eight standalone GLBs: two original palms, two original broad-leaf plants, three CC0 KayKit bush/stone derivatives and the KayKit-derived explorer. All three new CC0/source notices are copied byte-for-byte beside the Web export, bringing the total to seven. Actual Godot import and rendering remain required: a valid GLB or Blender preview alone is not Web acceptance. Shared input, engine-error, normal-exit and new-process save/LOAD guards remain unchanged.

The fresh native capture copy now runs the pinned official headless editor import before regression or runtime launch. It checks the importer exit/log and all eight GLB PackedScene import descriptors, and retains `native-import.log`. No editor cache is copied from the authoring session. The first tropical-art CI failure is retained: native GLB loading failed before real input because the clean capture copy had not yet been imported; Web export already performed its own import.

The subsequent native run imported all assets and rendered swimming, but its input route stopped after the swim screenshot: the harness intended to hold D, while passive game samples showed zero movement. Pearl interaction was never requested. The native adapter now waits after a real all-movement-key release for a newer live physics sample with finite neutral input before another press. The baseline is read after keyup, both sample and physics IDs must advance, and the 10-second deadline fails closed. Ordinary shared held keys, single action requests, route/screenshot budgets, every passive route sample, browser input and save/restore guards are unchanged. The precise X11 event-coalescing cause remains an inference; successful command delivery alone is not treated as observed game input.

### Collision and off-route acceptance

The retained 099ae060 run passed native and desktop Web, but portrait missed the last interaction after stop-command latency carried the player outside reach. The shared driver now establishes a passive boundary after the actual stop callback returns, then requires a strictly newer sample and physics frame, neutral movement input, horizontal speed at most 0.08 m/s and the game's shared interaction availability. It re-approaches physically before its one action if inertia carried it away. The final navigation point is `(0,-10.25)` with a 0.25 m approach radius; the authored beacon target remains `(0,-11.7)` and interaction remains strictly below 1.55 m. Pending actions never repeat.

`verify_collision.gd` independently compares visual triangles with physical ray intersections, checks all large rocks and palm trunks, attempts controller crossings through solid quest props/walls, climbs and descends the threshold, and tests height/LOS/own-target/duplicate-action gates. These are explicitly fixture-position/direct-controller tests, not keyboard or manual-play evidence.

Before the native quest recording route, `exploration.py` physically walks around the chart and holds W/S against its opposite flat faces. `chart-blocked-normal-v2` requires 12 consecutive actual `KinematicCollision3D` contacts: the same authored solid, matching face point/normal, inward input, positive attempted inward velocity, blocked normal velocity, at least 5 cm cumulative rejected inward sweep, and capsule clearance from the face plane. It also requires at least 15 cm of actual approach, opposite measured normals and radial directions, contiguous source-bound physics steps, and fresh `demo=false`, stage-zero state. Tangential sliding is allowed. This replaces the inappropriate total-position stationary-stop assertion, which rejected correct sliding against the bevel in head `4ed1a1f`; it does not remove collision or penetration proof.

The passive 32-step motion buffer records values immediately around the unchanged production `move_and_slide`. Native chart-area state receipts use a four-physics-step cadence to avoid stale observations across software-render bursts; Web observation and gameplay are unchanged. The same validator must accept real headless solid fixtures at the lane center and both staging-band edges, and reject identical approaches with the collider removed plus idle wall-adjacent controls. Those fixture spawns are explicitly separate from the actual X11 keyboard route. The 35-second approach and three-opposite-attempt limits remain.

After contact checks the player returns by an outside route and continues the complete treasure/swim loop without resetting or injecting position/progress. Two ordinary-camera contact images and `native-off-route-exploration.json` retain the evidence, including source and validator hashes. New exact-head artifacts are required for this contract; earlier receipts cannot qualify retroactively. This bounded automated exploration is not comprehensive human playtesting. All engine-error, shutdown and new-process restoration checks remain strict.


## Pinned typed-script bridge capacity

Head `d136c6b` [run 39353662052](https://github.com/dcc-mcp/showcase/actions/runs/39353662052)
failed during typed `create_script` before gameplay. The pinned Godot addon 0.9.6
keeps `WebSocketPeer`'s 65,535-byte inbound buffer. The pinned Core 0.20.42 bridge
request grew from 64,503 encoded bytes at `4ed1a1f` to 68,916 bytes at `d136c6b`;
source length alone (62,241 versus 66,532 UTF-8 bytes) understates the JSON cost.
The editor log had no engine crash or parse error; the bridge disconnected on
that oversized request. Godot 4.6.3 sets wslay's maximum received message length
to this buffer size ([engine implementation](https://github.com/godotengine/godot/blob/4.6.3-stable/modules/websocket/wsl_peer.cpp#L379-L389)).
This is a concrete adapter transport limitation, not a gameplay failure. A local
isolated Godot 4.6.3 WebSocket reproduction received 65,535 bytes successfully;
65,536 and 68,916 bytes closed with code 1009 (`Message too big`). All nine
bounded intermediate scripts also passed actual headless engine parsing.
These local checks do not substitute for hosted typed-MCP acceptance.

`author_native.py` now preflights the complete typed-authoring plan before that
script is mutated. It caps conservative JSON-encoded requests at 48 KiB, stages
only supported complete `void` function bodies as `pass`, and restores each
through the official exact-search `edit_script` action. Unsupported syntax,
ambiguous replacements, or an individual edit exceeding the budget aborts the
candidate. Every write retains the actual scan-idle boundary and path-only typed
validation. Final on-disk byte hashes and fresh-editor save/reopen checks remain
mandatory. Failure never packages a partial scaffold. No addon limit is changed,
no full script is read back over the similarly bounded response channel, and
no direct filesystem script-authoring fallback is used. Actual MCP acceptance
must come from a new exact-head run, not the prior failed artifact.

## Audio-thread observation candidate (2026-10-20)

Head `ff747ae`, [run 39354896538](https://github.com/dcc-mcp/showcase/actions/runs/39354896538),
passed bounded typed MCP authoring, actual native opposite-face keyboard contact,
the complete treasure/swim route, fresh-process save restoration, and official
Web export. Both actual Web viewports reached silent initialization and real
Begin, then failed sustained fresh audio-meter evidence. Their exact rejected
windows contain only two or three main-thread analyser observations; those sparse
samples do not establish continuous sound. This failed baseline stays retained.

The candidate observer uses a test-only public
[AudioWorkletProcessor](https://www.w3.org/TR/webaudio/#AudioWorkletProcessor)
to measure the browser's actual rendered PCM on the audio thread. It observes
one post-master mix tap and the two real upstream gain buses, pre-armed before
Begin. Original speaker edges, sources, assets, native loop and context lifecycle
are unchanged. Observer output is always zero into the existing capture stream;
it cannot generate audible replacement samples or resume a context. The shipped
game does not include this observer.

Each complete 100 ms record retains actual sample-frame bounds, channel sample
counts, per-channel square sums/RMS/peaks and clipping counts. Partial records
remain intact for integrity checks; only fully contained complete records count
toward required coverage. Missing input is an explicit gap, never assumed zero.
Missing, duplicated, reordered, discontinuous or malformed records fail closed,
as do bounded queue/storage overflow and processor errors. A snapshot freezes
its real context-clock cutoff before draining queued messages. Independent wall
time and the audio-thread drain watermark must establish elapsed coverage;
message delivery time is never relabeled as capture time.

Audibility and quiet thresholds remain `1e-4` and `1e-5` RMS respectively.
Running windows require contiguous real frames for their full minimum duration.
Cue and first-loop-seam checks require audible PCM on both the original source
bus and post-master mix, so background music cannot conceal a silent cue.
Source identity, trusted input, original durations, loop bounds, pitch, no music
overlap, actual topology and historical gain events remain independent checks.
A cue-time mute, rewire, competing source or unsupported automation fails even
if a later snapshot looks normal. The decoded Ogg's actual one-frame-short
buffer duration defines its native loop boundary without adding a sample.

A short hosted audio-only browser fixture checks the observer against the real
backend and unchanged assets before costly engine work. It is not Godot input,
rendering, loop-seam, focus or save acceptance. Full exact-head native and both
Web routes still must pass. The separate focus-suspension guard still requires
fresh main-thread observations of a frozen context and zero real terminal gain;
a suspended processor produces no fresh PCM. Live recording, closure and
fresh-process restoration checks remain in force.

Unit fixtures explicitly use fabricated inputs only to test rejection logic;
they never become runtime evidence. Passing audio-thread continuity does not
establish animation/input responsiveness, rendered frame rate, hardware GPU or
physical-device performance, or subjective listening quality. Software rendering
remains a known performance concern and cannot be relabeled playable on the
strength of an audio result.

### First-loop and real target-focus ordering (2026-10-20)

The `58e23f6` hosted run completed both actual keyboard/touch treasure routes,
but did not qualify the complete Web lifecycle. On desktop, slow rendering put
the intentional mute across the first music loop; on portrait, Playwright's
forced-focus emulation prevented real tab focus loss. These are failed receipts,
not a completed Web acceptance claim.

The harness now observes and validates the original first loop seam before its
intentional mute/unmute probe. The seam remains the first decoded-buffer boundary,
with the same source, observed gain history, dense music-bus and post-master PCM,
continuity and clipping gates. It cannot substitute a later seam. The exact early
snapshot is retained before validation, and its wait has a bounded audio-clock
observation deadline.

After final navigation and before Begin or the audio baseline, each test page
disables Playwright's default forced-focus emulation once through a retained CDP
session. Navigation can restore the original Playwright session's override; a
pre-navigation disable alone did not pass the `32a26cf` hosted smoke. The helper
rejects re-arming or navigation after this settled boundary. Real browser target activation then
must produce trusted window blur/focus events plus matching passive DOM focus.
Visibility is separately recorded: two browser windows can both remain visible
while only one is focused. A foreground return must be visible, but a genuine
blur is not relabeled as hidden-tab coverage. Any actual visibility-change
events must be trusted and consistent with their observed state. No synthetic event, JavaScript focus call or
repeated emulation toggle qualifies. The companion tab is created before Begin,
so its automatic activation cannot add a mid-route audio focus transition. The
original same-context suspended clock, zero terminal gain, source identity and
resumed PCM gates remain. A lightweight hosted smoke tests this lifecycle before
the costly Godot run; neither fixtures nor that smoke replace actual gameplay,
normal exit and fresh-process save restoration. New exact-head evidence is required.

The `efed55b` second hosted attempt observed a genuine trusted blur and
`document.hasFocus() == false`, while the page remained visible in its headless
window. Requiring hidden state for that target-focus transition conflated two
different browser properties. Target-focus acceptance preserves the original
real blur/focus plus audio suspension/resume requirements; hidden-tab and OS
application focus behavior remain unverified.


### Separate genuine hidden-tab lane (2026-10-20)

Exact-head `00ec229` run `39365593281` passed the full portrait touch, audio,
focus and fresh-process save restoration route. Desktop completed its keyboard
quest and original first-loop PCM gate, and delivered genuine blur/focus, but
failed the unchanged suspension observation density gate: the visible software
renderer blocked the main-thread sampler for roughly 3.3 seconds. A suspended
clock observed at sparse endpoints is not continuous proof. This desktop
visible-unfocused result remains runtime-limited, not passed.

The separate hosted lane uses `--headed` Chrome under Xvfb, a supported
[Playwright Linux headed CI configuration](https://playwright.dev/python/docs/ci).
It requires real same-window tab activation and trusted hidden/visible transitions,
not a synthetic visibility event, forced lifecycle freeze or reduced viewport.
The original audio graph, clock, gain, source identity, fresh observation density,
PCM, loop, input and persistence gates are unchanged. Product source is unchanged.
The lightweight actual-browser smoke must pass before the expensive game route.
A new exact-head hosted result is required; adding this lane is not itself a pass.
Hidden-tab acceptance does not qualify the separate visible-unfocused desktop
condition, physical devices, OS focus, subjective listening or GPU performance.


### Isolated no-defaults audio probe (2026-10-20)

The headed `25658dd` run `39369705455` proved genuine same-window targets and
trusted blur, but remained visible. The smoke failed after 17 seconds and did
not run the expensive game. Chromium's browser-process
[`EmulationHandler::SetFocusEmulationEnabled`](https://github.com/chromium/chromium/blob/main/content/browser/devtools/protocol/emulation_handler.cc)
owns a per-session visible capturer. Disabling focus from another CDP session
does not release Playwright's original session's capturer. Window focus and
browser visibility therefore differed even under Xvfb; no hidden-tab pass exists.

A manual `workflow_dispatch` with `smoke_only=true` selects a separately named
**Audio-only no-defaults probe (NOT full acceptance)** job and skips `original-3d`.
It cannot qualify native/gameplay/persistence acceptance. Ordinary PR runs keep
the full original job unchanged. The probe uses a fresh task-owned Chrome profile,
the official verified executable and public pinned Playwright 1.63
`connect_over_cdp(no_defaults=True)`, using only its existing default context.
It does not patch Playwright or set visibility, focus, audio or lifecycle state.
The browser's original sandbox stays enabled; the debug endpoint is loopback-only,
ephemeral and owned by this bounded worker. Chrome inherits the supervised process
group, so the unchanged 27-second work/30-second total limit also reaps Chrome.
All genuine hidden/visible, focus, clock, source, gain and PCM checks remain.
The full game is not moved to this route until the actual isolated probe passes.
