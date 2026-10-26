# Relic Courier: prepare a matched three-rig motion comparison

Status: preflight only, 2026-10-24. Stable case slug:
`courier-rig-motion-comparison`. This directory is outside the selected showcase
inventory because no new Maya or Blender production run has completed.

The intended comparison uses one existing Hyper3D-derived character mesh in
Maya with mGear, Maya with AdvancedSkeleton, and Blender with official Rigify.
The same motion brief, geometry, camera and lighting will make rig behavior
inspectable. A model, deformation skeleton, skin, control rig and animation are
five separate milestones. Existing Blender-authored game clips do not prove
either Maya rig or a Rigify control rig.

## What exists

The inspected `courier-character.glb` has SHA-256
`82a7b7456137eb133753650e2d9cda4f016ea810df68adcbfdc267f83ab29cd2`.
Its existing geometry has 30,000 triangles and 36,287 vertex entries. Its skin
uses a 17-joint skeleton, with 16 joints receiving nonzero weights. Five
historical clips are embedded: Idle, Walk, Dash, Attack and Cast.
[Source-bound measurements](measured-input.json) record these counts, numerical
checks, corrected transfer hashes and unresolved real-host stages.

The offline audit reads accessor bytes, samples quaternion/TRS animation and
composes the joint hierarchy. It does not run a DCC, simulate contact, or inspect
skinned pixels. All historical clip Root translations are stationary. Actor
locomotion is therefore a separate input, not evidence of a faulty clip. A low
foot-joint trajectory is only a review flag: the joint is not a sole contact.
Matching endpoints do not test velocity or angular-velocity continuity.

`audit_existing_motion.py` writes source-bound skin, inverse-bind and motion
measurements. `prepare_neutral_mesh.py` creates an explicit mesh-only default
pose OBJ bridge for Maya, with centimeters and original embedded textures.
The bridge converts glTF's top-origin UVs to OBJ bottom-origin UVs using
`(u, 1-v)`; inverse UV conversion is measured separately from serialization.
Neither script creates a control rig. Generated outputs remain local and are
not part of this source directory's public inventory.

```powershell
python audit_existing_motion.py --input <courier-character.glb> --output-dir <audit-directory>
python prepare_neutral_mesh.py --input <courier-character.glb> --output-dir <transfer-directory>
```

Acquire the source through its existing rights-cleared project, check the hash,
and retain the original notices. Do not silently accept a different GLB.
Use a new empty output directory for each run; both tools preserve previous
evidence by refusing nonempty destinations.

Both scripts require runtime assertions: optimized Python (`-O` or `-OO`) is
unsupported and is refused before parsing or writing output. Wrong-hash and
nonempty-output refusals remain explicit even in optimized mode; that does not
qualify optimized conversion or measurement. The script hashes in
`measured-input.json` belong to its recorded historical source commit, not the
latest scripts. [Dated offline revalidation](offline-revalidation-2026-10-27.json)
separately records the updated script hashes and new offline checks.

## Discovered capabilities

| Candidate | Current evidence | Remaining proof |
| --- | --- | --- |
| Maya mGear skill bundle 0.4.3 | Actual catalog inspect; pinned commit `9c45b87b0dda501f5d53f71ad7b39f5905a81b4c`; source schema inspected | Installed payload/version, Maya entitlement, real guide/build/bind/animation/export calls |
| Maya AdvancedSkeleton skill 0.1.1 | Actual catalog inspect; pinned commit `2e6a6dcd350a3e35d89b1a4c7870d2908103ea15`; source schema inspected | Applicable license, installed payload/version, real FitSkeleton/build/bind/animation/export calls |
| Blender Extensions provider 0.1.0 | Actual catalog inspect; pinned commit `503cdadef0238e827da01ede65618ee2c26601f5` | Actual official-extension search, compatible exact package inspection/acquisition, checksum, host enable and use |
| Official bundled Rigify 0.6.10 | Blender 5.1 installed source header declares GPL-2.0-or-later, Blender Foundation and OFFICIAL support | Fresh task-owned host, enabled add-on/version, generated rig, binding, animation and reopen |

Catalog inspect is not provider search or host execution. Bundled Rigify must
not be described as automatically downloaded. If suitable free rigging software
is already bundled, reuse it and separately demonstrate the provider's honest
search result. Do not install an unrelated extension merely to manufacture a
positive download claim. Discover live tool slugs and schemas after a ready,
task-owned instance is available; source tool names below are not routing tokens.

## Rights and compatibility

mGear is MIT; official release 5.4.2 includes Windows targets for Maya 2024 and
2026, which still need a real load. AdvancedSkeleton has its own EULA: the
official site makes noncommercial use free and sells commercial-use licenses.
No applicable entitlement has been verified for this promotional case. The
MIT integration skill does not grant payload rights. The separately advertised
AdvancedSkeleton Blender plugin requires Blender 5.2+, so it is not the chosen
Blender 5.1 path.

Rigify's bundled code and generated rig scripts carry GPL notices that must be
preserved when those scripts are distributed. Hyper3D output retains separate
account/plan-specific terms; it is not relicensed under the repository's MIT
license. Existing project provenance records that TAPose did not provide its
skeleton or animation. No new Hyper3D generation, payment or redistribution is
performed by this preflight.

Sources checked on 2026-10-24:
[mGear release](https://github.com/mgear-dev/mgear/releases/tag/5.4.2),
[mGear license](https://github.com/mgear-dev/mgear/blob/5.4.2/LICENSE),
[AdvancedSkeleton download](https://animationstudios.com.au/download.html),
[commercial terms](https://animationstudios.com.au/studios.html),
[Rigify manual](https://docs.blender.org/manual/en/latest/addons/rigify/index.html),
[Hyper3D terms](https://hyper3d.ai/legal/terms).

## Next real-host run

Follow [the production recipe](PRODUCTION.md) and
[planned measurements](motion-brief.json). The host run is blocked by live
inventory access and the serial desktop grant; AdvancedSkeleton additionally
needs applicable entitlement and payload evidence. The THM cache failure was
reported by the handoff and was not retried or bypassed here.

No `.ma`, `.blend`, FBX, video or animation acceptance result has been produced
for this comparison. Save/reopen, export/reopen, blank-scene rebuild, motion
review and all three actual marketplace skill paths remain outstanding.
Do not select this case in `collection.json` or represent it as a completed
showcase until those checks and the publication contract are satisfied.
