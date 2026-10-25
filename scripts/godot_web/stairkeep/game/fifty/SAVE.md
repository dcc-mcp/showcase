# Fifty runtime save contract

This module belongs to the existing `game/project.godot` project. It uses
`res://fifty/scripts/save.gd` and does not read, migrate or overwrite the original
three-floor or 21-floor slots. The current content is a new 1–10 slice toward a
50-floor target; a floor-10 slice completion is not a completed 50-floor campaign.

## Explicit mode and slot

`FiftySave.write_slot(runtime, slot_id)` and `load_slot(runtime, slot_id)` return
`{ok, status, message, ...}`. Both require an already selected
`classic_restart` or `practice_checkpoint` mode. New runtime content starts with
`mode = "unselected"`; storage never picks a default. A load cannot silently
switch the selected mode. A valid saved run with a different seed in the same
mode can be restored.

`slot_path(slot_id, mode)` maps to
`user://stairkeep-fifty-save-v1/slots/<mode>/<slot_id>.json`. The slot ID is an
explicit lowercase ASCII identifier of 1–32 characters, beginning with a letter
or digit and otherwise allowing letters, digits, `_` and `-`. Windows reserved
device names are refused. There is no default slot, arbitrary-path storage API,
slot enumeration or user-file cleanup operation. The two modes have separate
physical directories.

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
`stairkeep-fifty-state/v1`. Unknown or future envelope fields/versions are
refused. Static runtime identity has exactly `content_id`, `content_sha256`,
`rules_sha256`, `variant_spec` and `snapshot_schema`; it does not bind loading to
the currently active seed.

The runtime owns `export_snapshot`, read-only `validate_snapshot`, atomic
`import_snapshot` and `runtime_identity`. Save passes the entire exported
snapshot through these APIs. It does not reconstruct selected player fields,
reapply pickups, recompute the saved run, merge inventories, or perform its own
restart/checkpoint recovery. Seed/root seed/sequence state, D4 transforms and
layout identity, cleared IDs, keys, shop state, NPC flags, completed events,
cross-floor references, checkpoints, failures, history and actions remain in the
runtime snapshot, including `origin_consumed_loss_ids` as an audit origin.
Candidate-specific content/variant references and every checkpoint are the
runtime validator's authority. Its contract is an isolated deterministic replay
of the accepted action history from the bound seed, mode and variant origin,
followed by exact full-snapshot comparison and resource conservation. Checking
only Base state types or recalculated outer checksums is insufficient.

Classic restart must explicitly create a new seed and reset the complete run in
the runtime. Practice recovery must restore its complete recorded source world
and preserve the runtime's declared audit/history transaction semantics. Saving
either result captures that complete result, rather than implementing another
recovery path. Whole-campaign completion remains false in the 1–10 slice.

## Validate before commit

Load reads only the explicit mode/slot, bounds it to 8 MiB, parses one object,
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
refusals; separate mode paths; same-mode/different-seed roundtrip; full checkpoint,
resource, NPC, cross-floor, failure and history retention; old three/21 format,
foreign slot/content/rules/variant/schema and future-reference rejection;
truncation/empty/oversize/invalid JSON; snapshot/envelope checksum tampering;
re-signed snapshots with invented HP/gold/flags/shop stock/checkpoints or changed
action/history provenance; refusal to overwrite an invalid existing file;
and unchanged runtime/file bytes on every failed load. Native rename/flush
failures must preserve the old slot. Test runs use an isolated task-owned user
directory and exact test slot names without enumerating or deleting user saves.

No engine, native UI or browser execution is recorded by authoring these files.
