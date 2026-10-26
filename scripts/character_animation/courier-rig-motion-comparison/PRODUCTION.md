# Bounded production recipe

These are planned operations, not a synthetic MCP transcript. Current task
authorization covers the three-rig showcase and a draft contribution, but
shared desktop use is serial and needs a fresh coordinator grant. Do not
restart or repair a shared runtime to obtain it.

## Prepare once

1. Verify source GLB SHA-256 against README. Keep the source unchanged. Run the
   two local scripts into separate output folders and check their manifests.
   The default-pose OBJ contains mesh/UV/normals only. Its MTL is an import
   convenience, not a PBR equivalence guarantee. The source GLB retains the
   historical skeleton, weights and animation for comparison only.
2. Retain source notices and exact software versions. Confirm Maya entitlement,
   installed mGear payload and applicable AdvancedSkeleton license before
   executing either payload. Do not buy or accept new terms automatically.
3. Verify the live Core production-reuse contract, inventory and task ownership.
   Preserve registry/access errors rather than redirecting to another registry
   or endpoint. Start no paused host. Once granted, discover through
   `dcc-mcp-cli list`, then `search` and each returned `next_step`.
4. Use a single audit session for the run. If gateway call statistics are needed,
   use `--require-gateway --agent-session-id <current-session>` from the first
   actual call; do not mix in direct calls and later label them gateway evidence.

## Maya / mGear

Use marketplace bundle `dcc-mcp-maya-mgear` at the recorded pinned commit.
Discover live environment inspection and Shifter component/template tools.
Inspect actual mGear and solver dependencies. Import the mesh through the
existing `mgear-import-to-scene`/Maya import chain where its live schema supports
the transfer format. Preserve a measured mesh-only checkpoint.

Inspect an official biped sample or build the smallest matching Shifter guide
from available components. Fit guides to the character's real shoulder, elbow,
hip, knee and ankle landmarks; old deformation-joint origins are starting hints,
not automatically correct mGear guide parameters. Build using the marketplace
skill, then use discovered Maya rigging tools for skin binding and weight edits.
Record new deformation-joint and control counts separately. Fit, bind and inspect
neutral, deep-knee and raised-arm poses before the motion take.

Animate actual rig controls with the existing Maya animation tools. If fitting
or control keying has no typed coverage, retain the failed search/schema and
use only the smallest exposed scripting bridge; do not replace Shifter build or
export with a new rig system. Save an editable `.ma`, reopen it, then use the
skill's discovered `export_shifter_rig` for baked FBX. Validate the returned
metrics against an independent fresh import, not just export success.

## Maya / AdvancedSkeleton

Proceed only after entitlement/payload verification. Use a separate scene with
the same mesh and dimensions. The pinned skill's source sequence is
`inspect_advancedskeleton` -> `import_fit_skeleton` or `create_fit_skeleton` ->
`configure_fit_joint` -> `build_advancedskeleton`. Actual slugs must come from
live discovery. A custom joint specification must be parent-first with valid
labels, including Root; a template name must come from installed templates.
Do not fabricate or import an arbitrary third-party MEL path.

Fit landmarks and run the same pose checks, then use separate Maya rigging and
animation tools for binding/keying. AdvancedSkeleton build does not establish
either of those stages. Await asynchronous build by its returned operation ID;
do not resubmit a timed-out mutation. Save/reopen `.ma`, bake/export FBX through
the discovered Maya interchange tools, then fresh-import and compare.

## Blender / official free candidate and actual discovery

Use the installed Blender 5.1 and its official bundled Rigify if the fresh host
confirms the recorded version. Load the existing extension provider and search
for relevant rigging capabilities with the actual Blender version, retaining
the real results. Inspect credible official candidates for version, GPL/other
terms, maintenance, host compatibility and public operators. An empty search
result is valid evidence; it does not justify an unknown-source download.

When a suitable external package is genuinely needed, call the provider's
search -> inspect -> download sequence, preserve its checksum-verified
`package`, then pass it unchanged to the host's `blender-extensions`
plan/install chain. Do not claim these operations when reusing bundled Rigify.
Do not execute downloaded add-on code before source, checksum and rights review.

Import the same original GLB, make a clean mesh-only copy for the new Rigify
skin, and preserve the old rig in a separate reference file. Convert glTF's
Y-up meters through the host's declared importer conversion, then measure in
Blender Z-up meters; do not apply a second guessed conversion. Fit an official
human metarig, generate through Rigify, bind and inspect the same pose tests.
Use mature operators through typed tools when available and minimal parameter
bridges only for gaps. Save/reopen `.blend`; export baked animation through the
host's supported interchange tools and reimport independently.

## Matched motion and delivery

`motion-brief.json` defines target timing and tolerances before production.
Use planted foot controls, matching actor displacement, a readable turn and a
simple reach/return action. Choose contact intervals from actual sole motion;
do not derive contact labels solely from ankle height. Measure the evaluated
skinned soles in world space after actor motion is applied. Inspect knees,
hips, shoulders, hands and garment intersections from front and side.

Capture a continuous native take for each rig at natural speed, plus a close
view of the stance/turn and a control-rig breakdown. Save counts, units, camera,
lighting, color management, bake/export settings and hashes. Compare native,
fresh-reopened, exported/reimported and blank-scene rebuilt stages separately.
Record failure and uncertainty with the same prominence as success.

The planned film uses intentional silence so foot motion remains the focus.
Still review full playback, frame continuity, start/end and transitions. Produce
H.264 1280-wide media within the repository's duration limit only from actual
host frames. Package native projects with relinkable source/texture notices,
exclude restricted plugin payloads, and retain an artifact manifest/breakdown.
Complete independent motion/technical review before a publication decision.

When real media exists, create `docs/showcase/courier-rig-motion-comparison/`
with the required hero, report, manifest, validation and truthful optional
production-stage index. Keep this slug through revisions. Run existing entry,
collection, locale and affected build checks. Only a deduplicated draft PR is
authorized; no merge, release, site publication or deployment follows.
