# Historical split-boat comparison source and generation record

Recorded 2026-10-26. The active intact-source native-fracture plan uses [source-intact.zip](source-intact.zip) and [SOURCE-INTACT.md](SOURCE-INTACT.md); this split package remains a comparison. This package contains the actual Hyper3D Bang split model used for the assembled Houdini preview. It is source geometry for a production draft; it contains no completed destruction simulation.

## Actual generation sequence

The built-in image generator produced the intact wooden boat reference. Its complete prompt is in `imagegen-prompt.json` beside this archive. That reference was submitted to Hyper3D Rodin using `Gen-2.5-Medium`, `mesh_mode=Raw`, `geometry_file_format=obj`, `material=PBR` and `seed=4172`. Native import measured 500000 triangles.

The resulting Rodin asset was passed to Hyper3D Bang with `strength=7`, `quality_override=150000`, `mesh_mode=Raw`, `geometry_file_format=obj`, `material=PBR`, `resolution=Basic` and `seed=4172`. The instruction requested separate hull planks, ribs, gunwales, posts and bench boards in their assembled positions. Actual output and Houdini inspection yielded 17 named parts and 150000 triangles with vertex UVs. Group labels are the provider's existing labels, not a claim that every group is one anatomically correct timber.

The full public generation parameters, source hashes, mesh counts and archive member hashes are in `model-manifest.json` beside the archive. Provider asset identifiers, subscription keys, signed download links, account details, local paths and raw execution transcripts are excluded.

## Archive contents and import

`boat.obj` retains the generated coordinates, indices, normals, UVs and named objects. Only a relative `mtllib boat.mtl` directive and `usemtl wood` binding were added; no geometry repair, remeshing, rescaling or part merging was performed for this package. The added MTL binds only the base-color map for broad importer compatibility. `material.json` identifies the remaining PBR maps for explicit destination shader setup. No universal material appearance or tangent-normal convention is certified.

All five provider texture PNGs are preserved byte-for-byte under `textures/`: diffuse, metallic, normal, roughness and the additional provider PBR map. The additional packed map's channel layout has not been independently verified, so the explicit separate maps are the documented inputs. The OBJ's source coordinates have unspecified physical units. The assembled native preview used a separate scale and placement; its measured metre bounds are in the case validation.

Unzip to one directory and keep the relative structure intact. Import `boat.obj` with named objects preserved, then use `boat.mtl` for the diffuse map or construct a PBR material using `material.json`.

Independent Houdini acceptance of this archive preserved the 17-part, 150000-triangle geometry through HIP save/reopen and Bgeo export/reimport. The original importer nevertheless left the diffuse texture disabled and empty. Both results remain in `portable-acceptance-summary.json`. [Importer PR #361](https://github.com/dcc-mcp/dcc-mcp-houdini/pull/361), source `73e9db1e4dc85da16d33ab385cfa2f52e08b49f3`, subsequently passed native diffuse binding, scalar material values and save/reopen checks. Its native summary was recorded while the candidate was uncommitted; the later commit identifies the repaired source. A missing required texture reports `partial`. Separate roughness, metallic and normal texture binding and rendered equivalence remain outside that acceptance. No archive geometry or texture bytes were changed by this documentation update.

## Provider terms and rights

Provider sources checked on 2026-10-26: [Hyper3D Terms of Service](https://hyper3d.ai/legal/terms), [Hyper3D Copyright License](https://hyper3d.ai/legal/copyright-license), [Rodin Gen-2.5 API](https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5) and [Bang API](https://docs.hyper3d.ai/en/api-specification/bang). The provider's applicable terms, account entitlement and restrictions govern use of its generated output. These links and this production record do not replace those terms or establish independent legal clearance.

The case's generated artwork, model, textures and render derivatives are not assigned the repository's MIT software license. No additional blanket redistribution license, model-training license or evaluation-data grant is made here. Original input and third-party rights remain applicable. Check the relevant provider terms and rights before further distribution or a new use.
