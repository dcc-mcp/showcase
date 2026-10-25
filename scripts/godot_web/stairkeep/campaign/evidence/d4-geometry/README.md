# Proposed D4 geometry properties

[properties.json](properties.json) is the actual Python 3.12 test receipt for
the proposed [geometry helper](../../tools/d4_grid.py) and
[test source](../../tests/test_d4_grid.py). All 16 named tests passed, with zero
failures/errors, in 1,300.581 ms. Source and frozen 21-floor fixture hashes are
recorded in the receipt. The engine was not launched for these tests.

The tests cover reversible coordinate/vector transforms, composition,
distances and adjacency, differing floor dimensions and stair endpoints,
stable entity/event references, static resource/route-ledger preservation,
synthetic directional/NPC/hidden/restore fields, unsupported-field rejection,
and conservative duplicate-layout exclusion. Fully symmetric content may have
no changed candidate. Opaque IDs, labels and equivalent enemy type aliases do
not by themselves establish a new encounter layout. The duplicate-exclusion
projection is not a semantic or save-state hash.

This does not implement D4 in GDScript, select a death/respawn policy, change
the old HV variant or save format, generate 50 floors, validate special combat
mechanics, or establish 50-floor balance/browser/visual acceptance. See the
[50-floor transition proposal](../../FIFTY-FLOOR-TRANSITION.md).

From this campaign project, using the existing Python standard library only:

```text
python -B tests/test_d4_grid.py --output=<new-report.json>
```

An existing report is refused rather than overwritten. No software installation
or paid service is required.
