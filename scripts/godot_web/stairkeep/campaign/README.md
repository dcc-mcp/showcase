# Stairkeep: a 21-floor rules laboratory with reproducible losing runs

**阶塔 / Stairkeep is a temporary name and can be changed.** This independent
Godot project contains campaign data, rules and headless evidence. The original
three-floor playable candidate remains unchanged. This laboratory is not a
21-floor playable release, a rendered visual review or measured hours of play.

The completed baseline covers indices **0–9999**, five policies with **2,000
runs each**, **10,000 distinct layouts** and **9,823 distinct decision sequences**.
It recorded **8,638 wins and 1,362 dead ends**, with **558,596 combat-preview versus
actual-HP comparisons and zero mismatches**. Every losing run was independently
reproduced and continuously replayed to its full terminal state, with complete
navigation evidence and a separate initial-layout isomorphism certificate.

| Policy | Runs | Won | Dead end |
| --- | ---: | ---: | ---: |
| Resource | 2,000 | 2,000 | 0 |
| Attack | 2,000 | 2,000 | 0 |
| Defense | 2,000 | 2,000 | 0 |
| Cautious | 2,000 | 2,000 | 0 |
| Uncorrected randomized | 2,000 | 638 | 1,362 |

The four scored policies explicitly prioritize an affordable attack upgrade
when a currently observed armor gate cannot be penetrated. They consult no
authored winning route or unreachable future monster. Randomized play has no
gate correction, route repair or hidden resource grant. These results do not
mean arbitrary policies win or that the campaign has passed balance review.

## What the evidence separates

Of the losing continuations, **1,337 stop on floor 1 and 25 on floor 21**. All
1,362 retain their original seed, policy seed, decision signature, complete
executable path and terminal state. A complete global navigation BFS proves no
legal resource-changing action remains in each terminal state. Walking, shops
and stairs are included; checkpoint recovery and starting a new attempt are
outside that continuation query.

Final position is not failure stage: index 599, layout seed `04f26220`, reached
the final chapter and returned to floor 1 for an old-shop ward purchase. Its
terminal global frontier still contains the final boss. The actual stage
classification is **1,336 early first-shop attack locks and 26 final-boss
resource failures**. The early subset contains 638 ward-first and 698
flask-first purchases. See [failure classification](FAILURE-CLASSIFICATION.md);
the four-prefix purchase-guard experiment is not a verified repair of all 26
late continuations.

This is different from an unwinnable initial layout. Four canonical routes
(`blade`, `bulwark`, `balanced`, `frugal`) actually won through the frozen rules.
The independent Python audit checks the coordinate/attribute bijection for all
10,000 observed layouts: 210,000 floor transforms, 4,100,000 object instances and
400,000 stair links. An empty, resource-neutral prefix connects every selected
spawn to the reflected canonical start. Transporting a canonical winning path
therefore supplies a conditional existence proof for each observed initial
layout. This is not a new full engine replay of every winning route, enumeration
of all uint32 seeds or proof that every reached state stays winnable.

Sixteen additional complete routes ran through `CampaignRules` and actual
navigation on four seed inputs, with **32 native Save v2 save/load/continue
round trips**, 24,160 actions, 4,828 checked events and 916 preview comparisons.
The four route budgets, exact cleared IDs, shop stock and complete snapshots
matched. The lifecycle suite separately passed **88 checks**. The 10,000 policy
runs use the frozen base economy; they do not contain 10,000 death/respawn or
browser-storage tests.

The old three-floor simulation's 20 resource-exhaustion counterexamples are
retained separately. Their policy seeds do not generate maps. Each was replayed
to its original dead end and also has a real winning initial-state witness.

## Completed paired recovery follow-up

The production target is now **50 floors**. This 21-floor laboratory and its
10,000-run baseline remain historical regression fixtures; they are not the
final content target. The [transition proposal](FIFTY-FLOOR-TRANSITION.md)
records the module and reversible-grid work still needed. It does not claim
50 authored floors, copied original maps/dialogue or integrated D4 variants.

The [follow-up](RECOVERY-RESULTS.md) individually replays all **1,336 early**
and **26 late** original failures. All early bad purchases are blocked by
default without changing the complete state; explicit risk acceptance still
reproduces the original losses. Every case separately restores its complete
initial checkpoint and actually wins through a selected blade route. All 26
late cases additionally have an actual chapter-checkpoint winning suffix
(F19 × 10, F16 × 13, F13 × 3). The original baseline and difficulty remain
unchanged. This does not prove every strategy wins, that a blocked prestate
was winnable, or that the tested checkpoint is the latest possible winning
checkpoint. No warning/recovery interface has been accepted.

## A verified mitigation, with its scope

The first shop permits an irreversible mistake: buying ward or flask before
the necessary attack upgrade can destroy every ordinary winning continuation.
Four real prefixes were exhaustively checked, including both retained and
spent yellow-key choices. This remains visible in the unguarded baseline.

The optional [purchase guard](PURCHASE-GUARD.md) analyzes an isolated actual
purchase. It blocks a conclusively losing purchase by default, permits explicit
acceptance of that risk, and labels a bounded unanswered query **unknown**.
Its proof concerns the post-purchase state; an already unwinnable input does
not make that purchase the original cause of failure.
Opaque one-use tickets bind the full state and exact sources. It adds no coins,
health, keys, shop stock or automatic seed changes. Query limits are cooperative,
not process preemption or an accepted interface-latency budget.

