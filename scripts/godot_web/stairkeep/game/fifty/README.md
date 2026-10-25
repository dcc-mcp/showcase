# Stairkeep: ten authored floors connected to the new runtime

Stairkeep / 阶塔 remains a temporary, renameable title. This increment implements
floors 1–10 of the **50-floor target** in the existing Godot project. Floors
11–50 are explicitly unmade. It is a review candidate, not a released game.

Open the existing `../project.godot`, select `view/preview.tscn`, and run that
scene. The original project's default scene still opens the preserved three-floor
slice. The separate export staging recipe changes the entry only in its owned
copy. No existing manual saves are migrated or overwritten.

The new native scene uses the existing licensed isometric world, sprite frames,
icons and textures. It connects real authored maps, deterministic combat,
limited shops, two competing key branches on each floor, a return-visit story
chain, full-state saving, and a revisitable chapter ending. The design and
original Chinese narrative are in [CONTENT-DESIGN.md](CONTENT-DESIGN.md);
the visual direction is in [VISUAL-DIRECTION.md](VISUAL-DIRECTION.md).

[Native evidence](evidence/native-evidence.zip) · [Validation](evidence/validation.json) ·
[Evidence inventory](evidence/manifest.json) · [Source package](review/firstchapter-source.zip) ·
[Web export](review/firstchapter-web.zip) · [Export inventory](review/manifest.json)

## Run and recovery

Choose a mode explicitly; none is selected by default. Classic restarts the
entire tower with a different seed. Practice restores a complete earned chapter
snapshot, including consumed resources, events, purchases and later checkpoints.
The interface explains both losses before replacement. Classic blocks an earlier
manual load after failure in the current open session. It does not add a
permanent death tombstone: reopening the app may resume an older manual save.
The formal default and cross-session policy remain a user design choice.

The seed fixes each floor's D4 transform throughout a run. Whole-grid transforms
map walls, entities, stair destinations and directional events together; they
preserve resource budgets and routes. They change spatial orientation, not the
underlying puzzle into an unrelated random map. Chapter completion never sets
the full campaign's victory flag.

Movement and inspection use the original isometric controls. The native tabs
show combat costs, enemy information and story clues. Ordinary losing battles
are refused; the explicit unsafe challenge requires confirmation. Combat
preview and deduction use the same frozen combat implementation. A finite
lethal challenge records the actual outcome for the recovery panel.

## Measured scope

The root coordinator ran Godot **4.7.2.stable.official.ed1daf0bf**, Compatibility,
GDScript, using isolated data directories and task-owned BelowNormal headless
processes. The accepted source bindings and failures are retained in the evidence
bundle alongside the reproduction instructions.

| Actual check | Result |
| --- | --- |
| D4 geometry and composition | 75 checks passed |
| Runtime, typed content and recovery smoke | 35 checks passed |
| Complete ten-floor routes | 32/32: two modes × eight seeds × two strategies |
| Battle preview versus deduction on those routes | 640 comparisons, zero differences |
| Already-open door repeat | 352 checks, no repeated key charge |
| Sold-out shop / already-rewarded NPC repeat | 144 / 96 checks, state unchanged |
| Complete native F5 save round trip within route matrix | One per mode |
| Real finite combat death and recovery | Both modes, 16 checks passed |
| Save semantics, including 14 re-signed mutations | 26 checks passed |
| Update an existing valid native slot | Five checks passed |
| Positive transformed enter-event adapter | Two seeds, 12 checks passed |
| Imported native scene and direct UI method instrumentation | 26 checks passed; no pixel/input claim |

The route matrix covers **eight distinct layouts**, reused across modes and
strategies. The blade route ends with HP 77 / ATK 57 / DEF 19 / gold 418;
the bulwark route with HP 183 / ATK 45 / DEF 28 / gold 333. These are winning
witness routes, not a guarantee that all strategies or future content are solvable.
The earlier frozen 21-floor experiment and all 1,362 counterexamples remain
unchanged outside this directory.

Source inspection, later-frame container geometry and actual headless scene
instantiation are recorded separately from pixels and input. The current GUI
gate remains `interactive_input_surface_unavailable` / OS error 5; no denied
route is retried. Native visual readability, real keyboard/mouse/touch,
Chinese/Web glyph coverage, mobile layout, browser play and durable IndexedDB
save restoration remain unverified. The Web build deliberately refuses durable
save/load until that path is validated. It has no sound.

## Sources and reproduction

- [Runtime and D4 contract](scripts/RUNTIME.md), [save contract](SAVE.md)
- [Native view controls and limitations](view/README.md)
- [Asset and template sources](REUSE-LICENSES.md), [reuse manifest](reuse_manifest.json)
- [Authored content](data/content.json), [target coverage](data/manifest.json)

The official Godot isometric demo is an MIT component, not a complete tower-game
template. The reused Kenney textures are CC0. New maps, dialogue and game code
are original. ITWonder's channel is an explicitly documented gameplay research
assumption; no original map, dialogue, proprietary art, or unverified channel
values are copied. No new paid service, executable plugin or font was installed.

Rebuild the data without changing it with `python tools/build_content.py --check`.
Run the `.gd` tests from this existing project with an isolated user-data
directory. Tests that take route/death/legacy fixtures require the actual
retained reports; the evidence recipe specifies the order. Import cleared image
resources before scene checks. A producer's assertion result with resource errors
is rejected: both the Godot exit code and stderr must be clean.
