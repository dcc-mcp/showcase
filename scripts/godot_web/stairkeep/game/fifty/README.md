# Stairkeep: authored chapters toward a fifty-floor tower

Current source adds an original **1–20 floor** profile. Run
`view/chapter2.tscn` in the existing `../project.godot`; its explicit content is
`data/chapter2-content.json`. Floors 21–50 remain unmade and F20 is a slice
milestone, not full campaign victory. The default project scene still opens
the old three-floor slice; `view/preview.tscn` selects the ten-floor data.

The second chapter uses scarce keys, two competing reward branches, cross-floor
NPC returns and complete checkpoints at F11/F15. See
[Chapter 2 design and budgets](CHAPTER2-DESIGN.md) and the
[new profile entry](view/CHAPTER2-PROFILE.md). Current runtime saves use the separate
`stairkeep-fifty-chapters-save-v1/{chapter1|chapter2}` directory; they do not
read, migrate or overwrite the frozen first-chapter slots.

The source supports both explicit profiles. Its current rule fingerprint has
changed, so snapshots from the frozen executable are not silently accepted by
this new source. Use the frozen source/Web packages for the original release
identity. The 1–10 packages, original data and evidence below remain unchanged.

Current 1–20 logic measurements cover 32 successful full routes: two modes,
eight seeds and two resource strategies, with eight distinct layouts. The runs
record 44,512 actual actions, 1,280 combat comparisons with no preview/deduction
differences, 576 already-open door checks and 992 stair round trips. Two actual
bad-spend states at F11/F15 have specific yellow-key cut witnesses; restoring
their earned chapter snapshots permits a complete F20 suffix. These witnesses
do not prove every strategy wins. Full-state recovery and save-profile isolation
passed 20 and 24 checks respectively.

[Current logic evidence](chapter2-evidence/native-evidence.zip) ·
[Current validation](chapter2-evidence/validation.json) ·
[Source bindings and projection inventory](chapter2-evidence/manifest.json) ·
[Reproduction and access gate](chapter2-evidence/README.md)

The new dual-profile scene helper is present but **not executed**: starting the
original Godot console for the source-copy asset import was denied by Windows
with error 5 before process creation. No retry or alternate route was attempted.
The 1–20 scene, pixels, real input and browser acceptance remain blocked or
unverified; older first-chapter scene results below do not cover this increment.
The existing downloadable Web ZIP still contains **1–10**, not 1–20.

For a later permitted rerun, use a fresh task-owned user-data directory and a
new absolute output filename. From the existing game project, the bounded route
recipe is:

```text
godot --headless --path . --script res://fifty/tests/chapter2_replay.gd -- --output=<new-absolute-report.json> --mode=practice_checkpoint --seeds=00000001 --routes=keen --offset=0 --count=1 --content-sha256=a02704a4b9a9e871cca23054980e8f9dc45827ee58e8326ed19f5fbbc3953d58
```

This starts normally at F1 and executes the full stable-ID route from
`data/chapter2-budget.json`, using actual navigation and runtime actions. The
retained matrix records the measured pre-fix helper; the optional native-save
helper correction is separately marked unexecuted. This recipe was not retried
after the current process-creation denial.

## Frozen first-chapter review (6b599437)

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
| Save semantics: 13 re-signed cases plus one checksum-corruption case | 26 checks passed |
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
