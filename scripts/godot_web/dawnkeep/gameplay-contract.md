# Dawnkeep gameplay integration contract

Original hero-defense action RPG vertical slice for Godot 4.6.3. The hero protects an original dawn sanctuary, earns XP, purchases permanent equipment, commands optional support towers, and fights eight manually called waves. It is inspired by a historical genre; it does not reproduce a Warcraft map or use its characters/assets.

## Ownership and initialization

`game/gameplay.gd` extends Node. Host creates an instance, adds it to the tree, then calls `setup(world: Node3D, visuals: Node, hud: Control = null)`. Gameplay creates a CharacterBody3D hero (feet at y=0; capsule radius .38, height 1.55, collision layer 2/mask 1) and static tower colliders (radius .77, height 2; layer 1). Visuals are separate nodes; world props can use static collision layer 1. Do not add another hero collider.

Simulation uses its own 1×/2× multiplier and pause flag. Do not set Engine.time_scale or SceneTree.paused from host controls. Host owns camera, screen mapping, audio, language, keyboard events, UI, and pointer routing. `setup` immediately calls restart and emits state.

## Signals

- `state_changed(state: Dictionary)`: complete detached value-only snapshot, at 10 Hz and after commands.
- `game_event(key: String, data: Dictionary)`: localization key and parameters, for banners/audio. No embedded display language.
- `finished(victory: bool)`: terminal victory or core loss.

## Commands

- `select_pad(index: int)`: -1 clears; valid indices 0–11.
- `build_tower(kind: String) -> bool`: selected vacant pad, cost enforced.
- `upgrade_tower(branch: String) -> bool`: commits an existing level-one tower to one of its two level-two branches. No further upgrades.
- `sell_tower() -> bool`: refunds floor(70% of build + upgrade spend).
- `buy_item(item: String) -> bool`: shop available during combat/build, except while dead/paused/terminal. No free or out-of-band balance mutation.
- `start_wave() -> bool`: Space or UI. In build phase starts next wave. During combat requires the previous spawn queue to be empty and at most four surviving enemies; survivors remain and 30 gold is rewarded. No automatic wave progression.
- `cast_skill(skill: String) -> bool`: lowercase q/e/r.
- `set_move_target(position: Vector3)`: left-click ground move, clamped to play area. Uses obstacle feelers and real CharacterBody3D sliding.
- `set_move_input(direction: Vector2)`: host calls continuously from WASD/arrows. x maps world x; y maps world z. Nonzero input cancels pointer target.
- `toggle_pause()`, `set_speed(value: float)` (clamped 1 or 2), `restart()`.
- `snapshot() -> Dictionary`: read-only QA instrumentation. Returned data is detached and JSON serializable. There is no state injection API.

Suggested bindings: WASD/arrows movement, Q cleave, E healing rally, R starfall, Space wave, P/Escape pause. Host should avoid keyboard double dispatch and not route clicks through UI to ground movement.

## World coordinates

All points are (x,y,z), feet/ground y=0. Core=(13,0,5). Hero starts=(-6,0,0), respawns=(10,0,5). Hero bounds x=-16.7..14.7, z=-9.8..10.3.

Lane 0: (-15,0,-7), (-8,0,-7), (-8,0,2), (-2,0,2), (-2,0,-5), (7,0,-5), (7,0,5), (13,0,5).

Lane 1: (-15,0,8), (-11,0,8), (-11,0,2), (-2,0,2), (-2,0,-5), (7,0,-5), (7,0,5), (13,0,5).

Pads 0–11: (-11,0,-4), (-5,0,-7), (-5,0,-1), (-8,0,5), (-3,0,5), (1,0,-2), (2,0,-8), (5,0,-1), (10,0,-3), (10,0,2), (4,0,7), (10,0,8). Lanes and pads are exposed as constants `LANES`/`PADS`.

## Visual adapter

All calls are optional and guarded with `has_method`; missing visual methods do not stop simulation.

- `spawn_enemy(id, kind, position)`
- `update_enemy(id, position, direction, hp_ratio, status)`; status has slow/burn/stun/attacking booleans and boss_phase 1/2.
- `remove_enemy(id, defeated)`
- `spawn_tower(id, kind, position, level, branch)`
- `update_tower(id, level, branch)`
- `remove_tower(id)`
- `update_hero(position, direction, anim)`; anim has moving/attack/hurt/dead/rally booleans, hp_ratio, level.
- `projectile(from, to, kind)`; kinds hero/sunbow/ember/frost/storm/chain. Hits resolve in simulation immediately; visuals may animate travel.
- `effect(kind, position, radius)`
- `select_pad(index, range)`

