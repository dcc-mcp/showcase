# Tropical nature source

Two original leaning palms and two original broad-leaf understory variants were authored with Blender 4.3.2 built-ins. Their curved, tapered trunks, folded leaves, frond ribs and coconuts are real mesh geometry. All leaves have small physical thickness; no alpha-card texture is used. A selected CC0 KayKit bush and two pebbles are rematerialed to the shared blue-green/matte island palette. The unused second bush remains only in the editable library.

`export/tropical-nature.blend` is the editable source, saved without editor UI state or linked libraries. `native-reopen.json` records a separate Blender-process reopen. `export/authoring.json` records exact output hashes, triangle counts and bounds. Shipping GLBs and both original CC0 notices are in `../../game/assets/tropical/`.

## Rebuild

Run Blender with the already obtained official KayKit Forest Nature Pack 1.0 FREE glTF folder as input:

```sh
blender --background --factory-startup --python build_nature.py -- --source /path/to/Assets/gltf --out /path/to/output
blender --background --factory-startup --python verify_nature.py -- --blend /path/to/output/tropical-nature.blend --output /path/to/reopen.json
```

The scripts read static glTF data and use built-in mesh creation/import/export APIs. They do not download content, install plugins, or open a display service. Parameters are in the script: seeds 913/119, trunk heights 4.1/3.4 m, eight pinnate fronds, nine-sided trunk rings; broad-leaf seeds 211/721. Export is glTF 2.0 binary, Y-up, one joined mesh per nature asset and real leaf thickness.

Fresh factory-scene rebuilds preserve triangle counts, materials and vertex-position multisets to 1e-6 m. Blender may produce different binary ordering or floating-point normal bytes, so byte-identical rebuild hashes are not promised. Each delivered version has its own exact hashes. A native reopen is recorded separately from this rebuild comparison.

This is direct native Blender production. Blender MCP and extension-provider host calls were unavailable in this 4.3.2 asset session; no such coverage is claimed. The game continues to use the separately verified real Godot DCC-MCP author/save/reopen pipeline. Art acceptance still requires the ordinary playable Godot camera, rather than an isolated asset preview.
