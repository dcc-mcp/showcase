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
