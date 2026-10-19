# Dawnkeep: an original hero holds the Emerald Pass

Dawnkeep / 曙光守誓 is an original Godot 4.6.3 hero-defense vertical slice.
It takes its broad play loop from the historical Warcraft III “Defend Athena”
custom-map family: control one hero, protect a core, gain levels, buy equipment,
use active abilities and survive increasingly dangerous waves. It does not copy
Warcraft or League of Legends characters, models, audio or maps.

## Play loop

- Move Elyra, the Dawnwarden, with WASD/arrows or click/tap the ground.
- The hero automatically cleaves nearby enemies. Q casts Dawncleave, E heals
  and rallies, and R unlocks Starfall at level three.
- Spend kill rewards on five equipment options. Four optional tower classes
  each offer two different upgrade paths.
- Defend two incoming lanes through eight waves, including the Crownless King.
- A fallen hero returns after a delay. If the Dawnheart falls, restart and try
  another build. Pause, speed, sound, restart and EN/ZH controls are included.
- Portrait uses a closer tracking camera and touch movement/skill controls.

## Native interface

The HUD uses Godot `PanelContainer`, `HBoxContainer`, `VBoxContainer`,
`GridContainer`, `MarginContainer`, `CenterContainer` and `ScrollContainer`.
Anchors/free placement bound screen regions only; nested Containers own labels,
bars and buttons. A shared Theme supplies panel and semantic button styles.

- Desktop, stacked portrait and compact landscape reflow independently.
- Shop/help content scrolls on short displays; fixed action rows stay reachable.
- Tab/Shift-Tab and arrows navigate the active UI. Enter/Space activate it.
  Escape closes the current overlay, then returns keyboard focus to the
  battlefield, then pauses. Global L/M still change language/sound.
- Keyboard focus is trapped to active modal/shop controls, repaired when a
  purchase disables its button, and restored to a valid initiating control.
  GUI arrow navigation cannot also move the hero.
- The observer reports clipped, effectively visible bounds and actual focus;
  direct signal emission is never labelled a pointer test.

See the canonical [native UI workflow](../../../skills/dcc-showcase-production/references/godot-native-ui.md)
for the existing DCC-MCP capabilities and their limits.

## Current status and acceptance boundaries

This is an unpublished Draft candidate. The native-UI regression suite covers
73 mechanics assertions, 28,051 settled UI assertions across eight sizes
(320×568 through 2560×1080), EN/ZH, ten screen modes, clipped scrolling,
health/respawn labels and focus. The main-scene suite covers 133 integration
assertions, including 157 synthetic events dispatched through Godot's GUI and
pointer holds up to 18 process frames. The 56 shutdown assertions exercise
active, paused and locked-audio states, repeated close requests and actual
AudioStreamPlayback release. Font checks cover all 391 required UI characters
with system font fallback disabled.
Synthetic inputs and automated victory/AFK balance runs are not OS-input,
rendered-pixel, sound or subjective gameplay-quality acceptance.

The [2026-10-19 native UI acceptance record](research/native-ui-acceptance-20261019.md)
binds these results to runtime commit `81c109d`: real DCC-MCP creation/save/reopen,
official Web export, 16 reviewed native-rendered views, 300 ms held native
purchases/mute, keyboard cancel and EN/ZH switching, plus compact-landscape
scrolling, held D-pad release and focus-driven purchase. It retains the remaining
shutdown, browser, listening and physical-touch qualifications.

A prior actual native campaign on commit `523953fb` reached eight-wave victory,
then a natural unattended defeat and clean restarts, with a full recording.
That recording predates this native-UI refactor and does not prove its new
layout/input behavior. The new run covers native UI and early combat, not a
repeat of that full campaign. Refresh the exact-source checks for future
runtime changes; the pinned official Web export remains a separate stage.

On runtime commit `48e0d3b`, [hosted run 39223393872](https://github.com/dcc-mcp/showcase/actions/runs/39223393872)
passed real typed MCP creation/save/reopen, native input, headless checks and
official Web export. Sandboxed runner Chrome 155.0.8059.39 exercised real desktop
and emulated portrait Start/movement, EN/ZH, pause, mute, fullscreen, engine
quit/restart and required-download failure/Retry. Four formerly missing Chinese
glyphs are now bundled, and actual quit releases all tracked audio playbacks
without the previous ObjectDB/resource errors.

The strict Web job still fails on an engine-level WorkerThreadPool Group
allocator error at exit. A separate minimal diagnostic isolates this with the
same template; it cannot waive the game failure. Native rendered tests terminate
the host, so they do not establish manual OS-window-close acceptance. The local
cloud Chromium 154.0.8037.57 still lacks WebGL2; supported hosted Chrome is a
different recorded test environment. Browser security/GPU flags were not changed.
Physical phone/multitouch testing and subjective music listening remain unverified.
Objective PCM, clipping, mute and file-decode checks do not replace listening.
Do not promote a successful export/archive to browser or mobile acceptance.

The PR workflow deliberately produces a short actual native-rendered image gate
before long recordings. A CI artifact or Draft PR is not a Showcase gallery or
Pages deployment. See `ci/CONTRACT.md` for the evidence boundaries.

## Source and reproduction

Open `game/project.godot` in the official Godot 4.6.3 editor. Native scenes,
scripts, selected original and CC0 assets, fonts and audio are contained here.
The original Blender asset recipe and editable scene are in `art/`.

- `gameplay-contract.md`: mechanics, API and exact headless test commands/results
- `research/production-reuse.md`: dated gameplay/art/music sources and selection
- `ART-LICENSES.md`: selected model licenses, original art recipe and hashes
- `game/audio/SOURCE.json`: audio source/derivative hashes and author notices
- `ci/CONTRACT.md`: read-only observer and real-input acceptance boundaries
- `.github/workflows/dawnkeep-preview.yml`: isolated exact-head acceptance

Original art uses real Blender-native script authoring; it is not labelled a
Blender MCP run. Godot scene/script creation is performed through the real typed
DCC-MCP adapter, with raw calls and host readback retained by acceptance.
Generated AI artwork is not used as proof of native rendering.

## Rights

Original gameplay, design, interface, artwork, recipes and scene: copyright
2026 dcc-mcp contributors, all rights reserved. The credited third-party KayKit
and music assets retain their CC0 rights. The renamed Noto-derived font retains
SIL OFL 1.1. Godot/runtime and shared tooling retain their own notices.
See `LICENSES.md` and the asset-local notices. No purchase or new account is
required to reproduce the source. A source download grants no additional
license to original artwork.
