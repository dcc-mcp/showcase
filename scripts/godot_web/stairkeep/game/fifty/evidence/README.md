# First chapter: native evidence

This bundle records the authored floors 1–10 toward a 50-floor target. Floors 11–50 are not authored. `passed` in `validation.json` describes the bounded native suites and this evidence projection. It does not accept the complete 50-floor campaign, visual quality, real keyboard/mouse/touch play, browser HTTP play, browser persistence, or export. Export receipts are separate.

The parent coordinator executed the original Godot 4.7.2 binary at BelowNormal priority in isolated, task-owned user directories. Current accepted runs have exit 0, empty stderr, unchanged bound sources, and unchanged original game files. These are headless rule tests and direct production UI method instrumentation. No new native process was launched to prepare this archive.

## Actual accepted coverage

| Suite | Scope |
|---|---|
| D4 geometry | 75 checks against an independently generated, previously tested Python geometry oracle; all eight transforms, directions and destination-floor stair endpoints. This does not certify the old Python content schema for this runtime. |
| Runtime smoke | 35 checks: explicit modes, combat boundaries, typed attachments, full world reset/checkpoint behavior, native slots, and current failed Classic import/load refusal. |
| Authored routes | 32 actual cases: two modes × seeds 1–8 × two authored policies; **eight unique layouts**, 3,344 resource events and 19,108 successful API actions. All end with `slice_complete=true`, `core_state.won=false`, `campaign_complete=false`. |
| Route assertions | 640 preview/actual combat comparisons; 352 door revisits with one key charge; 144 finite-stock refusals; 96 exhausted NPC interactions; two full native F5 roundtrips. Each event's real action path is retained. |
| Finite combat death | 16 checks across both modes. A legal low-supply route reaches F3 at HP 111, damage 160 and terminal HP −49. Ordinary/unconfirmed attacks leave state unchanged; explicit death and mode-specific recovery use the same preview. |
| Save semantics | 26 checks and all 14 mutations: HP, gold, flags, stock, checkpoint, actions, history, consumed IDs, recovery count, future reference, foreign identity, future version, mode and checksum. Illegal changes are rejected even after attacker-recomputed checksums; current state and owned disk bytes stay unchanged. |
| Save update | Five checks of actual valid existing-slot replacement and fresh full readback. This is a single-writer test, not a power-loss certification. |
| Direction event | 12 checks over two seeds, using an isolated synthetic standalone enter event: wrong direction does not reward, correct direction rewards once, and replay validates. Production content events remain interaction events. |
| Legacy fixture | A genuine, newly owned old-21 Save v2 file was created and freshly loaded with the old authoritative runtime, then rejected by the new save namespace. No pre-existing user slot was accessed. An old-3 owned slot was also rejected. |
| Final scene | 26 checks after real resource import: settled node layout, resources, no default mode, direct UI actions, failed/completed recovery priority, finite death display, quantities and typed available-event effects. This is not a pixel or real-input acceptance. |

The route collector and this builder independently compare each actual ledger, final resources/flags/events/purchases/cleared sets, unchanged run seed/transforms/layout, and the complete action sequence. Blade ends at HP 77 / ATK 57 / DEF 19 / gold 418; Bulwark ends at HP 183 / ATK 45 / DEF 28 / gold 333. Both have zero yellow and blue keys. These two authored policies do not prove arbitrary strategies or hours of play. Complete checkpoint world restoration retains the documented audit transaction history. Failed Classic blocks old-slot import in the current instance; a fresh explicitly selected instance may resume a manual save. No persistent permadeath guarantee is claimed.

## Historical failures retained

Five historical run reports remain classified separately from the ten current records. The initial Classic assertion wrongly expected empty session audit after restart; the required whole-session journal was preserved. The attached-enter-event test found one real runtime boundary defect. Its second old fixture overlapped an existing object, so that old refusal is not evidence of a second typed guard; the corrected legal fixture is a later green check. The initial scene producer's pass flag was rejected because actual stderr contained 581,254 bytes of missing-import resource errors. A separate scene driver used a wrong Save method name and produced no scene report; the auxiliary assessment records the actual driver failure. The completed-and-failed modal case was red before the recovery-priority fix, then green. Final quantity display checks use the final view revision. Superseded green runs and probes are not additional independent cases.

Historical `.gd` bytes are stored as `.gd.txt.gz`, avoiding duplicate Godot `class_name` registration. Each source has an exact SHA and a provenance label. Some old sources were reconstructed later and matched the measured SHA; that is explicitly different from a contemporaneous capture. Final frozen source copies were made after measurement and are labelled accordingly.

## Evidence and privacy projection

`manifest.json` inside the ZIP uses archive-root member names. It binds every original raw report SHA, projected canonical JSON SHA, compressed member SHA, exact RFC6901 leaf removal/replacement, and immutable proof-root hashes. Original private reports are unchanged and are not distributed. Public owner receipts use a fixed safe whitelist, preserving source and process outcome evidence while omitting host paths/PIDs. Exact test-slot nonce aliases affect metadata only. Seeds, modes, actions, snapshots, world/core state, flags, previews, combat results, and proof hashes are unchanged. Hashes of original slot files still identify the original bytes; metadata aliases do not claim to create equivalent renamed files.

`summary.json` and `validation.json` contain the re-counted cases and bounded scope. Gzip report members can be read with any gzip/JSON tool. `source-history/` contains source bytes, and `auxiliary/` retains the genuine legacy fixture, historical assessments and attributed static reviews. The content author reviewed route records separately from the runtime implementation; the runtime author reviewed the final view separately from its implementation. These notes are attributed static reviews, not native executions by those reviewers.

`tools/build_fifty_qa_evidence.py verify --public-root EXTRACTED --raw-root PRIVATE_OUTPUT` repeats exact raw/public and protected-tree comparisons when the original private output is available. `tools/spec.json` records the private-source relative names and source bindings. Public-only integrity can be checked against the outer delivery manifest and ZIP CRC, then the internal member SHA values. The delivery manifest beside the ZIP adds its SHA/CRC receipt without a circular self-hash.
