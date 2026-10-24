# Bounded discovery, 2026-10-24

This is source/catalog evidence and an offline preparation recipe. It is not a
live-host capability transcript. GitHub source inspection used `gh` throughout.

The actual catalog commands completed successfully with CLI 0.20.46:

```text
dcc-mcp-cli --no-auto-gateway --no-update-maintenance --non-interactive marketplace inspect dcc-mcp-maya-mgear --output toon
dcc-mcp-cli --no-auto-gateway --no-update-maintenance --non-interactive marketplace inspect dcc-mcp-maya-advancedskeleton --output toon
dcc-mcp-cli --no-auto-gateway --no-update-maintenance --non-interactive marketplace inspect dcc-asset-blender-extensions --output toon
```

Exact catalog identities are in README. Reads of the pinned `SKILL.md` and
`tools.yaml` established the intended workflow boundaries:

- mGear: environment inspect, Shifter component/template inspection, guide
  creation/sample import, rig build and verifiable FBX/Alembic export. The
  import bundle depends on Maya import and rigging capabilities. Those
  dependencies still need live discovery.
- AdvancedSkeleton: installed-package inspect, FitSkeleton template import or
  parent-first custom specification, supported attribute configuration and
  asynchronous build/rebuild. Skin binding and animation belong to separate
  capabilities. The skill explicitly requires a licensed payload.
- Blender store: official-repository search and inspection; checksum-verified
  package download; the separate host package plans/enables it. A catalog read
  is not an extension search, acquisition or host enable.

The reuse investigation also read the canonical Core source through `gh api`
and confirmed `dcc-mcp-production-reuse/v1`. The installed gateway's actual
contract/version could not be read. The official mGear 5.4.2 Quick Start source
explains fitted guides, build, deformation-joint skinning and foot pivots. The
official Rigify manual and installed source motivate a visible breakdown from
metarig to generated controls to skinned motion, with the metarig retained for
regeneration. These are technical references, not copied animation assets.

## Real-host prerequisites still unresolved

The normal local inventory command failed before a usable host list was
returned: `INTERNAL_ERROR`, registry lock access denied. Read-only `doctor`
reported local inventory unavailable, gateway unhealthy and the selected
server binary missing. No host search/load/call followed; no alternative
registry, transport or modified ACL was used. The shared desktop also has no
fresh serial slot for this case. A handoff reported a separate THM read-only
cache problem; this run did not repeat THM or repair shared infrastructure.

Keep these records distinct from a zero-instance result. No assertion is made
about how many applications are currently running. A successful host call,
license check, native import, control-rig generation and save/export reopen
still need a supported runtime and task-owned session.

## Rigify source traps to check in the actual run

Installed official source gives search clues `object.armature_human_metarig_add`
and `pose.rigify_generate`. They are Blender operator names, not MCP slugs.
The generation operator catches some exceptions and can still return
`FINISHED`; read back the generated target rig, reports, deform bones,
controls, constraints, drivers and widget collection before declaring success.
IK/FK snap/bake operator suffixes include a generated rig ID, so discover them
from the actual rig. Automatic weights are only a starting point; a mesh
parented to the metarig instead of the generated rig is not this experiment.

FBX deform-only export can retain nondeforming ancestors of deformation
bones. Measure the emitted hierarchy and baked animation after fresh import.
Retain known-source generated Rigify UI notices; do not enable arbitrary
project scripts globally merely to make reopening appear successful.

Sources: [Core reuse guide](https://github.com/dcc-mcp/dcc-mcp-core/blob/main/crates/dcc-mcp-gateway/src/gateway/native_resources/agent_workflows.md),
[mGear source](https://github.com/mgear-dev/mgear/blob/5.4.2/docs/source/quickStart.rst),
[Rigify manual](https://docs.blender.org/manual/en/latest/addons/rigify/index.html),
[pinned extension provider](https://github.com/dcc-mcp/dcc-asset-blender-extensions/tree/503cdadef0238e827da01ede65618ee2c26601f5/skill/blender-extension-store).