Effect keys: restart, build, upgrade, purchase, move, cleave, rally, starfall_warning, starfall, boss_warning, boss_slam, boss_enrage, level_up, respawn, hero_death, enemy_death, ember_burst, core_hit, victory, defeat. Warnings should visibly telegraph impact areas. Boss slam follows its warning after one simulation second. Starfall resolves three pulses, .38/.73/1.08 seconds after casting.

## HUD/QA snapshot

Positions are dictionaries `{x,y,z}`. Main may project them and add screen positions/rectangles without mutating gameplay. Root keys include version, phase/mode (`build`, `wave`, `victory`, `defeat`), gold, hp/nexus_hp/core_hp, core_max_hp/max_hp=20, wave, waves/total_waves=8, enemies_left, spawn_remaining, kills, deaths, elapsed, paused, speed, selected_pad, selected, towers, enemies, pads, hero, shop, build_options, skills, cooldowns, cooldown_max, q_cd/e_cd/r_cd, r_unlocked, boss, can_start_wave, early_call, early_bonus, early_calls, wave_preview, last_action.

- `hero`: position, hp, max_hp, level, xp, xp_next, damage, speed, dead, respawn, equipment counts, rally seconds, target position or empty dictionary, moving.
- `skills`: q/e/r entries with key, cooldown, max_cooldown (equipment-adjusted), unlocked.
- `selected`: pad, occupied, upgrades array; when occupied adds kind/level/branch/refund/stats. Upgrade choices contain key/cost/available.
- `towers`: id/kind/level/branch/spent/refund/position/stats.
- `enemies`: id/kind/lane/position/hp/max_hp/progress/slow/attacking/boss_phase. `boss` duplicates live boss entry or is empty.
- `pads`: id/position/occupied.
- `shop`: key/cost/count/max_count/available.
- `build_options`: key/cost/available.
- `wave_preview`: kind/count/lane; lane 2 means alternating portals.

## Balancing and localized names/descriptions

Start 420 gold, core 20, hero 240 HP/32 damage. Autoattacks every .70 sec within 3.2 units; cleave up to three additional nearby enemies at 52% damage. XP threshold is 45 + level × 35, max level 10. Each level adds 28 HP and 6 damage and heals 75. Between waves hero regenerates rapidly; in combat regeneration is 1.6 HP/sec plus plate modifier. Death costs up to 30 gold; respawn delay starts at 8 seconds, grows by one per death to 14. The core remains vulnerable.

Shop localization keys:

- blade: 110 gold, +12 attack, max 3.
- plate: 95 gold, +65 max/current HP, 7% incoming-damage reduction and .6 HP/sec regeneration per rank, max 3.
- focus: 120 gold, +20% spell potency and 8% lower cooldown per rank, max 3.
- boots: 85 gold, +.9 move speed per rank, max 2.
- potion: 45 gold, heal 150; rejected at full health without charge.

Skill keys:

- q: holy AoE radius 4.9, damage 85 + 12 × (level-1), 8-sec cooldown; focus scaling; ignores armor.
- e: heal 75 + 10 × level, 6-sec rally (+55% hero attack rate/+12% movement, nearby support towers +25% attack rate), 16-sec cooldown.
- r: unlock level 3; three holy pulses radius 7, each damage 76 + 8 × level, 30-sec cooldown.

Support towers:

- sunbow: 80 gold, 13 damage/.72 sec/range 5.4; 110-gold upgrade. pierce: 28 damage/range 6.4 and ignores 85% of armor. volley: 16 damage/.58 sec and two extra targets at 72% damage.
- ember: 115 gold, 32 magic damage/2.1 sec/range 5.8/splash 1.7; 145-gold upgrade. inferno: 43 damage, burn and damaging ground. siege: 66 damage/2.5 sec/range 7/splash 2.35.
- frost: 100 gold, 7 magic damage/1.1 sec/range 5, slows to 62%; 125-gold upgrade. deepfreeze: 11 damage/range 5.8, slows to 36%, every fourth shot stuns (.85 sec, bosses .4). shatter: 24 damage/.9 sec and +25% incoming damage vulnerability.
- storm: 145 gold, 18 magic damage/1.5 sec/range 5.4/chains up to 3; 175-gold upgrade. conduit: 26 damage/chains up to 5. tempest: 28 damage/1.05 sec and chained targets briefly stunned.

Enemy keys: scout, skeleton (armor), runner (fast), brute (high HP/leaks 3), wraith (high armor/leaks 2), boss. Boss has 2900 HP, enrages below 50%, telegraphs periodic area slams, leaks all 20 core health. Killing boss alone does not win: all final-wave enemies must be cleared.

