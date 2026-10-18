# Dawnkeep original art recipe

The visual proposition is a readable heroic silhouette in a dark teal forest, warm sandstone paths, and a luminous pale-turquoise shrine. The original architecture uses swept/extruded ribs, bevel-profile rings, an embracing crystal sanctuary, and four distinct functional tower crowns. The flat traversable surface and perimeter collision remain separate from the floating-cliff visual silhouette. Trees are concentrated at the distant/western edges; near-camera plants are deliberately low.

## Reproduce

1. Use Blender 4.3.2 and Godot 4.6.3. Original mesh units are meters, Y-up in glTF/Godot, Z-up in Blender. The authored scene uses seed 18026.
2. Run `blender -b -t 2 --python art/build_dawnkeep.py -- --render` from the case directory. It resets to a blank scene, writes seven original GLBs, saves the editable `art/dawnkeep-original.blend`, records geometry/output hashes in `art/evidence/build.json`, and renders `art/evidence/native-world.png`.
3. Obtain the four official FREE packages listed in `../ART-LICENSES.md`, compare ZIP SHA-256 values, and extract into the layout listed in `download-manifest.json`. Place `prepare_runtime.py` adjacent to those extracted roots and run it with Python 3. It creates `runtime-selected/`; copy `characters/` and `forest/` to `game/assets/kaykit/`. Source images stay unmodified; animations retain the author's official names.
4. Run `blender -b -t 2 --python art/preview_dawnkeep.py` for a native staged composition using the shipped runtime characters and forest. This is explicitly an art-layout render, not a gameplay screenshot.
5. Import/open `game/project.godot` in Godot. `visuals.gd` loads the native GLBs and character animations. Main owns the camera, lighting, environment, UI, and input. Gameplay owns hero and tower bodies; art owns ground, narrow tree-trunk colliders, and cliff perimeter walls. Enemies are nonblocking simulation visuals.

## Bounded reuse discovery, 2026-10-18

- Core production-reuse v1 dependency was checked by the case owner before delegation.
- Installed Blender 4.3.2 includes official glTF I/O, Rigify, Node Wrangler and native mesh/material APIs. Existing native glTF import/export was selected; no extension installation was necessary.
- Godot's official Asset Library lists KayKit Character Adventurers and Skeletons 1.0 as CC0 (https://godotengine.org/asset-library/asset?filter=kaykit). Current author listings provide the newer FREE 2.0/1.1 versions and coherent Forest 1.0. The author's current official downloads were selected over older mirrored packages.
- Official Blender Extensions discovery: A.N.T.Landscape 0.2.0, GPL-2.0-or-later, Blender 4.2+ (https://extensions.blender.org/add-ons/antlandscape/), is a suitable noise-landscape generator but not a fit for the flat playable road/pad topology and deliberately designed architectural silhouette. It was evaluated and not installed. PTerrain 1.0.4 targets real-world progressive terrain and similarly does not address this authored arena. Neither is claimed as installed, tested, or used.
- The smallest bespoke addition is the checked-in native Blender recipe for the original bounded terrace/architecture. No new runtime, provider, paid assets, or software were installed.

## Review and boundaries

Native pixel inspection caught overlapping flagstones at junctions and an overly pale terrain palette in the first pass. The retained revised world uses a single non-overlapping connected road bed, spaced inset stones, a darker teal palette, and thicker cliff strata. The staged composition includes the selected foliage/rigs. Character idle/chop and skeleton walk were separately inspected as real Blender renders. Individual Godot 4.6.3 import/playback validation has zero asset failures. Exact source and selected-file hashes are retained.

`native-world.png` and `native-composition.png` are real native renders and are not final game evidence. They do not prove browser input, performance, audio, camera behavior, mobile layout, or full game completion. The browser image/interaction gate is owned by the case's runtime acceptance path. Native direct scripting is not a Blender MCP coverage claim.
