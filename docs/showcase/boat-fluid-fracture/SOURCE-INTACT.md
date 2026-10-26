# Intact Rodin boat source for a new native-fracture candidate

Recorded 2026-10-26. This is the actual intact Hyper3D Rodin source, separate from the earlier Bang split-model comparison. It is an input package for a planned Houdini native wood-fracture, constraint, Bullet and FLIP workflow. It contains no completed fracture simulation, released pieces or flotation result.

The built-in imagegen reference was submitted to Rodin with Gen-2.5-Medium, Raw triangle mesh, OBJ, PBR and seed 4172. The complete generation prompt and settings are in source-intact-manifest.json beside the archive; imagegen-prompt.json preserves the reference prompt. Provider identifiers, account details, signed URLs, credentials and private execution paths are omitted.

## Geometry and portable import

The original OBJ has 1 named object, 249960 vertex positions, 262894 UV coordinates, 390147 normals and 500000 triangle faces. Every face corner references an in-range position, UV and normal. These counts and finite-value checks were parsed from the actual source bytes. They are not new Houdini fracture counts, watertightness proof, engineering hull certification or a new archive import/save/reopen acceptance.

boat.obj preserves the complete original OBJ payload byte-for-byte after a relative mtllib/usemtl prefix. No vertex, index, normal, UV, object, scale or mesh repair is changed for packaging. Source units are unspecified. boat.mtl binds only textures/texture_diffuse.png for basic diffuse portability. material.json lists the separate metallic, normal and roughness maps for explicit destination shader setup. The additional provider PBR map is preserved, but its packed-channel layout has not been independently verified. No universal tangent-normal convention, full PBR equivalence or destination appearance is certified.

Extract the archive into one directory, retain the relative structure and import boat.obj. The generated hull may require explicitly documented native preprocessing for fracture. Such production geometry and its validation must be recorded separately from this unchanged source package.

## Provider terms and rights

Authoritative sources checked 2026-10-26: [Hyper3D Terms of Service](https://hyper3d.ai/legal/terms), [Hyper3D Copyright License](https://hyper3d.ai/legal/copyright-license), [Rodin Gen-2.5 API](https://docs.hyper3d.ai/en/api-specification/rodin-gen2-5). Applicable provider terms, account entitlement, input rights and restrictions govern use. These links and this record do not establish independent legal clearance.

The generated image, model, textures and render derivatives are not assigned the repository MIT software license. No additional blanket redistribution, model-training or evaluation-data license is granted here. Further distribution or new uses remain subject to the relevant terms and rights.
