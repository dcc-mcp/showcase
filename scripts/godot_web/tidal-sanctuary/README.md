# Tidal Sanctuary

An original compact island treasure hunt for Godot 4.6.3 and WebGL 2. This remains an internal playable prototype under visual review.

Read the mariner's chart on the shore, search the leaning grove for a brass key, swim into the sheltered cove to recover a tide pearl from the red buoy, and bring it back to the ruined sanctuary. The route crosses dry ground, a continuous shallow-water ramp and swimmable sea; the northern sand beach is the return route. There is no breath timer or drowning penalty. Distant currents gently keep the playable area bounded.

## Play

- WASD / arrows: move in camera space, on land or in water
- E / Space: read the chart, open the chest, recover or place the pearl
- R: restart this treasure hunt
- L or EN / ZH: English / Simplified Chinese
- H: hide the interface
- Touch: drag the left side to move or swim; tap the right action button

The character automatically wades and swims according to actual water depth, and walks again on a shallow shore. The objective, clue, distance and movement state stay visible. Swimming has a horizontal body pose, limb strokes and a small surface wake. Treasure interactions open the land chest and light the sanctuary on completion.

Progress is written locally to a version-2 save. On Web, use **Save & return** and wait for its saved confirmation before leaving. Immediately closing the tab can interrupt the browser’s asynchronous save; that abrupt-close case is not guaranteed. The earlier lantern-study save is left untouched. No account, network gameplay, analytics or external assets are loaded by the game. Restart affects only this game's current local progress.

## Build and review

The isolated `ci` tools reuse Showcase's artifact-only acceptance architecture: pinned official Godot, actual typed DCC-MCP script and scene authoring, save, editor restart/reopen, standalone native input, real X11 capture, official single-thread Web export and actual Chromium interaction.

Physical keyboard and emulated touch routes are separate from the explicitly scripted traversal movie. Capture artifacts are unpublished review candidates. A technical pass does not establish visual quality, fun, broad device performance or physical-phone compatibility. The latest actual frames must be inspected before any quality claim. The game now includes an original music loop and four story cues, started by Begin; the native X11 videos remain silent captures. Browser audible-output, mute and loop-continuity acceptance is still required.

Headless regressions exercise repeated shore transitions at several physics rates, stationary hysteresis, idle buoyancy, exploration bounds, save sanitization and the complete treasure loop. Native and Web acceptance separately exercise real user input, route continuity, completion and a new process loading its own saved progress.

## Art and source

The sculpted cove, ruins, layout, palm and broad-leaf models, surface variation, water shader, interface and game logic are original. The new explorer uses a credited CC0 KayKit Ranger head/skeleton and Idle/Walk actions with original beach clothing and a Blender-authored swim action. Selected CC0 KayKit bushes/pebbles use the shared matte island palette. Existing Kenney shore rocks and a subtle Poly Haven stone relief remain. Forest growth is clustered around the land cache; open wet sand gives the shore a readable transition. The world is reviewed from the ordinary follow camera, not a substitute fixed-camera composition.

All exact third-party sources, hashes and conversion notices remain bundled. Sanctuary Sans is a renamed subset of Noto CJK under SIL OFL; the subset includes the new treasure and swimming labels. No third-party music, sound or game code was copied. See `LICENSES.md` and `game/FONT-LICENSE.txt`.

The rejected darker experiment remains in history and is not the current visual baseline. No gallery, publishing manifest, merge or deployment is part of this Draft.

## Blender art iteration

The editable palm/understory library and explorer source under `artwork` preserve the historical Blender 4.3.2 built-in production and independent save/reopen checks. The current `game/assets/tropical/SOURCE.json` records a later Blender 4.5.13 DCC-MCP rebuild, retaining the earlier attribution under `historical_production`. Its eight game GLB hashes identify the actual runtime inputs; the historical `.blend` files do not establish a fresh reopen of that later rebuild. Godot creation/save/reopen continues through the actual DCC-MCP acceptance workflow.

This art candidate keeps the same gameplay camera, controls, water-depth controller, objectives and save protocol; the collision/interaction repair adds semantically selected physical blockers and shared reachability checks. Screenshots must be compared at matching playable views before judging it an improvement.

## Collision and interaction repair candidate

Visible walls, large shoreline rocks, palm trunks, quest pedestals and chest bodies now block movement. Imported solid shapes use transformed visible triangles; palm leaves and soft understory remain nonblocking. Low worn paving is buried into the actual terrain grade; the solid terrain supplies foot support without raised micro-collider seams. World geometry uses collision layer 1 and the player layer 2.

Prompt and action share a single check: less than 1.55 m horizontal reach, at most 1.2 m vertical separation, and unobstructed line of sight. The target's own physical body is allowed; another wall or rock is not. Unreachable targets explain whether to move closer, reach the same level or walk around. Repeated actions still cannot skip stages.

The earlier portrait attempt used a stale moving position and missed the final interaction. The repaired input harness waits for a newer neutral, settled physics observation after the real stop callback, and re-approaches before its single action when necessary. The beacon has a reachable front approach outside its solid base. Exact-head real rendering/input/save validation is still required; local physics fixtures alone do not establish experience quality.

## Retained acceptance checkpoint, 2026-10-27

Commit `3952d4687c44a2be34bc64e99d32f304d3f79b61` passed the full
[CI lane](https://github.com/dcc-mcp/showcase/actions/runs/39507662879).
Its retained artifacts record actual Linux Godot keyboard input, all four quest
stages, native save restoration, and desktop/portrait Chromium input, audio
measurement and fresh-process save restoration. The two native videos fully
decode at 1280 x 720 and 24 fps: 3,977 physical-input frames and 866 scripted
traversal frames. The scripted movie remains separate from input evidence;
native captures are silent.

This review checked those media bytes and the actual native stills. Bright sand
and dense foreground foliage remain visual limitations. PCM measurements do not
establish subjective listening, and emulated touch is not a physical phone test.
Windows DCC-CUA, public-site playback and final gallery acceptance remain unrun.
Integration with current main requires new candidate CI; no collection entry or
public playable is added by this source/prototype merge.
