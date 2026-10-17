# Tidal Sanctuary

An original small 3D exploration study for Godot 4.6.3 and WebGL 2.

A blue-cloaked traveller arrives on a limestone island. Follow the weathered processional path, wake three tide lanterns, and return their light to an ancient ring. Warm limestone, olive pines, and muted turquoise water share one restrained palette. The game is deliberately compact: this first study establishes the environment, movement and interaction before a larger puzzle is designed.

## Play

- WASD or arrow keys: move in camera space
- E or Space: interact with a nearby lantern or the final ring
- R: restart
- L: English / Simplified Chinese
- H: hide interface for inspection
- Touch: drag the left side to move; tap LIGHT to interact

Progress saves locally. No account, network gameplay, analytics or external assets are loaded by the game. Restart resets this game's local progress.

## Build and review

The isolated `ci` tools use the existing Showcase acceptance pattern: pinned official Godot, actual DCC-MCP author/save/restart/reopen, standalone native input smoke, real Xvfb capture, official single-thread Web export, and Chromium screenshots. Capture artifacts are unpublished review candidates. A scripted traversal is labeled as such and is separate from input verification.

The source has been run in the actual Godot 4.6.3 headless engine. Headless checks do not establish visual quality, browser performance, physical-device behavior, or sound quality. The first visual review must inspect the actual capture before expanding scope.

No audio is present in this initial visual study. The art direction calls for restrained shoreline ambience and distinct interaction sound later, after picture and controls are accepted.

## Source and rights

The game geometry, palette, shader, character, level layout and logic are original for this study. No third-party art, music, sound or game code was copied. The existing Showcase capture architecture is reused within the same repository. See `LICENSES.md` and `game/FONT-LICENSE.txt`.
