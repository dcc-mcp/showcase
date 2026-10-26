# Relic Courier: ARPG revision brief

Status: gameplay positioning corrected; visual direction pending review. The
previous two concept images remain references, not implemented screenshots.
An earlier A-environment/B-HUD preference is retained as history; it does not
finalize a MU-specific art or gameplay specification after this correction.

## Two games, one owner per game

Relic Courier remains the existing Godot single-player ARPG. Its reference is
MU-like readable casting/projectiles, impact, enemy groups, visible equipped
weapons, loot and character growth. This is not an MMO or a third game. Do not
copy proprietary characters, logos, interface artwork or assets. A separate
Mota project covers exploration/puzzle/progression; its engine/project decisions
belong to that owner. No Unreal migration is authorized here.

## Preserve the working foundation

Keep the original generated actors, Kenney MIT movement adaptation/CC0 audio,
validated save contracts and town/combat/loot/equipment/return course. The
functional patch aligns contacts to animation clocks, adds separate Walk/Run,
imports a licensed independent sword and replaces generic sword drops, exposes
a harmless town skill rehearsal, and preserves saves when starting anew.
Those are regression fixes, not completion of the new ARPG scope.

## Next implementation priorities

1. Skills: define projectile spawn, travel, collision, impact/damage and cleanup
   as one observable lifecycle. Show cast availability, cost, cooldown and
   invalid-target reasons. Current Arc is a short beam; it is not proof that
   projectile combat is implemented. Real input and sound review are required.
2. Groups and growth: design a compact connected combat-zone slice with
   deliberate encounter groups, telegraphs, useful gear drops and a readable
   upgrade/return loop. Do not enlarge empty ground or claim a full MMO economy.
3. Equipment: retain independently imported sword, exact hand socket and
   source/license hashes. Validate rendered grip, attack sweep and occlusion;
   native transform checks alone do not prove attractive holding/weapon hits.
4. HUD: prioritize health/resources, usable skill icons and cooldown/selection,
   equipped weapon and contextual loot. Use one coherent fantasy icon family.
   Old HTML wireframe is rejected history, not a visual target. Native visual
   implementation waits for the corrected art review.
5. Environment: use licensed reusable vegetation/ruins and an encounter layout
   that supports combat readability, camera and occlusion. Two old concepts
   remain art references; distant skyline detail is not a performance promise.

## Reuse selection and budget hypotheses

- Retain Kenney MIT controller adaptation and CC0 RPG audio with provenance.
- Imported cached KayKit CC0 independent sword (300 triangles in native import)
  and Forest tree GLBs use existing legal assets, not new provider generation.
  Source/output hashes and licenses are in game/assets/reused/SOURCE.json and
  game/notices. They still require game-camera visual acceptance.
- Existing KayKit walking/running animation sets are plausible reuse candidates,
  but their rig differs from the 17-joint generated hero. Do not blindly retarget
  or claim a Blender integration while no DCC instance is registered. Current
  separate Run is a declared runtime-authored derivative of the existing Walk.
- Game-icons.net provides CC BY 3.0 icons: select one author/style subset with
  per-icon source, author, modification and attribution. Kenney Game Icons CC0
  fit input/device prompts; do not assume they supply the fantasy skill artwork.
- Godot 4.6.3 Compatibility-native particles are currently used without an addon.
  Evaluate a free VFX library only against renderer compatibility, appearance,
  performance, maintenance and license; do not install unknown scripts casually.
- Starting budgets (unmeasured): <=250k visible triangles, <=128 live particles,
  <=1K textures and <=3MB new static assets. Crowd count/LOD requires measurement.

## Authority and acceptance

Hyper3D budget remains exhausted at15.5 credits. No new paid submission, network
permission bypass, credential acquisition, release or deployment is authorized.
Static generated mesh structure is asset-specific; Bang is paid processing,
not a guarantee that all generated parts are independently detachable.

Existing GUI/input and recording restrictions remain. Real keyboard/mouse,
rendered motion/grip/VFX visibility, listening and natural-speed audio video
are NOT_RUN. Native headless tests and a scripted route do not clear player
quality or balance acceptance. Preserve the failed course and candidate.

## Engine decision and first measurable slice

Choose Godot 4.6.3 for Relic Courier. Its existing project, source/save contracts,
verified matching Windows release template, pinned Web templates and actual
headless/runtime/export receipts are usable now. Unity WebGL modules/license and
Unreal installation/license are not established here; Unreal streaming is not
an interchangeable free static-Web export. Permission to consider engines is
not evidence that missing modules are installed. Preserve the current work;
reconsider only on a measured Godot blocker or a proved higher-quality migration.

First functional slice: separate Walk/Run, animated hand-held weapon, cast
windup/contact/impact with matching sound events, consistent equipment state,
loot/save/new-game preservation and the original town-combat-return route.
Next ARPG slice: actual projectile travel/impact, encounter groups, readable
upgrades and a coherent fantasy HUD. Current beam and two solo encounters are
not described as completed group/projectile combat. A Mota project decision is
outside this game's owner scope.

Gates: exact engine/template/source/artifact hashes; import/script and contact
contracts; continuous scripted controller route; fresh portable-package launch;
then authorized real input, rendered weapon/gait/VFX, complete sound review and
natural-speed audio demo. Keep failed and not-run gates separate. Do not start
shared applications, install unknown addons, retry denied input/recording, pay,
publish or deploy to make a gate look complete.
