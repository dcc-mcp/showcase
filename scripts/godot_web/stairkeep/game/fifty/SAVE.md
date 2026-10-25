# Fifty runtime save contract

This module belongs to the existing `game/project.godot` project. It uses
`res://fifty/scripts/save.gd`. The current source supports two explicit content
profiles toward a 50-floor target: the original authored 1–10 chapter and the
new authored 1–20 chapter. It does not read, migrate or overwrite the original
three-floor, 21-floor or frozen first-chapter save directories. Neither profile
claims a completed 50-floor campaign.

## Explicit mode and slot

`FiftySave.write_slot(runtime, slot_id)` and `load_slot(runtime, slot_id)` return
`{ok, status, message, ...}`. Both require an already selected
`classic_restart` or `practice_checkpoint` mode. New runtime content starts with
`mode = "unselected"`; storage never picks a default. A load cannot silently
switch the selected mode or content profile. A valid saved run with a different
seed in the same selected mode and matching content/rules identity can be restored.

`slot_path(slot_id, mode, content_id = "stairkeep-fifty-slice/v1")` maps only
these fixed content IDs to fixed directory names:

| Content identity | Directory |
| --- | --- |
| `stairkeep-fifty-slice/v1` | `chapter1` |
| `stairkeep-fifty-chapter2/v1` | `chapter2` |

The new path is
`user://stairkeep-fifty-chapters-save-v1/<chapter>/slots/<mode>/<slot_id>.json`.
The two-argument call remains supported and selects the **new** `chapter1`
namespace. Write/load explicitly use `runtime_identity.content_id`; they never
paste a caller-supplied content ID into a path. Unknown profiles are refused
with `unsupported_content_profile` before any slot I/O; `slot_path` returns an
empty string for an unknown profile.

The frozen v1 application continues to use its original
`user://stairkeep-fifty-save-v1/slots/<mode>/<slot_id>.json` namespace and original
rules hash. This new source never opens, enumerates, migrates, rewrites or cleans
that directory, including when running the original v1 content profile. The
new source has changed rules fingerprints, so snapshots from the frozen app
are explicitly refused by identity validation even if their bytes are supplied
to the pure decoder. Continue those saves with the frozen v1 app; there is no
silent migration or fallback lookup.

The slot ID is an
explicit lowercase ASCII identifier of 1–32 characters, beginning with a letter
or digit and otherwise allowing letters, digits, `_` and `-`. Windows reserved
device names are refused. There is no default slot, arbitrary-path storage API,
slot enumeration or user-file cleanup operation. The two modes have separate
physical directories within each chapter, and the chapters are physically
separate even when mode and slot names are identical.

`encode_slot(runtime, slot_id)` returns the serialized `text` and complete
`payload` without writing. `decode_slot(runtime, slot_id, text)` returns a
validated `snapshot` candidate without importing it. These pure operations are
not a persistence receipt. Native success statuses are `saved_native` and
`loaded_native`. Web read/write returns
`blocked_web_persistence_unvalidated`; durable Web close/reopen acceptance is
not claimed.

## Full snapshot and independent identity

The envelope has exactly `format_id`, `save_version`, `slot_id`, `mode`,
`runtime_identity`, `snapshot`, `snapshot_sha256` and `payload_sha256`.
`format_id` is `stairkeep-fifty-save`, version is `1`, and the state schema is
`stairkeep-fifty-state/v1`. The envelope and snapshot structures are unchanged;
profile separation uses the existing `content_id`, so this change does not bump
`save_version`. Unknown or future envelope fields/versions are still refused.
Static runtime identity has exactly `content_id`, `content_sha256`,
`rules_sha256`, `variant_spec` and `snapshot_schema`; it does not bind loading to
the currently active seed. Bytes from the other chapter are refused by content
identity even if mode, slot and both recomputed checksums are otherwise valid.