Event keys available for localization: ready, invalid_build, hero_on_pad, not_enough_gold, no_tower, invalid_upgrade, invalid_purchase, item_maxed, health_full, cannot_start_wave, wave_not_ready, skill_unavailable, skill_cooling, skill_locked, tower_built, tower_upgraded, tower_sold, item_bought, wave_started, wave_cleared, skill_cast, boss_arrived, boss_enraged, boss_defeated, hero_fallen, hero_respawned, level_up, core_damaged, victory, defeat. A failure return does not deduct currency or trigger gameplay effects.

## Verification boundary

Run `godot --headless --path game --script verify_gameplay.gd` from this directory with writable XDG_DATA_HOME/XDG_CACHE_HOME/XDG_CONFIG_HOME. Tests explicitly alter unit fixture state to exercise terminal paths and mechanics, and test a real physical collision. These checks are not real-input playtesting. Real-input acceptance must operate the actual UI with keyboard/mouse, observe read-only snapshots/captures, and never inject runtime state. Do not turn unit fixture outcomes into a claim that a human completed all waves.


The retained verifier also has reproducible public-command-only balance modes:

- `godot --headless --fixed-fps 60 --path game --script verify_gameplay.gd -- --balance-active`: purchases gear, follows leading enemies, uses skills, and calls completed waves; expected victory. It never directly modifies gameplay state.
- `godot --headless --fixed-fps 60 --path game --script verify_gameplay.gd -- --balance-afk`: only calls completed waves, leaving the unequipped hero stationary; expected core defeat.

These output `DAWNKEEP_BALANCE` JSON with elapsed simulation time, kills, deaths, terminal phase, equipment, and wave/boss event history. The active controller has perfect polling and is a balance/simulation check, not a demonstration of human input or difficulty. Real keyboard/mouse review remains separate.


## Recorded verification, 2026-10-18

Godot 4.6.3.stable.official.7d41c59c4, headless, fixed 60 FPS. The isolated test project contained unchanged copies of the two source files; the same commands below target the delivered game project. This record does not establish rendered visuals, audible music, keyboard/mouse operation, or human difficulty.

- gameplay.gd SHA-256: `669c859a86456215ea64f04150b947ced11b89e9bd1cae5ba00e436e3b85fd12`
- verify_gameplay.gd SHA-256: `76256b4e68899e47edd35c3ba314300267e459c16ba63cce789bb8d240116c8b`

### unit

Command (with writable XDG_DATA_HOME, XDG_CACHE_HOME, XDG_CONFIG_HOME):

`godot --headless --fixed-fps 60 --path game --script verify_gameplay.gd`

Exact machine-readable output:

```text
DAWNKEEP_GAMEPLAY_CHECKS {"checks":[{"name":"initial economy and health","passed":true},{"name":"real colliding hero body","passed":true},{"name":"two lanes and twelve fixed pads","passed":true},{"name":"build requires pad selection","passed":true},{"name":"sunbow build costs 80","passed":true},{"name":"occupied pad rejects duplicate build","passed":true},{"name":"split branch upgrade costs 110","passed":true},{"name":"branch commitment cannot change","passed":true},{"name":"selling returns floor 70 percent","passed":true},{"name":"selling removes simulation tower","passed":true},{"name":"build and upgrade sunbow/pierce","passed":true},{"name":"valid branch stats pierce","passed":true},{"name":"build and upgrade sunbow/volley","passed":true},{"name":"valid branch stats volley","passed":true},{"name":"build and upgrade ember/inferno","passed":true},{"name":"valid branch stats inferno","passed":true},{"name":"build and upgrade ember/siege","passed":true},{"name":"valid branch stats siege","passed":true},{"name":"build and upgrade frost/deepfreeze","passed":true},{"name":"valid branch stats deepfreeze","passed":true},{"name":"build and upgrade frost/shatter","passed":true},{"name":"valid branch stats shatter","passed":true},{"name":"build and upgrade storm/conduit","passed":true},{"name":"valid branch stats conduit","passed":true},{"name":"build and upgrade storm/tempest","passed":true},{"name":"valid branch stats tempest","passed":true},{"name":"blade adds 12 damage","passed":true},{"name":"plate adds max health","passed":true},{"name":"focus purchase succeeds","passed":true},{"name":"full health potion rejected without charge","passed":true},{"name":"potion heals 150 for 45 gold","passed":true},{"name":"Q deals damage and awards kill bounty","passed":true},{"name":"skill cooldown prevents spam","passed":true},{"name":"ultimate requires level three","passed":true},{"name":"experience levels hero and improves attack","passed":true},{"name":"ultimate schedules three impacts","passed":true},{"name":"scheduled impacts resolve","passed":true},{"name":"rally heals and grants finite buff","passed":true},{"name":"snapshot is deep detached and read only","passed":true},{"name":"snapshot is JSON serializable","passed":true},{"name":"first wave queues eleven enemies","passed":true},{"name":"cannot call wave while spawning","passed":true},{"name":"finite spawn queue drains deterministically","passed":true},{"name":"early call unlocks at four surviving enemies","passed":true},{"name":"early call grants 30 while survivors remain","passed":true},{"name":"death costs gold and starts respawn","passed":true},{"name":"dead hero cannot cast or buy","passed":true},{"name":"hero respawns near core with full health","passed":true},{"name":"boss enrages below half health","passed":true},{"name":"boss telegraphs delayed area attack","passed":true},{"name":"boss reaching core is genuine defeat","passed":true},{"name":"all final wave enemies cleared gives victory","passed":true},{"name":"restart clears terminal state","passed":true},{"name":"pause freezes simulation and commands","passed":true},{"name":"two times speed is explicit","passed":true},{"name":"speed clamps to supported values","passed":true},{"name":"hero is physically blocked by tower cylinder","passed":true},{"name":"click movement steers around a solid tower","passed":true},{"name":"building cannot trap hero inside tower","passed":true},{"name":"visual adapter receives gameplay events","passed":true}],"failures":[],"passed":true,"scope":"headless simulation and physical collision fixture; not real-input acceptance"}
```

