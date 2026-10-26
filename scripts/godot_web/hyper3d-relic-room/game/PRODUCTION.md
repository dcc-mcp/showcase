# Relic Courier: production and evidence boundaries

The Sunken Archive is a connected town-to-grove ARPG candidate. A safe arrival
bridge and court lead through a raised rear archive into the warden grove.
Generated characters, a treasure chest and the repaired shrine are its focal
assets. Native architecture, asymmetric masonry, vegetation, warm/moonlight
studies and a following perspective camera form the authored environment.
Character, chest and combat visibility samples were reviewed. The original
runtime freeze `ec13ca4d…` passed a complete real native input course and fresh
normal-process restore. Its PCK `22f7d1c3…` passed the actual 15-action HiDPI Web
smoke for movement, pause, SFX and language controls; the complete Web
course/lifecycle remains blocked before further input by another window
overlapping the browser. Those are historical accepted baseline results. A
later, isolated save-caller correction has its own engine/filesystem evidence;
current real-input follow-up is recorded separately in the case report.

## A small deterministic loop

`scripts/expedition.gd` is a RefCounted rules model. It owns health/mana,
cooldowns, enemy health, deterministic drops, inventory, equipment, progression
and strict versioned save data. It does not own Nodes, Input, physics, clocks,
randomness or filesystem IO. `data/arpg.json` defines town/wilderness, the scout
and sentinel, melee/Arc, focus/weapon slots and the one-time town chest.
IDs and numeric definitions provide the extension seam for zones, encounters,
enemy variants, skills and equipment. New scene placements and animation/contact
contracts still need world integration; this is not an arbitrary-content editor.
Definition changes alter the save fingerprint and require an explicit migration
or new progress rather than silently interpreting incompatible saved data.

`main.gd`, `courier.gd` and `enemy_actor.gd` own scene positions, collision,
animation, telegraphs, input and file IO. Player and enemy motion use
CharacterBody3D physics. Simplified invisible collision shapes are authored
gameplay structures, distinct from the visible generated meshes. Per-instance
display heights are chosen for the scene; unknown provider units are not
treated as calibrated physical dimensions.

An attack schedules one visible windup. Damage is requested only at its authored
contact/release, using current measured distance and line of sight. The core
also rejects invalid state, range, cooldown, locked skill and insufficient mana.
Melee contact is **0.18 s** in a **0.45 s** Attack; Arc releases at **0.32 s** in
a **0.65 s** Cast. Guardian contact is **0.38 s** in a **0.65 s** Attack. These
are authored clip markers, not provider animations. The beam is an authored
instant-release effect; the world caller owns windup and whiff recovery.

Defeated wardens yield guaranteed focus/blade drops. The focus and weapon can
remain equipped together. The chest is another legitimate blade source;
duplicate item pickup consumes that drop without adding another stat bonus.
Completion requires both wardens defeated, the gear equipped and a town return;
it does not require a forced Arc cast or collecting every duplicate drop.

## Generated appearance and authored derivatives

The [asset map](assets/asset-map.json) and
[prop derivative receipt](assets/derivative-provenance.json) distinguish source
outputs from canonical assets. The courier and mechanical guardian originated
from approved original single-view concepts and real Hyper3D MCP submissions.
Each original is a static **30,000-triangle** mesh with three embedded
**2,048 × 2,048** PBR images. Their Blender skeletons, weights and Idle/Walk/Dash
clips were authored later; Attack/Cast additions preserve earlier geometry,
UVs, material/image data and original animation values. The clips use no root
motion. The courier has five clips (Idle/Walk/Dash/Attack/Cast), the guardian
four (Idle/Walk/Dash/Attack). Skin deformation, timing and real input are distinct
checks. The [ARPG asset handoff](../../../../docs/showcase/hyper3d-relic-room/arpg-assets.public.json)
records the measured preservation checks.

The interactive chest keeps the generated exterior, source UVs, PBR channel
bindings and all three embedded image payloads. A separate `Lid` pivot, lining
and underside were authored in Blender. The real Lid rotates about local X
from closed to −100° while Base remains fixed. Opening cancels at the configured
interaction range before the one-time drop commits; pause freezes progress.
Isolated hinge and full real-input/save/reopen checks passed separately. The OS
step-away attempt completed opening before leaving range and did not establish
native cancellation; the engine cancel test passed separately.

The [native diagnosis](../../../../docs/showcase/hyper3d-relic-room/ASSET-DIAGNOSIS.md)
documents a rejected shrine reduction. The immutable **559,968-triangle** source
became a visibly torn **5,000-triangle** derivative. A **60,000-triangle** repair
retains the original **1,024 × 1,024** image pixels and passes the identified
same-camera near-view regression in Blender and Godot. Chest fidelity and the
portal's simpler source design have separate comparisons. These static
derivatives are not a verified LOD ladder.

Base-color textures use sRGB; normal and packed metallic/roughness data use
linear interpretation, with G for roughness and B for metallic. Source-channel
retention does not alone prove visual fidelity. The Shaded arch's emission
image is adapted to lit albedo in the scene; architecture uses authored Godot
noise/triplanar stone materials. The column's UVs and baked stone maps are
authored Blender detail, not Hyper3D textures. Imported material adaptations,
lighting and geometry reduction remain explicit boundaries.

