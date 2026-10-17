# Rights and source review

- Original game code, generated geometry, level, character, materials, interface and shader: copyright 2026 dcc-mcp contributors, all rights reserved. This prototype is prepared for review in the original Showcase repository.
- `game/sanctuary-font.otf`: a newly generated subset of Noto Sans CJK SC Regular from Debian's Noto CJK package. Source: https://github.com/notofonts/noto-cjk . SIL Open Font License 1.1; full upstream package notice is retained in `game/FONT-LICENSE.txt`. It is not sold by itself. No reserved-name claim is made for the subset.
- Godot editor and Web runtime: MIT and third-party notices. The CI export preserves the repository's existing runtime notices. Runtime code is downloaded only from the pinned official Godot release/template, not committed with the source.
- DCC-MCP authoring and capture reuse: existing source in dcc-mcp/showcase; retain repository notices.

## Bounded reuse investigation, 2026-10-17

Official Godot Platformer 3D was inspected for movement/camera patterns, but no source was copied; the current upstream demo uses Forward+ and is not a drop-in Web presentation.
https://github.com/godotengine/godot-demo-projects/tree/master/3d/platformer

Official Web and renderer capability documentation informed the Compatibility and single-thread choices:
https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_web.html
https://docs.godotengine.org/en/4.6/tutorials/rendering/renderers.html

Kenney Nature Kit (330 assets, CC0) and Poly Haven (CC0) were checked as potential small-asset sources. No assets were downloaded or bundled. The first slice uses authored geometry to maintain a single material palette and keep the source portable; these sources remain candidates if real visual review identifies a concrete shape/material gap.
https://kenney.nl/assets/nature-kit
https://polyhaven.com/license

Do not describe online discovery, a headless launch, or a passing acceptance check as subjective visual or audio approval. No synthetic image is substituted for a game screenshot.
