# Tidal Sanctuary

An original small 3D exploration study for Godot 4.6.3 and WebGL 2.

A blue-cloaked traveller arrives on a rising coastal sanctuary. Follow the weathered processional path, wake three tide lanterns, and return their light to an ancient ring. Cool weathered stone, olive foliage, and muted turquoise water share one restrained palette. The game is deliberately compact: this first study establishes the environment, movement and interaction before a larger puzzle is designed.

## Play

- WASD or arrow keys: move in camera space
- E or Space: interact with a nearby lantern or the final ring
- R: restart
- L: English / Simplified Chinese
- H: hide interface for inspection
- Touch: drag the left side to move; tap the action button to interact or restart
- EN / ZH button: change language without a keyboard

Progress saves locally. No account, network gameplay, analytics or external assets are loaded by the game. Restart resets this game's local progress.

## Build and review

The isolated `ci` tools use the existing Showcase acceptance pattern: pinned official Godot, actual DCC-MCP author/save/restart/reopen, standalone native input smoke, real Xvfb capture, official single-thread Web export, and Chromium screenshots. Capture artifacts are unpublished review candidates. A scripted traversal is labeled as such and is separate from input verification.

The source has been run in the actual Godot 4.6.3 headless engine. Headless checks do not establish visual quality, browser performance, physical-device behavior, or sound quality. The first visual review must inspect the actual capture before expanding scope.

No audio is present in this initial visual study. The art direction calls for restrained shoreline ambience and distinct interaction sound later, after picture and controls are accepted.

## Source and rights

The terrain, ruins, palette, shader, character, level layout and game logic are original for this study. Four compact tree/rock meshes are adapted from Kenney Nature Kit (CC0), with matte palette overrides. The sanctuary entrance additionally uses Poly Haven Rock 04 surfaces and Fern 02 meshes (CC0). No third-party music, sound or game code was copied. The existing Showcase capture architecture is reused within the same repository. See `LICENSES.md` and `game/FONT-LICENSE.txt`.

## Fourth visual pass: sanctuary entrance

This is an internal layout prototype under visual review, not a finished premium game. The current pass narrows detail work to a weathered arch, broken return wall, uneven threshold, grouped fern growth and warmer ring light. Rock 04 and Fern 02 are official Poly Haven CC0 assets; their precise provenance and technical conversions are included. `hero-composition.png` and `hero-wide.png` are actual Godot fixed-camera composition studies captured after the scripted traversal, separate from ordinary camera and physical-input evidence. They do not claim manual gameplay. No additional gameplay or audio is introduced by this pass.