## Persistence and interruption

The core serializes progress IDs, opened chests, defeated enemies, spawned and
picked drops, inventory, equipment, unlocks, XP/level and quest completion. It
strictly validates the data version, definition fingerprint and consistency.
It does not persist positions, pending actions or combat timers. The world
restores the player safely in town and keeps completed rewards consumed.

The caller limits reads to 64 KiB before parsing, checks write/flush errors,
validates the temporary file and rotates a valid primary into a backup before
promotion. The loader tries primary then valid backup, retaining rejected bytes.
Interrupted rename, corrupt/oversized primary and recovery were tested in the
engine. Instrumented QA requires `--qa` and an isolated `user://qa-*.json` name.
A separate actual OS course and new normal process verified chest, gear,
enemy and completed-quest persistence on the original `ec13ca4d…` runtime.
JSON roundtrip alone was not that proof.

The later correction keeps Save & Title on its current screen when writing
fails and displays the existing localized error. Won Explore and lost Retry
validate the latest in-memory save representation before resetting transients,
rather than loading older disk progress. Normal Title Continue still loads
verified disk data. Rebuilding cached drop anchors also preserves an unpicked
chest reward across same-process Title Continue. Only `main.gd` changes among
the 41 runtime files. The focused regression uses an isolated QA save and a
directory at its temporary-file path to cause an actual write failure; 57
checks cover paused/won/lost continuation, EN/ZH feedback, unchanged older
primary bytes, unique gear/rewards and subsequent successful save/continue.
A separate fresh-process read passed five checks; affected native integration,
interface/font/touch checks and changed-script parses passed too. These are
headless engine and actual filesystem results, not new OS/Web pixel acceptance.
Unsaved memory still requires a later successful write before process closure.

Inventory locally suspends the world while the model remains available for
equip. Pause and focus loss suspend contacts, AI, animation and held touch
movement. Retry clears pending actions and transient visuals before rebuilding
current progress. These behaviors require exact-source native tests and actual
input review; original OS acceptance and the later scoped correction checks
remain distinct. Touch-handler
checks are not physical mobile-device acceptance.

## Reuse, cost and remaining gates

The engine baseline is Godot 4.6.3 GL Compatibility with built-in Jolt 3D.
Kenney's MIT Starter Kit controller provides the attributed axis/rotation
movement flow. Relic Sans is a renamed Noto Sans CJK SC subset under SIL OFL
1.1. Six unmodified Kenney RPG Audio effects total **85,740 bytes**, retain CC0,
and have exact source hashes in [AUDIO-SOURCES.json](audio/AUDIO-SOURCES.json).
Source/license verification is complete. Four bounded native audio voices play
lid, confirmed hit, pickup, equip, grounded footstep and swing effects; a native
pause-panel SFX switch mutes the Master bus. The capture preserves engine audio.
Native and Web SFX toggles passed their scoped baseline checks. Signal/mute checks do not
establish subjective listening, which was not run. The 59.033333 s editorial
film preserves the original freeze's complete scripted native GPU/audio course without cuts or
retiming; full decode and sampled first/middle/last pixels passed. Natural-speed
film playback was not run. Scripted capture is separate from real OS input.
Native source notices remain authoritative for redistribution.

The acquisition round completed **23 paid cases for 15.5 credits**, exhausting
its approved cap. The historical API experiment used the direct Python runtime;
the two later hero requests used actual MCP tools/call. The integration's eight
tools cover seven HTTP endpoints, not every Hyper3D website feature or option
combination. There are no further paid calls in the ARPG authoring work.

Use the focused commands in [README.md](README.md). Source rules, staged native
contacts, continuous controller physics, final native pixels/OS input, fresh
save/reopen, Web export/input/lifecycle, audio listening and media playback are
separate gates. The runtime freeze covers 41 files; the source bundles thirteen
GLBs and the scene loads eleven types. Its initial generated instanced-triangle
upper bound is 258,525, including created hidden instances, not a measured
per-frame visible/GPU triangle count. The unused historical closed chest and
block guardian are omitted only from isolated Web staging. The historical
`22f7d1c3…` PCK is 41,192,268 bytes; its case manifest-listed files after notes total
41,226,944 raw and 40,851,259 gzip-equivalent bytes against separate 40 MiB ceilings. Shared
official 4.6.3 runtime bytes are counted separately. No hero texture reduction
was used to meet the old blockout ceiling. ZIP hashes are in the case package
receipts; later source/PCK receipts identify the isolated save correction
separately, without rewriting prior acceptance hashes.
No earlier timed-relic win, placeholder check or scripted exhibit film
certifies this ARPG revision.

Generated models retain applicable Hyper3D terms; authored rigs and game
systems are not provider output. Keep [asset rights](notices/ASSET-RIGHTS.md),
license notices and provenance with the project. Physical touch, gamepads,
portrait, cross-device performance and an independent blank-scene rebuild are
not established here. Model/reasoning attribution is Unknown where unsupported.
