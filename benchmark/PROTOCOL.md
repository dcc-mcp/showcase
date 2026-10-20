# Model preview and comparable-run pilot

Status: infrastructure pilot, not a benchmark release. The public index is an
inventory of selected works. Zero accepted runs. No model scores or leaderboard.
Existing model attribution is historical, stage-specific evidence; it must not
be promoted into the exact model identity for a new measured run.

## Compare like with like

A future comparison card has a frozen task/specification and input hashes on the
left, then one column per recorded attempt. Only records sharing task hash,
protocol revision, split, evaluation rubric and budget may be compared. Hardware
and runtime differences must remain visible; matching these is required for
resource-efficiency claims. Never compare different curated tasks as model wins.

The detail view separates: brief and inputs; native/source artifacts and rights;
model identity receipts by stage; runtime/software/hardware; seed and attempt;
wall time and tool-call accounting; visual/manual judgments; structural checks;
and incomplete/failed stages. No global score is derived in this pilot.

Unknown means null, displayed as “Not recorded”, not zero, a failed check, an
inferred model alias, or exclusion from a denominator. Actual failed attempts
remain in their declared cohort. Public examples and reusable prompts are not
held-out/hidden tests. Rights to public display do not confer evaluation,
training or redistribution rights.

## Run interchange

`run.schema.json` defines the proposed machine-readable unit. `runs.json` remains
empty until a frozen protocol, scoped evaluation rights and genuine production
receipts are reviewed. The builder deliberately rejects nonempty runs during
this pilot. This is separate from the ecosystem gate and must never bypass it.
Task fields in `index.json` point to the authoritative collection, not to a newly
invented task spec. A stable task hash is required before comparative runs.

## Preview acceptance

`model-previews.json` is an explicit allowlist, empty until acceptance. A case
must pass the complete ecosystem production gate from PR #46 before activation;
the asset must be in its hash-bound public inventory, have an explicit scoped
display permission and license reference, and be a self-contained GLB ≤8 MiB.
No external buffers/images or decoder downloads are accepted in this pilot.
Only KHR_materials_emissive_strength (a numeric material scalar) is allowed;
other extensions require review. Desktop/mobile memory and triangle/texture budgets remain future explicit
acceptance measurements; compressed file size alone is not a GPU-memory bound.

The viewer is locally vendored @google/model-viewer 4.4.0 (Apache-2.0), loaded
only after a click. Drag/pinch and keyboard-accessible orbit/zoom/reset buttons
are available. No autoplay, automatic rotation, audio or AR. Close cancels late
activation; failure/timeout keeps the original case images and source links.
Materials/lighting are a browser approximation, not native render equivalence.

## Reference and current audit

[BlenderWorld](https://blenderworld.github.io/#showcase) was consulted on
2026-10-20. Useful patterns: task-first comparison, selectable model submissions,
brief/reference context, interactive artifacts, separate structural and visual
evaluation, and an explicit warning that curated samples do not measure average
quality. Its scores and model identities are not imported.

The existing site is Python static generation plus plain browser JavaScript.
The current GLBs are Orbital Loom's historical artifact and Dawnkeep's original
and third-party game assets. Historical native-only exports are not eligible by
renaming them. Dawnkeep MCP rebuild acceptance is separate ongoing work. This
change neither rerenders nor modifies assets, production claims or licenses.
