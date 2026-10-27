# Rights and source review

- Original game code, generated terrain/ruins geometry, level, character, material definitions, interface and shader (excluding explicitly credited third-party assets): copyright 2026 dcc-mcp contributors, all rights reserved. This prototype is prepared for review in the original Showcase repository.
- `game/sanctuary-font.otf`: a newly generated subset of Noto Sans CJK SC Regular from Debian's Noto CJK package. Source: https://github.com/notofonts/noto-cjk . SIL Open Font License 1.1; full upstream package notice is retained in `game/FONT-LICENSE.txt`. It is not sold by itself. No reserved-name claim is made for the subset.
- `game/assets/*.tscn`: four meshes derived from Kenney Nature Kit 2.1 (CC0 1.0 Universal), imported and normalized with Godot, with new matte material overrides. Original source names/hashes and the official archive URL are recorded in `game/assets/SOURCE.json`; bundled upstream notice is `game/assets/KENNEY-LICENSE.txt`. No textures, scripts, animations or external dependencies are included.
- Godot editor and Web runtime: MIT and third-party notices. The CI export preserves the repository's existing runtime notices. Runtime code is downloaded only from the pinned official Godot release/template, not committed with the source.
- DCC-MCP authoring and capture reuse: existing source in dcc-mcp/showcase; retain repository notices.

## Bounded reuse investigation, 2026-10-17

Official Godot Platformer 3D was inspected for movement/camera patterns, but no source was copied; the current upstream demo uses Forward+ and is not a drop-in Web presentation.
https://github.com/godotengine/godot-demo-projects/tree/master/3d/platformer

Official Web and renderer capability documentation informed the Compatibility and single-thread choices:
https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
https://docs.godotengine.org/en/4.6/tutorials/rendering/renderers.html

Kenney Nature Kit (330 assets, CC0) and Poly Haven (CC0) were checked as potential small-asset sources. Following actual visual review, four tiny Kenney meshes were selected and bundled as self-contained Godot scenes: two shore rocks, one irregular branching tree, and one narrow pine. Their default metallic materials were replaced with the same matte island palette. The initial passes did not bundle Poly Haven; the fourth hero pass now includes the specifically credited surfaces and ferns below.
https://kenney.nl/assets/nature-kit
https://polyhaven.com/license

Do not describe online discovery, a headless launch, or a passing acceptance check as subjective visual or audio approval. No synthetic image is substituted for a game screenshot.

## Poly Haven surfaces and ferns (hero composition pass)

Rock 04 by Rob Tuytel and Fern 02 by Rico Cilliers/Rob Tuytel are official CC0 assets. Exact URLs, original MD5/SHA256, byte sizes and derived-file hashes are recorded in `game/assets/POLYHAVEN-SOURCE.json`; the notice is `game/assets/POLYHAVEN-LICENSE.txt`. The bounded official static download totals 4,590,433 bytes. Four fern meshes are converted with Godot GLTFDocument; the missing glTF alpha channel is restored from the separately verified official alpha map. Reduced texture resolutions and original materials are documented there. No third-party scripts execute. These assets retain CC0, independently of this original scene’s creative rights.

## Treasure and swimming iteration

The initial compact treasure route, walk/wade/swim controller, primitive swimming animation, cove shape, water shader and generated surface variation are original. Its first gameplay iteration reused existing CC0 assets. The subsequent Blender art iteration adds the specifically credited assets below. The Noto CJK subset was regenerated from the same installed upstream font to cover the new English/Chinese interface while retaining the renamed Sanctuary Sans family and full OFL notice.

The implementation consulted official Godot CharacterBody3D and Button documentation for floor snapping, slope behavior and multitouch limitations; no third-party implementation was copied:
https://docs.godotengine.org/en/4.6/classes/class_characterbody3d.html
https://docs.godotengine.org/en/4.6/classes/class_button.html

## Blender tropical art iteration

The original palm variants and broad-leaf understory geometry, editable Blender sources, coral explorer clothing/hat/sandals and keyed swim action retain this case's original creative rights. The explorer's head, skeleton and normalized Idle_A/Walking_A actions derive from Kay Lousberg's KayKit Adventurers 2.0 FREE (CC0). Selected Bush_3_A_Color1 and Rock_3_A_Color1/Rock_2_C_Color1 geometry derives from KayKit Forest Nature Pack 1.0 FREE (CC0), with new shared matte materials. Existing upstream content remains CC0 even when bundled in a modified asset; the original-rights statement does not revoke those rights.

Official source pages: https://kaylousberg.itch.io/kaykit-forest and https://kaylousberg.itch.io/kaykit-adventurers . The two selected official static archives total 19,459,975 bytes; exact archive/source/export hashes and conversion details are in `game/assets/tropical/SOURCE.json`. Original notices are in `FOREST-LICENSE.txt` and `ADVENTURERS-LICENSE.txt` beside it. No paid source package, third-party script, addon or sound is included.

Historical Blender 4.3.2 native save/reopen evidence and reusable asset scripts remain under `artwork`; these were native operations without Blender MCP. The current `game/assets/tropical/SOURCE.json` separately records the later Blender 4.5.13 DCC-MCP rebuild and eight runtime GLB hashes while retaining the original source attribution under `historical_production`. These stages do not replace each other's native-scene evidence. Game authoring remains Godot DCC-MCP. Shared acceptance tooling continues under the repository MIT license.