### active

Command (with writable XDG_DATA_HOME, XDG_CACHE_HOME, XDG_CONFIG_HOME):

`godot --headless --fixed-fps 60 --path game --script verify_gameplay.gd -- --balance-active`

Exact machine-readable output:

```text
DAWNKEEP_BALANCE {"controller":"active","deaths":0,"elapsed":175.150000000032,"equipment":{"blade":3,"boots":2,"focus":3,"plate":3,"potion":0},"events":[{"data":{"gold":45,"wave":1},"key":"wave_cleared","time":13.8333333333336},{"data":{"gold":50,"wave":2},"key":"wave_cleared","time":28.9666666666663},{"data":{"gold":55,"wave":3},"key":"wave_cleared","time":46.8166666666653},{"data":{"gold":60,"wave":4},"key":"wave_cleared","time":70.5499999999973},{"data":{"gold":65,"wave":5},"key":"wave_cleared","time":94.8666666666626},{"data":{"gold":70,"wave":6},"key":"wave_cleared","time":118.649999999995},{"data":{"gold":75,"wave":7},"key":"wave_cleared","time":146.783333333342},{"data":{"id":140},"key":"boss_arrived","time":151.033333333346},{"data":{},"key":"boss_defeated","time":175.150000000032},{"data":{"kills":159,"wave":8},"key":"victory","time":175.150000000032}],"expected":"victory","gold":2271,"hero_level":10,"hp":20,"kills":159,"passed":true,"phase":"victory","scope":"automated public-command simulation; not real-input acceptance","wave":8}
```

### afk

Command (with writable XDG_DATA_HOME, XDG_CACHE_HOME, XDG_CONFIG_HOME):

`godot --headless --fixed-fps 60 --path game --script verify_gameplay.gd -- --balance-afk`

Exact machine-readable output:

```text
DAWNKEEP_BALANCE {"controller":"afk","deaths":3,"elapsed":222.633333333403,"equipment":{"blade":0,"boots":0,"focus":0,"plate":0,"potion":0},"events":[{"data":{"gold":45,"wave":1},"key":"wave_cleared","time":20.7333333333334},{"data":{"gold_lost":30,"respawn":8.0},"key":"hero_fallen","time":40.8666666666656},{"data":{"gold":50,"wave":2},"key":"wave_cleared","time":67.2166666666641},{"data":{"gold":55,"wave":3},"key":"wave_cleared","time":130.066666666662},{"data":{"gold_lost":30,"respawn":9.0},"key":"hero_fallen","time":163.300000000022},{"data":{"gold":60,"wave":4},"key":"wave_cleared","time":194.216666666713},{"data":{"gold_lost":30,"respawn":10.0},"key":"hero_fallen","time":219.1333333334},{"data":{"kills":49,"wave":5},"key":"defeat","time":222.633333333403}],"expected":"defeat","gold":1159,"hero_level":6,"hp":0,"kills":49,"passed":true,"phase":"defeat","scope":"automated public-command simulation; not real-input acceptance","wave":5}
```
