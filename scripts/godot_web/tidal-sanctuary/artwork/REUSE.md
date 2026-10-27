# Tropical art reuse review, 2026-10-17

The bounded target is a compact warm low-poly island: readable palm silhouettes, cool green foliage, soft low-frequency ground/stone materials and a coral explorer against teal water. Existing treasure, swimming, shore-return and save behavior are retained. The first visual decision uses matching ordinary gameplay cameras, not an isolated hero composition.

## Selected static assets

- Kay Lousberg's [Forest Nature Pack](https://kaylousberg.itch.io/kaykit-forest), free package 1.0: small bush/rock meshes suit the target silhouette after shared matte materials. The author page and bundled License.txt state CC0. The exact 6,435,630-byte archive was obtained from the official free download and safely inspected; source/output hashes are in the game's tropical source manifest.
- [KayKit Adventurers](https://kaylousberg.itch.io/kaykit-adventurers), free package 2.0: the Ranger head and compatible 23-bone rig provide a coherent character base. Compatible Idle_A and Walking_A are reused, while beach clothing and swimming keys are original. The exact 13,024,345-byte free archive and its CC0 notice were checked. Free glTF is used; the separately paid Blender source package is excluded.

Only the listed static glTF/buffer/image/license files were extracted, with path, symlink and size checks. No downloaded script ran. The selected upstream CC0 assets may be redistributed under their upstream terms. Blender's software license does not alter the separate rights stated for this case's original work. All credited upstream geometry/actions remain CC0.

## Capability discovery and limits

The existing [DCC-MCP Blender Extensions provider](https://github.com/dcc-mcp/dcc-asset-blender-extensions) and its `blender-extension-store` route were located through the official DCC-MCP marketplace. There was no ready Blender/provider MCP host in this asset session. Existing Blender was 4.3.2; the separately investigated current Blender adapter requires a newer host. No provider download, extension installation or Blender MCP capability call is claimed.

Official Blender Extensions discovery included [Sapling Tree Gen](https://extensions.blender.org/add-ons/sapling-tree-gen/versions/) and [Generate Tree Plugin](https://extensions.blender.org/add-ons/generate-tree-plugin/). The indexed official Sapling listing requires Blender 4.4 or newer. The current official detail pages could not be retrieved in the final read-only check, so installation compatibility and output rights were not promoted to verified. Neither extension was installed. Their tree-generation functionality also does not supply the selected explorer or original swim action.

The selected narrow fallback uses existing Blender built-in mesh, material, armature, keyframe and glTF import/export APIs. It adds no runtime, marketplace or plugin system. Fixed seeds and dimensions are in the native scripts. Actual native saving, independent reopen, self-contained export and Godot import were run; native Blender operations are explicitly separate from the game's genuine typed Godot DCC-MCP production chain.

## Evidence boundary

Blender asset previews do not establish Godot visual quality. Structural counts do not establish frame rate, and emulated touch does not establish physical-phone compatibility. No audio is present. The art candidate requires a new hosted actual-input/render/save-reopen run and independent inspection before an improvement claim. The earlier successful gameplay build is evidence for its own exact head only.
