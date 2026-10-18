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

## Current status

This is an unpublished Draft candidate. Local actual Godot parsing and 60
headless gameplay checks pass. Automated balance controllers establish a
possible full victory and a losing unattended run; these are not real-input
acceptance or a subjective gameplay-quality verdict.

The genuine DCC-MCP author/save/restart/reopen route is implemented with pinned
official adapter/Core dependencies. The actual game source must pass that route
and the early native image/input gate on the exact candidate commit. Desktop
and emulated-touch Web checks, full recordings, video decoding, sound review,
full real-input victory/failure and final independent visual review remain
separate required stages. A running engine or an exported archive does not
establish those stages. Physical-phone testing is not claimed.

The first PR workflow deliberately produces a short actual native-rendered
image gate before long recordings. This is a candidate CI artifact, not a
publication to the Showcase gallery or Pages deployment.

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
