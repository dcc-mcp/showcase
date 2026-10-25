# Fifty slice authority

This module runs ten original authored floors inside the existing Godot project.
The manifest records floors 11-50 as not authored. F10 sets slice_complete;
core_state.won and campaign_complete stay false, and revisits remain available.
The default project scene and the original three-/21-floor sources are unchanged.

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
