# Native boat replay

This package rebuilds the shot from the adjacent public `source-model.zip`.
It requires licensed Houdini 22 with the installed native RBD Glue Object,
FLIP, Script Solver and Mantra node types, plus the DCC-MCP Houdini automation,
parameter and render tools. It makes no generation requests or paid calls.
The build refuses an occupied object network and never clears a scene.

The public OBJ has 17 named parts and 150,000 triangles. A 4,000-triangle
simulation proxy preserves the part names, paths and vertex UVs. Native DOP
transform points and Transform Pieces move the original high resolution mesh
for the piece caches and render. The initial rest comparison must pass within
0.002 m before continuing. The boat is normalized to 6 m long with its keel at
-0.25 m. The supplied UV maps are bound explicitly to a Principled Shader;
the OBJ's MTL only supplies a relative diffuse binding.

## Prepare local inputs

Run `python selfcheck.py` from this directory. This checks asset hashes, OBJ
part/face parsing, payload dependency order, callback contracts and failure-rule
math. It does not run Houdini or certify fluid behavior.

Copy `config.example.json` to a local config and set `asset_dir` and
`output_root` to paths visible to the chosen Houdini host. Relative paths resolve
against the config file. Use a fresh output directory and keep generated calls,
receipts, scenes and caches outside the published case directory.

```powershell
python prepare.py ./config-run.json --extract ../source-model.zip
```

`--extract` verifies the exact archive hash and safe member names and requires
a fresh asset directory. Omit it when the verified assets are already extracted.
Preparation writes JSON call inputs and `call-plan.json`; it performs no host
calls. The default cache input requests two frames. A 96-frame run requires
explicitly changing `end_frame` to 96 in a new local config/output directory.

## Rebuild in a separate empty scene

Use the normal DCC-MCP discovery route to select a task-owned Houdini instance,
load the needed skills, and describe the installed tools. Use the returned
instance identifier; no identifier or endpoint is embedded in these files.

```powershell
dcc-mcp-cli search --query "build node chain" --dcc-type houdini
dcc-mcp-cli search --query "set node parms" --dcc-type houdini
dcc-mcp-cli search --query "run python file" --dcc-type houdini
```

Execute the `phase=build` rows of the generated `call-plan.json` in their listed
order. `00` asserts an empty `/obj`, sets 24 fps and frame 1. For each node
recipe, first call its `.dry-run.json` input after its parent has been built,
inspect the result, then apply the normal JSON. An example, using your selected
instance and prepared calls directory:

```powershell
$instance = '<selected-instance-id>'
$calls = '<prepared-output-root>/calls'
dcc-mcp-cli call houdini_automation__build_node_chain --dcc-type houdini --instance-id $instance --json-file "$calls/01-containers.dry-run.json" --output json
dcc-mcp-cli call houdini_automation__build_node_chain --dcc-type houdini --instance-id $instance --json-file "$calls/01-containers.json" --output json
```

| Input | Tool | Result |
| --- | --- | --- |
| 00 | `houdini_automation__run_python_file` | Empty scene check and timing |
| 01–04 | `houdini_automation__build_node_chain` | Stable File SOP, normalization, pieces/proxy, container walls, coupled DOP and high resolution reconstruction |
| 05–09 | `houdini_automation__build_node_chain` | PBR materials, camera/lights, floor, cache readers, Mantra ROP |
| 10–11 | `houdini_automation__run_python_file` | Render flags and actual frame-1 source/proxy/reconstruction checks |

Retain every raw tool response. Check the nested tool result and native node
errors as well as the outer CLI envelope. The builder's dry-run proves payload
validation; it does not prove cooking, simulation or rendering. `11` evaluates
frame 1 and requires 17 real DOP transform points and preserved high resolution
positions/UVs. The default native DOP creation script supplies `file_output`;
an installation that lacks it must fail the dry-run rather than silently
replacing the network.

## Simulate and measure explicitly

Call `12-cache-short-or-explicit-run.json` through
`houdini_automation__run_python_file` only after the build checks pass. It advances
the coupled simulation once, writes a frame-1 `boat-fluid.hip`, per-frame
`pieces.NNNN.bgeo.sc` and `water_particles.NNNN.bgeo.sc`, and `metrics.json`.
Every frame requires nonempty fluid, all 17 physical bodies, finite transforms,
and a piece cache with vertex UVs. A `STOP` file inside the run directory stops
the loop before its next frame; partial evidence is preserved. A short run
checks execution only and cannot establish settling or flotation.

The actual settings are native RBD before FLIP in a mutual collision merge,
two DOP substeps, water separation 0.1 m, grid scale 1.25, four particles per
voxel, FLIP feedback scale 1, and native solid walls/floor. Initial water is an
8 × 1.2 × 10 m pool united with a raised pulse, moving at 3.5 m/s along +X.
Collision SDF spacing is 0.04 m with 0.08 m surface offset and density 400 kg/m³.
The inflated proxy changes computed mass as well as collision shape; this is
a coarse VFX setup, with no engineering accuracy claim.

The Script Solver reads native water-only `Feedback/Impacts`, sums the existing
vector `normal * impulse`, divides by the actual timestep and compares its
resultant magnitude with `1.3 * mass * gravity`. The native `normal` record is
already a scaled vector and is not normalized. Pending `computemass` bodies and
new objects are skipped. On overload it clears only the native `glueobject`
attachment; no release frame, motion or extra force is prescribed. This is a
coarse fluid-load failure rule, not a structural stress model. The callback runs
before RBD consumes the preceding FLIP feedback.

For a separate feedback-disabled control, use the optional
`control-feedback-off.json` with `houdini_nodes__set_node_parms` before any
simulation frame; rebuild in a separate empty scene and fresh run. Restore
`control-feedback-on.json` for a separate enabled trial. Set `release_enabled`
false in a new config for a diagnostic-only failure rule. Do not compare trials
that reused an already advanced DOP state.

After a sufficiently long finished run, optional `13-check-flotation.json`
samples the last 12 cached frames against local water-surface rays for each
recorded fluid-released part. It reports missing samples, submerged/airborne
pieces and continuing vertical motion. Its declared 0.2 m waterline tolerance
and speed limits are VFX observations; it never turns a short/failed window into
a pass.

## Render cached geometry explicitly

The ROP `/out/boat_fluid_beauty` reads `BEAUTY`, which contains only the high
resolution piece cache and surfaced water cache, plus the separate pool base.
It uses `/obj/boat_camera`, 960 × 540 resolution, 3 × 3 pixel samples and
1–6 ray samples. Output is `<run>/renders/boat.$F4.exr`.

Optional `14-render-cached-frame.json` uses the existing
`houdini_render__render_rop` tool for frame 1, with `background=true`. Inspect its
returned job with `houdini_render__get_render_job`, passing the actual `job_id`
and `include_details=true`. For a completed 96-frame cache, explicitly request
`frame_range=[1,95,2]` for an every-other-frame review render. This is separate
from the default build/short verification. Rendering never substitutes for
native simulation metrics, cache/reopen checks or motion review.

The independent native blank-scene rebuild passed the frame-1 rest checks and
two-frame cache comparison: piece and water positions matched exactly, with
piece names, paths, UVs and normals preserved ([rebuild summary](../rebuild-summary.json)).
After reopening its native scene, the controlled frame-1 render matched decoded
production pixels ([render comparison](../render-rebuild-summary.json)). Full
sequence simulation and all-frame render equivalence remain unverified. The
offline self-check does not establish these native results.
