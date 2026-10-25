# Fifty slice authority

This module supports two explicitly selected authored-content profiles inside
the existing Godot project. The default content path remains
res://fifty/data/content.json, content_id stairkeep-fifty-slice/v1: ten authored
floors, F10 slice completion and floors 11-50 not authored. That unchanged data
keeps its original every-floor entry-checkpoint policy.

The opt-in path res://fifty/data/chapter2-content.json selects
stairkeep-fifty-chapter2/v1: twenty authored floors, with floors 21-50 not
authored and explicit checkpoint_floors [1, 5, 11, 15]. F10's relay_lit flag is a
chapter-one milestone; only the declared F20 goal marks slice_complete.
core_state.won and campaign_complete remain false for either partial profile,
and revisits remain available. Neither profile creates empty higher floors.
The default original project scene, three-/21-floor sources, v1 content file,
existing Source/Web archives and captured evidence remain unchanged.

Load a content path explicitly before choose_mode. profile_info() returns copied
content_id, authored_count, target_count, authored_floors, not_authored_floors,
checkpoint_floors and slice_goal_object_id metadata. The runtime identity uses
the validated canonical content_id/content hash, not a fixed default profile.
Checkpoint capture happens after the real entry action and eligible enter
events, only at the selected profile's whitelisted floors. Restoration keeps
the existing complete-world and future-checkpoint-prefix semantics.

The updated rule sources produce a new rules fingerprint. An unchanged old
snapshot is refused, not silently migrated. Current source code uses the new
profile-separated save root user://stairkeep-fifty-chapters-save-v1 for BOTH
chapter1 and chapter2, never the old user://stairkeep-fifty-save-v1 directory.
The frozen v1 application/archive retains its original code, rules fingerprint
and old save namespace; use that version to resume its old saves. See SAVE.md
for the exact slot mapping. The envelope and snapshot structures did not change.

FiftyRuntime loads content, then requires an explicit choose_mode(mode, seed).
There is no selected default mode and calling choose_mode again cannot reset
an active session. Data is recursively read-only; state/snapshot queries copy.
Ordinary combat previews and execution delegate to res://scripts/rules.gd.
NPCs and one-shot events have typed conditions/effects and exact stable-ID
attachments. Direction-bound enter events cannot be invoked as NPC interactions.

In classic_restart, restart_classic(new_seed, true, loss_id) starts a new
complete world: initial resources, stock, flags, events and checkpoints. An
active voluntary restart requires an empty loss ID; a failed run requires its
current unconsumed failure ID. Cancelled/stale/repeated confirmations do not
advance the run. A failed classic instance rejects import_snapshot; its UI
must also avoid creating a fresh same-mode candidate to bypass that failure.

This is a current-session rule. No persistent death tombstone, slot deletion,
anti-cheat or cross-application-restart rollback prevention is implemented.
Manual slot resume after application restart remains ordinary save recovery.
Whether to adopt a stricter persistent death policy is an open product choice.

In practice_checkpoint, explicit restoration copies the entire captured world:
core resources/position, cleared objects, exact shop stock, flags, completed
events and slice milestone. Later checkpoints are discarded together. The seed,
resolved D4 map and run attempt remain unchanged. The audit action journal,
failure history and consumed loss IDs remain, with a new restoration transaction
and recovery counter. This audit exception is explicit; future rewards or stock
are never merged into the restored world.

Snapshots include the complete accepted action journal from the original seed,
including classic restarts and practice restores. Validation regenerates the
variant in an isolated runtime, executes that journal through the same APIs and
compares the entire snapshot before import can commit. A changed/re-signed HP,
gold, flag, purchase, checkpoint or history is not authorized by a checksum.
validate_snapshot tests candidate legality separately from whether the current
failed classic session permits import_snapshot.

D4 codes use fifty/xorshift32-d4-v1, independent of frozen HV/43-draw saves.
Every authored floor receives one fixed transform for the run; generation uses
one base draw per authored floor plus one final selection draw. Actual encounter
projections deduplicate outcomes and exclude the previous layout when possible.
Projection keys are not semantic/save equivalence proofs and cannot substitute
game state. Entirely symmetric content may have no changed spatial outcome.

Normal unwinnable combat is blocked without damage or death. Only a confirmed
finite lethal unsafe_challenge records a combat loss. Its terminal_hp comes
from the same combat preview; the positive core HP is retained as a valid source
state, not represented as an executed lethal deduction. give_up(true) records
voluntary abandonment and makes no claim of mathematical unsatisfiability.

The QA owner supplies native tests; root alone executes the installed engine.
This document does not certify browser, pixels, interaction, fifty-floor content
or fifty-floor balance acceptance.
