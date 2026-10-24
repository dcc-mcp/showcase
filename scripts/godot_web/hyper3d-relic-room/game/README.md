# Relic Courier: town, grove, loot and return

Open `project.godot` in **Godot 4.6.3**, let resource imports finish, and run
`scenes/main.tscn`. The project uses GL Compatibility, built-in Jolt 3D physics,
Dummy 2D physics and 60 physics ticks per second. The declared layout boundary
is landscape, 960 × 600 and above. Standalone play needs no API credential,
DCC adapter, debugger autoload or network service.

Start in the safe archive court, pass through the rear gate, and fight the
grove's scout and sentinel. Recover their drops with E, equip the arc focus and
bronze edge in the bag, then return to the turquoise beacon. Equipping the focus
unlocks Arc; using Arc is optional. The town chest has a real hinged lid and a
one-time bronze-edge find. A second legitimate copy clears its loot without
stacking the item or bonus.

| Input | Action |
| --- | --- |
| WASD / arrows | Walk |
| Shift + movement | Run (independent Run animation) |
| Space | Dash |
| F / left click | Melee |
| Q | Arc, after equipping the focus |
| E | Open chest, recover nearby loot or complete the return objective |
| I | Bag and equipment |
| Escape | Pause / resume |

The header switches English/Chinese and exposes optional on-screen controls.
The pause panel switches SFX through the engine Master bus.
Inventory suspends world updates while permitting equipment changes. Pause and
focus loss suspend action contact, AI, animations and held touch movement.
Defeat continuation validates current in-memory progress and returns to safe
ground; completed progress can be explored without respawning collected rewards.

Progress saves after persistent changes to `user://expedition-save.json`. Save data includes chest/enemy/drop
state, inventory, equipment, unlocks and quest progress; transient positions,
combat timers and visual windups are not restored. Invalid data produces a clean
expedition with feedback. Reads are bounded; verified temporary writes and a
valid backup permit recovery of a missing/corrupt primary. Rejected bytes are
retained. A failed Save & Title keeps the current session and reports the error.
Explore after victory and Retry after defeat retain current in-memory gear and
consumed rewards even if a preceding write failed. Keep the session open until
a subsequent save succeeds; closing the process cannot preserve unsaved memory.

The original runtime freeze `ec13ca4d…` passed an actual Windows keyboard/mouse
expedition and a fresh normal-process reopen, with unique gear, opened chest,
defeated enemies and completed quest restored in town. Its PCK `22f7d1c3…`
passed a 15-action HiDPI Web smoke for continue/movement/pause/SFX/language.
These are accepted historical baseline results, separate from the later
save-failure correction and the tests below.
The full Web combat/loot/save-reopen/quit/fullscreen/restart scope is blocked
before further input by another native window overlapping the browser.
The baseline's 59.033333 s film passed full decode and sampled-frame review;
natural-speed playback and subjective listening were not run.
The OS step-away attempt finished opening before leaving range, so native chest
cancellation was not accepted; the engine cancellation test passed separately.

Generated model/PBR data is separate from authored Blender rigs, action clips,
chest interior, Godot architecture, physics, UI and VFX. Read
[production notes](PRODUCTION.md), [asset provenance](assets/derivative-provenance.json),
[rights](notices/ASSET-RIGHTS.md), [audio sources](audio/AUDIO-SOURCES.json) and
[font source](ui/FONT-SOURCE.json).
The source bundles thirteen GLBs, including two unused historical models;
the current scene loads eleven asset types.

## Focused engine checks

After editor imports, run these from this directory using the Godot 4.6.3
console executable in `$godot`:

