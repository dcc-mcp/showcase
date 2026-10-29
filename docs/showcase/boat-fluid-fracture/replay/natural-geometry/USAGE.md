# Native wood rest geometry

These recipes start from the intact generated 500K-triangle hull in
`../../source-intact.zip` and use Houdini's native WOOD fracture. They describe
static rest geometry. They do not reproduce a fluid blast, actor clustering,
constraint failure or flotation.

Houdini 22.0.368 was tested with explicit `rbdmaterialfracture::2.0` and the
existing typed DCC-MCP tools. The node's installed 2.0 parameters and three-output
contract were checked; the presence of newer versions does not make them
interchangeable. Density is explicitly 400 kg/m3, not an inferred wood species.

Prepare payloads in a new local output directory:

```text
python prepare.py --source-archive ../../source-intact.zip --out /absolute/new/native-wood-run
python -B selfcheck.py
```

Preparation verifies the exact archive and actual `boat.obj` member hashes,
extracts safe relative members, and writes task-local JSON payloads. It makes no
DCC call and refuses to overwrite an existing output directory. Machine paths
appear only in those local payloads, not in the published recipe templates.

Use the normal DCC-MCP Skill route: inventory, select an explicitly owned blank
Houdini session, search/load `houdini-automation`, and describe the returned
`build_node_chain`, `run_python_file`, `save_hip_file` and `load_hip_file` slugs.
Use the exact discovered slugs with `dcc-mcp-cli call` and `--json-file`.
Nothing in this replay clears an existing scene or installs a dependency.

Apply the payloads in numerical order:

1. For 00, 01, 02 and 03, apply each `.dry-run.json` and inspect the result before
   applying the corresponding normal JSON through `build_node_chain`.
2. Apply `04-cache-and-verify.json` through `run_python_file`. Allow at least
   `--timeout-secs 900` for its bounded full topology, UV/N and closed-volume
   audit. The accepted run took about seven minutes. A CLI timeout alone does
   not establish whether the native script stopped; retain the receipt and
   inspect its output before any retry. Never blindly repeat a mutation.
3. After `cold-rebuild.json` exists and passes, dry-run and apply
   `05-ready-readers` through `build_node_chain`.
4. Apply `06-recover-audit.json` through `run_python_file`. It binds the completed
   report to unchanged cache hashes and raw File SOP output without refracturing.
5. Apply `07-save.json`, `08-reopen.json` and `09-verify-reopened.json` through
   `save_hip_file`, `load_hip_file` and `run_python_file`, respectively.

The complete native cold rebuild and cache-reader save/reopen passed. The
initial full audit exceeded its 300-second CLI wait; its completed native report
was retrieved through a subsequent successful typed readback. No mutation was
retried. Evidence is summarized in `../../native-geometry-summary.json`.

Recipe 01 scales the long Z extent to 6 m and places the keel at Y=-0.25 m without
capping or repairing the source. Recipe 02 uses seeded grain cuts, crosscuts and
splinters. Physical grain runs along +Z; the grain cutter parameter is the plane
normal +X. Recipe 03 removes only the measured zero-volume, two-triangle
`naturalwood-intact_hull-8-10` artifact and its one incident bond. Raw native
output is 72 names/172 bonds; accepted rest geometry is 71 names/171 bonds.

The rest cache contains exterior source UV/N and new inside-face labels
`inside`, `surface_role=cutwood` and `is_cutface=1`. New cut faces need a separate
procedural wood shader; original texture meaning is not claimed on them.

For the delivered static assets, extract `../../fractured-rest.zip` and follow
its `asset-manifest.json` role map. The complete uninflated render mesh is also
the full wood source for constructing a fluid collision SDF. Identical geometry
allows that role to reuse the render file. The 20K contact proxy is separate.
Recipe 05 is for freshly rebuilt four-file audit output; when loading the
three-cache delivered package, bind both render and full-SDF-source roles to the
single render file as its manifest specifies.

The delivered bundle has no HIP: the private proof HIP retained local source
paths, so it is not distributed. The portable recipe is the native project
reconstruction route. Mass/COM and full inertia metadata come from the closed
full geometry; the tensor is an independent reference, not a native Bullet
override. Proxy contacts, shrink, convex filling and inertia convergence need
their own dynamics checks. Shared cut area, section moments, minimum physical
thickness and absence of self intersections are not certified. Seventy-one
geometric pieces do not assert seventy-one independent FLIP solids or actors.
