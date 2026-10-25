# Campaign lifecycle and Save v2

This is an independent rules laboratory for `stairkeep-campaign-21/v1`. The
three-floor project and its Save v1 slot are unchanged. `scripts/base_rules.gd`
is a byte-for-byte frozen copy; the wrapper delegates every ordinary combat
preview and actual resource-changing action to that same implementation.

## API

```gdscript
var campaign = preload("res://scripts/campaign_rules.gd").new()
var opened = campaign.load_campaign("res://data/levels21.json", 20261025)
var preview = campaign.inspect([x, y])
var result = campaign.move(dx, dy) # interact / use_stairs / buy also delegate
var snapshot = campaign.campaign_snapshot() # complete, nested deep copy
var independent = campaign.clone_for_search()
var restored = independent.restore_snapshot(snapshot) # bool; all-or-nothing
```

`state` is a snapshot getter with the original `floor`, `pos`, `hp`, `atk`,
`def`, `gold`, `keys`, `cleared`, `purchases`, `won` names. Modifying it does not
change the game. `data` is shared content whose dictionaries and arrays are
recursively sealed with `make_read_only()` after initial state creation. Search
clones share that immutable tree without copying the full campaign on every
getter access. A clone has independent authoritative resource state,
failure state, history and checkpoint dictionaries.

`CampaignVariant.generate(canonical, seed)` validates the complete content,
normalizes the seed, draws exactly 43 xorshift32 values and returns a separate
transformed data dictionary plus mirror/spawn/hash evidence. The generation
stream never consumes the lifecycle sequence stream. Initialization is a rules
laboratory operation, not a claim that an arbitrary seed has passed its full
winning-witness replay or has been accepted for product use. The solver and
multi-policy receipts must make that separate acceptance explicit.

`restart_same_seed()` restores all initial resources, cleared objects and shop
stock while preserving root/current seed, sequence state and attempt index.
`respawn_new_variant(confirmed, loss_id)` requires an active failure, explicit
confirmation and its exact unconsumed ID. Only this operation advances the
sequence once and increments the attempt once. It resets the entire run at the
new safe first-floor spawn; it never carries old keys or cleared objects into a
new variant. Consumed loss IDs remain recorded and their count must equal the
attempt index when restoring a snapshot.

## Failure semantics

Ordinary `move`/`interact` never execute an unwinnable encounter. Stronger armor
or insufficient HP alone does not declare the expedition lost.

`challenge_enemy(cell, confirmed=false)` is a separate, explicit unsafe action.
A finite lethal preview requires confirmation. Impenetrable armor has no finite
fight outcome and remains blocked. Confirmed lethal combat records
`failure_reason = combat_death` and `terminal_hp = prior_hp - preview.damage`,
using the exact base combat preview. It does **not** fabricate a successful base
fight: the frozen base retains its last legal positive HP, position, gold and
uncleared enemy. Campaign ordinary actions are then frozen. Presentation must
use the terminal metadata when showing death, rather than presenting the base
HP as an alive hero or claiming that the base battle method deducted it.

`assess_failure(max_nodes=0)` uses the shared complete navigation frontier.
Only an exhausted cross-floor BFS with no legal resource-changing action sets
`resource_exhausted`; a node budget returns `unknown`, and an available action
keeps the campaign active. Repeated assessment/presentation keeps the same
failure ID and count. `mark_loss_proven(receipt)` accepts only an exact-version,
exact-state exhaustive `unsatisfiable` receipt from the solver integration.
It checks the receipt binding; it is not an independent proof checker for
untrusted external solver output. Unknown or incomplete receipts cannot mark a
loss. No rescue resources, stock refill or automatic seed changes are added.

Chapter entries 1/4/7/10/13/16/19 capture complete snapshots once per attempt.
`restore_checkpoint(id)` restores the full economy, world, stock, log and
variant. Returning to an earlier entry discards checkpoints from its future
timeline, while retaining failure/consumed-token history to prevent duplicate
counting or sequence advances. A checkpoint is not advertised as a winning
position without a solver/witness result for that exact state.

## Save v2

`save_v2(path=...)` / `load_v2(path=...)` return structured outcomes;
`save_game` / `load_game` are boolean compatibility wrappers. The default
native slot is `user://stairkeep-campaign-v2.json`.

The v2 payload contains the specified content/rules/variant hashes, normalized
root/current/sequence seeds, attempt index, all 21 mirrors, resolved start,
transformed hash, complete state, decision hash chain and complete checkpoints.
Serialized state uses `keys_by_color`, `cleared_object_ids` and
`purchase_counts_by_shop_and_offer`; the internal base retains its original
field names. Checkpoints retain the same complete internal snapshot format.
Story flags are currently the empty reserved dictionary; unsupported nonempty
flags are rejected rather than silently accepted as inactive story logic.

Loading regenerates the variant in an isolated candidate and checks seed
sequence, mirrors, spawn, hashes, integral resource bounds, object/stock IDs,
decision chain, failure evidence and checkpoint history before committing
anything to the active campaign. Combat-death previews are recalculated with
the frozen combat function; resource-exhaustion states are checked with a new
complete navigation BFS. A v1 file, invalid JSON or any mismatching binding is
rejected without modifying either active state or the input file.

Native writes serialize a complete snapshot into a same-directory `.pending`
file, flush and read it back, then commit with `DirAccess.rename_absolute`.
There is no delete-old-slot fallback. A failed pending write or rename reports
failure and preserves the previous final slot. Crash durability against an OS
or device power loss is not claimed.

The rules fingerprint hashes the actual five source files, including the frozen
base and shared navigation. These native laboratory saves require accessible
source bytes. A future stripped export needs a separately verified build
manifest before it may claim the same binding.

The Web persistence backend is deliberately **blocked** in this laboratory.
Neither a virtual-FS write nor `is_userfs_persistent()` alone proves an
asynchronous IndexedDB commit. `save_v2`/`load_v2` report this boundary and do not
display persistent success. No browser was launched or persistence accepted by
these modules; a durable backend and real HTTP close/reopen run remain separate
work.

## Validation

```text
godot --headless --path campaign --script res://tests/test_campaign.gd
```

The test exercises real ordinary rule actions and controlled terminal actions,
golden PRNG outputs, mixed-size reflection targets, safe-spawn rejection,
sequence/idempotency, bounded failure classification, nested snapshots,
tamper rejection, native atomic overwrite, v1/corrupt preservation and
checkpoint recovery. These are instrumented headless checks, not rendered
visual, real keyboard/mouse, browser persistence or human-duration evidence.
