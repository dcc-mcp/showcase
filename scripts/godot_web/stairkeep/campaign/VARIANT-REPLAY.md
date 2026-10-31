# Complete variant witnesses and native Save v2

The new `tests/replay_variant_routes.gd` connects the canonical authored budgets
to the campaign wrapper, mirrored world, actual navigation actions and actual
native-file restoration. It does not change any of the five frozen rule sources.
The parent task must run it with its authorized existing Godot executable; this
document is not a test receipt.

## Current executed result

The default sixteen-run matrix was actually executed headlessly on 2026-10-25
and passed: **4,828 authored events, 24,160 real actions, 916 preview/deduction
comparisons and 32 complete native Save v2 round trips**. Automated execution
took **175,606 ms**; that is a test runtime, not a human campaign-duration result.
The tested script SHA-256 is
`95a3dea57d56522397e2fdca2dc5557823b027cfef3f8ba27ad7a2995f49b4b4`.
The full bound run report is archived at
[evidence/variant-witness-16.json.gz](evidence/variant-witness-16.json.gz).
This result covers the four named routes on the four stated seed inputs only.
It does not accept browser behavior, arbitrary seeds or hours of human play.

From the campaign project, use an isolated native user-data directory:

```text
godot --headless --path . --script res://tests/replay_variant_routes.gd -- --seeds=1 --routes=blade,bulwark --output=user://variant-two.json
godot --headless --path . --script res://tests/replay_variant_routes.gd -- --output=user://variant-sixteen.json
```

The first command is a two-complete-route benchmark. The default matrix is the
four authored routes (`blade`, `bulwark`, `balanced`, `frugal`) on seed inputs
`0`, `1`, `20261025` and `0xffffffff`: sixteen complete expeditions. Zero is
displayed and bound as its specified normalized seed `6d2b79f5`.
`--seeds=` accepts comma-separated decimal values, `0x` hexadecimal or
`hex:` followed by an eight-character normalized seed. Bare all-digit input is
always decimal, so a copied saved seed such as `00042021` must use
`0x00042021` or `hex:00042021`. Each native-save receipt supplies an unambiguous
`replay_seed_argument`. `--routes=` selects exact route names.

For each event the harness finds the exact stable-ID resource/shop option in
the shared Navigation frontier. Stair approaches are reconstructed from that
same frontier's resource-neutral directed edges. Every path is executed by
`CampaignNavigation.execute`, which calls real campaign
`move`/`use_stairs`/`buy` methods and checks authoritative combat previews
against actual HP deductions. A local floor horizon is a speed hint only:
missing local paths fall back to the global frontier before being rejected.
No game-state setter or second combat formula is used.

Every authored event checks HP, attack, defense, gold and every key color.
The harness independently accumulates the exact cleared/picked/opened ID set
and per-shop/offer purchase counts from the executed event sequence, and
compares both to the authoritative state after every event. Seed, sequence,
attempt, content/rules hashes, mirror table and resolved start must remain
unchanged during ordinary play. Stair landings must equal the transformed
destination. The final event must reach victory with the authored full budget.

Every run saves after first reaching the second chapter (floor 4 or later),
creates a completely new wrapper, loads the native v2 file and continues the
remaining route. Victory is saved and loaded again into another new wrapper.
Thus the default passing matrix contains 32 successful native-file round trips.
The original three-floor Save v1 slot is never used.

## Exact snapshot comparison

Before and after every disk round trip, the **entire** snapshot is compared
using the versioned `CampaignVariant.canonical_json` serializer. No audit,
resource, object, stock, seed, checkpoint or history field is removed.

The serializer's declared normalizations are representation rules: dictionary
keys are sorted; integral JSON numbers are written as integers; floor/object
arrays are ordered by their stable identities; cleared-ID arrays are sorted
because they represent sets. The cleared-ID ordering does not govern gameplay:
the frozen rules use membership tests, their validator builds a seen-ID set,
and Navigation builds an ID membership dictionary. Decision hashing uses this
same canonical serializer. Purchase counts, all resource values and the actual
IDs remain exact. Decision-log and checkpoint order is preserved.

The report binds both complete snapshot hashes, actual saved bytes/hash,
native storage result, load result and equality verdict. By default successful
test-owned save files are removed after verified loading; `--keep-saves` retains
them for inspection. Failed files are retained. `--output=` writes the full
per-event actual path, resource ledger, object/stock hashes and save receipts;
stdout remains a compact summary.

This is headless native evidence only. It does not establish real input,
rendered art, Web storage durability, browser behavior, arbitrary untested seeds
or human campaign duration.