The runtime owns `export_snapshot`, read-only `validate_snapshot`, atomic
`import_snapshot` and `runtime_identity`. Save passes the entire exported
snapshot through these APIs. It does not reconstruct selected player fields,
reapply pickups, recompute the saved run, merge inventories, or perform its own
restart/checkpoint recovery. Seed/root seed/sequence state, D4 transforms and
layout identity, cleared IDs, keys, shop state, NPC flags, completed events,
cross-floor references, checkpoints, failures, history and actions remain in the
runtime snapshot. The retained `origin_consumed_loss_ids` field must be empty:
consumed failures are derived from the full session action history rather than
accepted as a supplied historical origin.
Candidate-specific content/variant references and every checkpoint are the
runtime validator's authority. Its contract is an isolated deterministic replay
of the accepted action history from the root seed, selected mode and attempt 0,
followed by exact full-snapshot comparison and resource conservation. Checking
only Base state types or recalculated outer checksums is insufficient.

Classic restart must explicitly create a new seed and reset the complete run in
the runtime. A failed live Classic attempt still refuses slot imports until its
explicit new-seed restart; chapter routing does not bypass that runtime gate.
Practice recovery must restore its complete recorded source world
and preserve the runtime's declared audit/history transaction semantics. Saving
either result captures that complete result, rather than implementing another
recovery path. In the original profile, the existing per-floor entry checkpoints
and floor-10 slice endpoint remain its content behavior. The new chapter-2
profile captures practice checkpoints only at floors **1, 5, 11 and 15**;
floor 10's `relay_lit` is a milestone, and floor 20 is its authored-slice
completion. These are runtime/content rules, not alternate save behavior.
Whole-campaign completion remains false. Stat types and the authoritative
combat calculation are unchanged.

## Validate before commit

Load reads only the explicit chapter/mode/slot, bounds it to 8 MiB, parses one object,
rejects missing/unknown fields, checks format/version/slot/mode/static identity,
and checks both canonical SHA-256 fields. It then asks the runtime to validate
the full detached candidate before its single `import_snapshot` call. The
runtime repeats validation and atomically commits. Every rejected load leaves
the current runtime and the original file unchanged. Load never rewrites a slot.

Write validates the complete current snapshot first. If a target already exists,
that old payload must also pass validation before it is eligible for replacement;
corrupt, legacy, future and foreign files are preserved. New bytes go to a
same-directory `.pending` file, are flushed and read back exactly, then commit
by rename. There is no delete-old-file fallback. A pre-existing pending file is
preserved and blocks another writer. After an error, only the exact pending file
created by that call can be removed. This is a single-writer-per-slot contract;
cross-process concurrency and power-loss durability are not certified.

Canonical JSON sorts keys, normalizes finite integral floats to exact integers,
and rejects non-JSON values, excessive nesting and integers outside the exact
JSON range. Large seed/sequence identities must use lossless string encodings.
Both checksums are integrity checks, not authenticated anti-cheat signatures: a
user who can rewrite a fully valid state and recompute checksums is not prevented
by a local checksum. Re-signed invalid states still have to fail runtime validation.

## QA handoff

The unified `fifty/tests` owner supplies actual native QA; this document is not a
test receipt. Required cases include explicit unselected/invalid mode and slot
refusals; separate chapter/mode paths; same-profile/same-mode/different-seed
roundtrip; cross-profile byte rejection and unknown-profile refusal; proof that
new code performs no I/O in the frozen v1 directory; full checkpoint,
resource, NPC, cross-floor, failure and history retention; old three/21 format,
foreign slot/content/rules/variant/schema and future-reference rejection;
truncation/empty/oversize/invalid JSON; snapshot/envelope checksum tampering;
re-signed snapshots with invented HP/gold/flags/shop stock/checkpoints or changed
action/history provenance; refusal to overwrite an invalid existing file;
and unchanged runtime/file bytes on every failed load. Native rename/flush
failures must preserve the old slot. Test runs use an isolated task-owned user
directory and exact test slot names without enumerating or deleting user saves.

No engine, native UI or browser execution is recorded by authoring these files.
