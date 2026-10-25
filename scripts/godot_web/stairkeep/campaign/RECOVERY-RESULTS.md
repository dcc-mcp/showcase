# Paired recovery follow-up: 1,362 historical losses

The original 10,000-run baseline remains **8,638 wins / 1,362 dead ends**.
This follow-up changes no level data, combat rule, reward, price, stock, seed
sequence, purchase-guard budget or original policy. It adds two native QA
replayers, shared verification helpers and a strict independent aggregation
tool. The original three-floor playable candidate is unchanged.

The production target has since changed to **50 floors**. This completed
measurement retains the existing 21-floor regression fixture; it is not the
final content target. See [the proposed transition](FIFTY-FLOOR-TRANSITION.md).
No 50-floor gameplay, authored content or integrated D4 variants are claimed.

## Actual completed outcomes

| Original cohort | Same seed/actions reproduced | Default bad purchase blocked, complete state unchanged | Complete initial checkpoint restored and alternate blade route actually won | Additional chapter-checkpoint winning suffix |
| --- | ---: | ---: | ---: | ---: |
| Early shop attack lock | 1,336 / 1,336 | 1,336 / 1,336 | 1,336 / 1,336 | Not queried |
| Final boss resource deficit | 26 / 26 | Not queried | 26 / 26 | 26 / 26 |

Early queries use the unchanged production defaults, with no budget override.
All 1,336 first queries returned complete `known_losing` proofs and blocked
before spending. A fresh, explicitly confirmed purchase then deliberately
rejoined the original actions and reproduced the same losing terminal state.
Those accepted-risk controls are **still losses**. Complete checkpoint rollback
and a separately selected actual blade route supplied each recovery win.

These are three different branches. Blocking a purchase is not a played win,
and an initial-checkpoint winning route is not a winning suffix from the exact
pre-purchase state. The latter was not tested for all 1,336 cases, so purchase
causality is not inferred from a post-purchase unsatisfiability proof.

The six observed early prefixes are defense-door-open/flask 452,
defense-door-open/ward 394, yellow-key-available/flask 151,
yellow-key-available/ward 139, yellow-key-not-yet-collected/flask 95 and
yellow-key-not-yet-collected/ward 105. Zero yellow keys alone does not prove a
key was spent. No sampled probes are counted toward the 1,362-case coverage.

All 26 late histories now have an actually executed winning suffix from a
complete chapter snapshot: **F19 × 10, F16 × 13, F13 × 3**. These are the nearest
*verified* winning checkpoints among the tested candidates, not a proof of the
nearest possible winning checkpoint. Later unsuccessful attempts remain
unknown or a particular policy's dead end; none proved checkpoint-wide
unsatisfiability. Each case also separately restored its actual initial
checkpoint and executed all 323 blade events to victory.

| Original index | Layout seed | Terminal floor | Verified winning checkpoint floor | Actual victory HP |
| --- | --- | ---: | ---: | ---: |
| 24 | `015b82f9` | 21 | 16 | 7 |
| 169 | `02433a22` | 21 | 19 | 1 |
| 599 | `04f26220` | 1 | 16 | 68 |
| 1289 | `09410782` | 21 | 13 | 7 |
| 1349 | `09a0e95e` | 21 | 19 | 9 |
| 1634 | `0b685a33` | 21 | 16 | 108 |
| 1979 | `0d8face4` | 21 | 19 | 89 |
| 1994 | `0da7a55b` | 21 | 19 | 65 |
| 2279 | `0f6f1630` | 21 | 16 | 1 |
| 2479 | `10aeb1b8` | 21 | 16 | 159 |
| 2739 | `124e2f1c` | 21 | 16 | 91 |
| 3129 | `14bd6b32` | 21 | 19 | 79 |
| 3354 | `1624fa2b` | 21 | 16 | 20 |
| 3379 | `164ced9c` | 21 | 19 | 9 |
| 4554 | `1da29f5b` | 21 | 19 | 10 |
| 5269 | `2219382e` | 21 | 19 | 56 |
| 5704 | `24d05da9` | 21 | 16 | 4 |
| 5854 | `25c0124f` | 21 | 16 | 123 |
| 7609 | `30b4a0b2` | 21 | 19 | 19 |
| 7784 | `31cc48c9` | 21 | 16 | 80 |
| 7899 | `32840f04` | 21 | 13 | 58 |
| 8179 | `3443825c` | 21 | 16 | 21 |
| 8194 | `345b7ad3` | 21 | 13 | 72 |
| 8574 | `36babbef` | 21 | 16 | 75 |
| 8704 | `378a7aa1` | 21 | 16 | 70 |
| 9019 | `3981dc64` | 21 | 19 | 45 |

Index 599 reached the final chapter and returned to floor 1. It remains a late
failure: its original HP 310 versus boss damage 423 requires **114 additional
HP** to survive, because legal victory requires `HP > damage`. Its actual
chapter-16 recovery wins with HP 68. All restored world objects, door/key
consumption, offer stock, resources, checkpoint history and seed/attempt
sequence were checked; rollback does not retain later gains or manufacture
health, refunds or inventory.

## Evidence and reproduction

See the separate [recovery evidence package](evidence/recovery-followup/README.md),
its [completed summary](evidence/recovery-followup/summary.json) and
[26-case table](evidence/recovery-followup/late-case-table.json). Raw line
locators, source/input hashes, actual actions, full snapshots, retained failed
attempts and solver unknowns remain in the package. The prior
`evidence/campaign-evidence.zip` is retained byte-for-byte.

The native run used the recorded Godot 4.7.2 stable `ed1daf0bf` executable,
at most four task-owned BelowNormal headless workers, four late shards
(offset/count 0/7, 7/7, 14/6, 20/6) and four early shards (0/334, 334/334,
668/334, 1002/334, all with `--winning=all`). The native harnesses deliberately
bind the measured original input and raw journal bytes. Public proof auditing
uses the explicitly mapped privacy derivatives; it is not a native rerun of a
changed input. The package README states the original-file requirement for
native reproduction.

The aggregation tool rejects missing/duplicate cases, old harness versions,
changed guard budgets, discontinuous actions, manufactured restore resources,
missing winning events and invalid byte locators. Its 20 positive/negative
self-checks passed before final aggregation. A partial report or exit code zero
alone cannot satisfy the full measurement.

## Player-facing limits

[The Chinese recovery copy and API mapping](RECOVERY-DESIGN.md) explain the
existing options: cancel a blocked purchase; explicitly accept its risk; or
restore a complete recorded checkpoint with subsequent gains and spending
rolled back together. No new economic rescue rule is needed for the verified
cases. Interface recommendation policy and any future refunds or rescue items
remain product decisions, with their tradeoffs recorded separately.

This is backend QA, **not an implemented warning/recovery screen**, a playable
21-floor release, or measured hours of human play. Browser input/reload/IndexedDB
acceptance remains blocked at the prior interactive-input access gate and was
not retried. Web Save v2 persistence remains unimplemented. Repository CI covers
its existing selected cases; it does not turn these headless results into
Stairkeep browser or visual acceptance. No merge or deployment is requested.