```powershell
& $godot --headless --path . --script res://tests/test_expedition.gd
& $godot --headless --path . --script res://tests/test_expedition_native.gd -- --qa --save-path=user://qa-expedition-native.json
& $godot --headless --path . --script res://tests/test_enemy_cadence.gd -- --qa --save-path=user://qa-enemy-cadence.json
& $godot --headless --path . --script res://tests/test_expedition_route.gd -- --qa --save-path=user://qa-expedition-route.json
& $godot --headless --path . --script res://tests/test_expedition_course.gd -- --qa --save-path=user://qa-expedition-course.json
& $godot --headless --path . --script res://tests/test_chest_persistence.gd -- --qa --save-path=user://qa-chest-persistence.json
& $godot --headless --path . --script res://tests/test_chest_persistence.gd -- --qa --save-path=user://qa-chest-persistence.json --read
& $godot --headless --path . --script res://tests/test_character_motion.gd -- --qa
& $godot --headless --path . --script res://tests/test_stage.gd -- --qa
& $godot --headless --path . --script res://tests/test_native.gd -- --qa
& $godot --headless --path . --script res://tests/test_layout.gd -- --qa
```

The pure test exercises deterministic combat, invalid distances, cooldowns,
pause, duplicate loot, equipment and strict save-data restore. The staged
native test loads the real scene and checks authored contact timing, drop/equip
integration and file JSON roundtrip. The route test drives continuous controller
motion across connected floors and ramps. The full course uses the controller
and normal action handlers without position writes after spawn. Cadence checks
exercise consecutive contacts, whiff/dash and wall blocking. Chest checks cover
cancel/pause, fixed base/real lid, one-time rewards, interrupted rename,
corrupt/oversized primary recovery and a separate process read. The later
save-failure regression passed 57 staged engine/actual-filesystem checks for
failed Save & Title, won Explore, lost Retry, EN/ZH feedback, preserved gear and
one-time loot, normal successful continuation and cached unpicked chest loot;
the separate process read passed five checks. Native scene integration,
interface/font/touch checks and both changed-script parses also passed on that
correction. UI checks cover
bundled glyphs, settled layout, touch cancel, bilingual controls and SFX mute.
The broader suite passed on the original freeze; only the explicitly listed
affected checks were rerun for the correction. Neither substitutes for OS input.

QA save overrides require `--qa` and the guarded `user://qa-*.json` filename.
Never point these checks at a player's save. `qa_snapshot()` is read-only;
`qa_stage()` and `qa_set_view()` stage state and do not certify real input.
Historical timed-relic media describes the preserved earlier game; it is not
ARPG acceptance. The current suite also includes character motion, UI layout,
enemy cadence, chest persistence and a continuous expedition course; its
instrumented results remain separate from real operating-system input.

After localized game copy changes, regenerate and verify the licensed subset:

```powershell
python tests/subset_font.py SOURCE_FONT.otf
```

The [case report](../../../../docs/showcase/hyper3d-relic-room/README.md)
separates source checks, staged engine checks, continuous physics, real native
input, fresh save/reopen, Web smoke, blocked full Web lifecycle and media review.
Film decode/sampled pixels passed; natural-speed playback/listening remain
untested. The case's `native-package.public.json` identifies each measured source
repackage. The later save correction changes only `scripts/main.gd` among the
41 frozen runtime files; its focused test is bundled separately. Current
real-input follow-up belongs in the case report and is not inferred from the
baseline OS/Web/film results. The clean source archive and exported PCK have
separate receipts. Historical V1 wins and scripted exhibit footage do not
establish the current loop.

## Functional playtest revision

The separate right-hand sword is visible from the start as a practice blade.
Recovering/equipping the bronze edge applies the persistent attack upgrade.
The town supports harmless Q rehearsal with a windup ring and beam; combat Arc
still requires the recovered focus. In the grove, focus equipment unlocks the
real mana-costing skill. Read the skill button's range, cost and failure reason.
Attack sound and contact now follow the imported animation clock. Footfalls
follow Walk/Run contact phases, not an independent velocity timer.
New expedition requires the title confirmation and preserves previous save
bytes in separate before-new archives.

This source revision is a functional candidate. The corrected direction is a Godot single-player ARPG with readable skills,
projectiles, enemy groups, equipment and loot growth. Visual direction remains
pending review; see ../ARPG-REVISION-BRIEF.md.
Real OS input, rendered gait/grip/VFX visibility, listening and natural-speed
audio video remain unverified; headless checks do not clear the failed player
quality gate.
