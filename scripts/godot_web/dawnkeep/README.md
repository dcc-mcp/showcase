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

The source at `957c1d3928d4d7382535a5b50ae2990aa4cf5854` passed the
[full native and Web campaign](https://github.com/dcc-mcp/showcase/actions/runs/39285690349)
on 2026-10-19. Native and desktop Web actual input completed eight-wave victory,
a natural AFK defeat and both restarts. Portrait emulated touch completed two
waves, Q/E/R use and pause/confirmation/reset. Headless assertions:78 mechanics,
28,051 UI,135 runtime integration and56 shutdown. Strict actual-game Web error
gates passed, including official engine quit/reopen and required-download Retry.

The supported built-in Jolt backend retains actual collisions and ray queries.
The separate same-template negative controls still reproduce the Group diagnostic
with active GodotPhysics3D or an explicit awaited worker Group. See the
[backend repair and regression scope](research/physics-backend-20261019.md).

The public promotion preserves that verified PCK and all native gameplay bytes,
reuses the existing hash-identical official runtime and adds only a same-origin
page-readiness/reset bridge. See the [public case](../../../docs/showcase/dawnkeep-defense/README.md)
for dated evidence, assets, exact hashes and limitations. The publication gate
checks the integrated bilingual page and real embedded input separately; a
successful local build does not establish the live site's deployment.

Historical failures remain linked in the public evidence. Physical-phone and
multitouch testing, subjective listening, manual native OS-window-close and
physical-GPU performance remain unverified. Native software-renderer capture
framerate is not a claim about a physical device.

## Source and reproduction

Open `game/project.godot` in the official Godot 4.6.3 editor. Native scenes,
scripts, selected original and CC0 assets, fonts and audio are contained here.
The original Blender asset recipe and editable scene are in `art/`.

- `gameplay-contract.md`: mechanics, API and exact headless test commands/results
- `research/production-reuse.md`: dated gameplay/art/music sources and selection
- `game/notices/ART-LICENSES.md`: selected model licenses, original art recipe and hashes
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
See `game/notices/LICENSES.md` and the asset-local notices. No purchase or new account is
required to reproduce the source. A source download grants no additional
license to original artwork.

## Promote the verified candidate

Run `python scripts/godot_web/dawnkeep/promote.py --candidate <extracted-full-run-candidate>` from the Showcase root. It requires the successful native and Web receipts, exact frozen pack hash, all exported file hashes, and matching frozen/current source files. It copies no duplicate engine and adds no browser security setting. The public HTML uses a hash-named pack and content-versioned publication bridge. Run the public-page gate before merge and again against the authorized deployed origin.
