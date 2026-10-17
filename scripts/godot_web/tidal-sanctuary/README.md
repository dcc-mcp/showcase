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

Physical keyboard and emulated touch routes are separate from the explicitly scripted traversal movie. Capture artifacts are unpublished review candidates. A technical pass does not establish visual quality, fun, broad device performance or physical-phone compatibility. The latest actual frames must be inspected before any quality claim. No audio is present.

Headless regressions exercise repeated shore transitions at several physics rates, stationary hysteresis, idle buoyancy, exploration bounds, save sanitization and the complete treasure loop. Native and Web acceptance separately exercise real user input, route continuity, completion and a new process loading its own saved progress.

## Art and source

The sculpted cove, ruins, layout, palm and broad-leaf models, surface variation, water shader, interface and game logic are original. The new explorer uses a credited CC0 KayKit Ranger head/skeleton and Idle/Walk actions with original beach clothing and a Blender-authored swim action. Selected CC0 KayKit bushes/pebbles use the shared matte island palette. Existing Kenney shore rocks and a subtle Poly Haven stone relief remain. Forest growth is clustered around the land cache; open wet sand gives the shore a readable transition. The world is reviewed from the ordinary follow camera, not a substitute fixed-camera composition.

All exact third-party sources, hashes and conversion notices remain bundled. Sanctuary Sans is a renamed subset of Noto CJK under SIL OFL; the subset includes the new treasure and swimming labels. No third-party music, sound or game code was copied. See `LICENSES.md` and `game/FONT-LICENSE.txt`.

The rejected darker experiment remains in history and is not the current visual baseline. No gallery, publishing manifest, merge or deployment is part of this Draft.

## Blender art iteration

The editable palm/understory library and explorer source are under `artwork`. Their scripts use Blender 4.3.2 built-ins and verified static CC0 inputs, with no external plugin or network execution. The source scenes were saved and reopened in independent Blender processes; GLBs are self-contained. This is native Blender production, not a claim of Blender MCP execution. Godot creation/save/reopen continues through the actual DCC-MCP acceptance workflow.

This art candidate keeps the same gameplay camera, controls, water-depth controller, collision terrain, objectives and save protocol. Screenshots must be compared at matching playable views before judging it an improvement.
