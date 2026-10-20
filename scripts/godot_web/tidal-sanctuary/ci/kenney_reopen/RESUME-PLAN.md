# Remaining-only independent reopen of four existing saves

Status: frozen offline remaining-only patch for review. No new native execution, commit, push or dispatch. All 36 offline unit tests passed; exact original-artifact admission also passed without modifying any original bytes.

## Historical result remains unchanged

Run 39515704533, head 7de0ffd794a7deefb4cca66ebb62041708a6584b, remains failed. Its official MCP conversion response reported four successful saves; native same-session comparisons finished. The host rejected the scene's own generated header UID. Witness SHA-256 is 38fbc9494c0f60601dbbd03353760d74cb4c998d888f65e9e7d6fbcb6618babf, 413742 bytes. Owned editor and Xvfb exited -15 and 0 after requested termination; caller wait was terminal and cleanup errors were empty. No second session was started.

The original reviewed conversion package and downloaded artifact are untouched. This separate package preserves the old manifest as original-conversion-freeze.json.

## Minimal acceptance change

Permit an optional bounded lowercase-alphanumeric uid="uid://..." attribute in the exact format=4 gd_scene header, after the existing optional load_steps attribute. This declares this scene's identity, not an external resource reference. No other header field or format is added. All URI tokens, external references and unknown property/value expressions remain rejected in the body. The four fixtures are byte-for-byte original saved candidates, not edited or regenerated scenes.

## Fixed artifact admission

original-evidence-pins.json identifies the exact original repository/run/head/artifact and hashes/sizes of 21 required evidence files: actual script-publication requests, convert request/response/outcome record, witness, four candidates, four save receipts, inputs, editor/display logs, caller launch/wait and result records. resume_evidence.py reads and validates these files without rewriting them. It requires:
- Known completed official native request, matching response envelope and reviewed original script contents.
- The precise old header-UID audit failure, with actual owned shutdown and caller wait recorded.
- Successful native save_error=0 receipts for all four original candidate hashes.
- Revalidation of the full original witness using the narrow header fix, preserving exact geometry/material checks and the existing transform-only tolerance.

The original four candidate hashes are pinned in the manifest and in their exact fixture regressions. The old run remains failed even if these previously saved candidates are admitted for the next step.

## Remaining-only execution proposal

After review, a separate hosted kenney_reopen_only job would:
1. Use contents:read and actions:read only; check out the reviewed new diagnostic commit.
2. Download the exact artifact named tidal-kenney-conversion-7de0ffd794a7deefb4cca66ebb62041708a6584b-39515704533-1 from run 39515704533. Never substitute a newer artifact or generic latest run.
3. Verify the resume freeze and all fixed evidence hashes before native startup. Refuse symlink paths and missing/changed evidence.
4. Install the same pinned Godot 4.6.3, adapter 0.9.6 and Core 0.20.42. No source GLB archive download or import is needed.
5. Invoke run_reopen.py with a new output directory and the downloaded artifact root. It launches exactly one fresh owned Python/server/editor/Xvfb session. The native script method is reopen_candidates only. It loads the four existing candidate bytes and pinned original baseline scenes, compares full graphs, and verifies the empty editor remains unchanged. No ResourceSaver/convert request is sent.
6. Preserve new admission receipt, raw official requests/responses, original candidate hashes, native witness, actual shutdown records and result in an always-uploaded artifact.

The header correction does not authorize replaying conversion. Any failure stops and preserves evidence. Visual old/new acceptance and integrated-head CI still precede formal PR #44 asset replacement.

## Patch files

Modified relative to the reviewed conversion bundle: conversion_contract.py (header-only UID), run_conversion_session.py (explicit fixed-artifact reopen admission, no GLB preparation/import for that path). New: resume_evidence.py, original-evidence-pins.json, run_reopen.py, test_resume.py, four exact candidate fixtures, and this plan. The existing converter GDScript is unchanged.