Its full engine suite passed **75 checks**. All four bad purchases were blocked;
explicitly accepting them still produced actual unsatisfiable states. One
accepted loss was restored through the complete chapter-entry checkpoint, then
the actual corrected blade route won on floor 21 with HP 138, attack 153,
defense 47 and gold 946. A real floor-19 flask also received a verified winning
suffix preview. This four-prefix experiment is not a claim that every late
losing route or every arbitrary policy is protected. The 21-floor interface
has not been connected to the guard.

## Fixed content and controlled variants

The canonical data contains 21 fixed 13×13 floors, 410 objects, 68 monsters,
49 doors, seven shops and 40 directed stair links. There are 21 coordinate
layouts and eight unlabelled room-tree shapes. Runtime generation reflects
whole floors horizontally/vertically and chooses one of four connected empty
starting cells; it does not redistribute enemies or invent random loot.

`CampaignVariant` draws exactly 43 xorshift32 values per layout. A separate
policy RNG drives exploration. For master layout seed 20261025 (`013528a1`):

```text
layout_seed = (20261025 + absolute_index * 104729) uint32
master_policy_seed = a424c112
policy_seed = master_policy_seed XOR layout_seed XOR ((absolute_index+1)*2654435761 uint32)
zero state is normalized to 6d2b79f5
```

The [lifecycle API](LIFECYCLE-API.md) advances the attempt sequence exactly once
after a unique confirmed loss. Restarting the same seed preserves the sequence.
Checkpoints restore the complete economy, cleared objects and stock; they are
not advertised as winning positions without a witness for that exact state.
Explicit lethal challenges use the same combat preview to record terminal HP
in campaign failure metadata; the frozen base remains a legal recovery
snapshot. Presentation must use that failure metadata. Native Save v2 is
strictly versioned and atomic. Web Save v2 persistence is not implemented.

## Reproduce with the recorded toolchain

The measured engine is **Godot 4.7.2 stable, official ed1daf0bf**. The project
is configured for GDScript and Compatibility; these runs are headless.
Python helpers use only the standard library. Use an
isolated native user-data directory for these tests. The original three-floor
Save v1 slot and its Web export are separate.

From this project directory, with the authorized local Godot executable:

```text
python tools/build_campaign.py --check
godot --headless --path . --script res://tests/test_campaign.gd
godot --headless --path . --script res://tests/replay_witnesses.gd -- --output=<new-canonical-report.json>
godot --headless --path . --script res://tests/replay_variant_routes.gd -- --output=<new-variant-report.json>
godot --headless --path . --script res://tests/test_purchase_guard.gd -- --output=<new-guard-report.json>
godot --headless --path . --script res://tests/simulate_campaign.gd -- --runs=2500 --start-index=0 --seed=20261025 --stop-file=<owned-stop-marker> --output=<new-shard-0.json>
```

Repeat the last command with start indices 2500, 5000 and 7500. Serial execution
has the same logical results. The recorded batch used at most four BelowNormal,
task-owned headless workers; other engine verification waited for an owned slot.
A stop marker produces a partial report at a case boundary: exit 0 alone does
not mean all requested runs completed.

`tools/aggregate_campaign_shards.py --help` describes strict coverage, journal
and source verification. Initial aggregation creates the exact failure queue;
`tests/replay_campaign_failures.gd` replays its original indices with optional
`--offset`/`--count`. Final aggregation requires all replay files, their exact
`--replay-input`, and the bound replayer script. Missing or duplicated indices,
incomplete frontiers and changed sources fail verification. See
[search evidence](SEARCH-EVIDENCE.md), [variant replay](VARIANT-REPLAY.md) and
[bijection certificates](VARIANT-BIJECTION-CERTIFICATE.md).

`tools/classify_campaign_failure_modes.py --help` reproduces the stage
classification from a new original, hash-bound measurement/replay set, using
recorded authoritative previews rather than another combat formula. Its
recorded source SHA-256 is
`22cc92db2fcf99145150630f4d873bade1ca86d06dc98831353b9ce956d544d6`.
The public privacy derivative has separate path/hash mappings; it is not
presented as the byte-identical private input of that original analysis.

## Review artifacts and boundaries

[Complete evidence ZIP](evidence/campaign-evidence.zip) ·
[Manifest](evidence/manifest.json) · [Checks](evidence/CHECKS.json) ·
[Public/raw provenance](evidence/PORTABILITY.json) ·
[Canonical wins](evidence/canonical-witnesses.json.gz) ·
[Variant and native saves](evidence/variant-witness-16.json.gz) ·
[Purchase guard](evidence/purchase-guard.json.gz) ·
[Lifecycle](evidence/lifecycle.json.gz) ·
[Old 20 counterexamples](evidence/slice-failure-classification.json.gz)

The public evidence is an explicitly labelled derivative. Header process IDs
are removed with byte-length-preserving padding; subsequent records, seeds,
decisions, resources and failure outcomes are retained. Locators and delivered
hashes are checked again. Private originals remain unchanged. The complete ZIP
uses standard ZIP LZMA compression; Python's `-m zipfile -e` can extract it.

The canonical data SHA-256 is
`b11c41ed50566f0fcfc7c50f59641c987d29b249435ff08487ab17fd580550d1`.
`scripts/base_rules.gd` is byte-identical to the delivered three-floor core
(`e89070d800c3a7769c4440b6eec8ed4702afaa45ef0055e78c67959b310c0495`).
No legacy Mota levels, new third-party code or assets were introduced here.
Repository MIT terms apply to this new code/data; the existing official Godot
MIT and Kenney CC0 notices remain scoped to their original components.

Actual browser input, HTTP-served play, reload/IndexedDB persistence, rendered
21-floor visuals, audio, mobile devices and human duration remain unaccepted.
The previous DCC-CUA input-surface access denial was not retried. No merge,
deployment, shared runtime/registry modification or shared Host operation occurred.
