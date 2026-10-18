# Dawnkeep art rights and provenance

Verified 2026-10-18. This case uses original environment/architecture and Kay Lousberg's official free CC0 assets. No Warcraft, League of Legends, or other proprietary game assets, characters, logos, sounds, or map layouts are included. The genre and broad stylized-fantasy art direction are references only.

## Third-party art

All selected KayKit content is Creative Commons Zero 1.0 Universal. The bundled license explicitly permits personal, educational, and commercial use; attribution is optional. Credit is nevertheless retained: **Kay Lousberg, www.kaylousberg.com**. The license and original creator remain attached to the source material; this project does not claim authorship of those models or animations.

| Pack | Version/tier | Official source | Original archive SHA-256 |
|---|---|---|---|
| Forest Nature | 1.0 FREE | https://kaylousberg.itch.io/kaykit-forest | `2ee83e63bb7695f2d884ec27ddf6fce020789a452e7d5c5b0bbdfc4f6ea1fc8c` |
| Adventurers | 2.0 FREE | https://kaylousberg.itch.io/kaykit-adventurers | `abe48f4763fba0896bab486ee9e6d08ca6b5b3884b9601f235c8847ae94dc479` |
| Skeletons | 1.1 FREE | https://kaylousberg.itch.io/kaykit-skeletons | `21fbad59ee6cc1d7bed12d0e425acab8ebe564b8620bbc1d017aedb29dd8a3d2` |
| Character Animations | 1.1 FREE | https://kaylousberg.itch.io/kaykit-character-animations | `65882f31f905ad2e953819648a59287cdeab8f623908d5ef701971d3758be20f` |

The copies of the author's bundled licenses are in `art/licenses/`. See `art/download-manifest.json` for acquisition UTC timestamps, byte counts, source versions, and official public free-download route. No paid EXTRA/SOURCE tier, payment, account, or proprietary game content was used. CC0 legal text: https://creativecommons.org/publicdomain/zero/1.0/

Runtime selection is listed with per-file hashes in `game/assets/kaykit/SOURCE.json`. `art/prepare_runtime.py` selects official source meshes and copies glTF buffer/accessor data, maps animation target nodes by exact joint name, and attaches official sword/shield equipment to the Knight's existing hand-slot bones. It does not recreate, reskin, or retarget the character rig. Runtime original orange cape recoloring and game-state VFX are implemented in `game/visuals.gd`. The unused unarmed Knight is retained as an inspectable comparison/fallback.

## Original work

`art/build_dawnkeep.py`, `art/dawnkeep-original.blend`, `game/assets/original/`, `game/visuals.gd`, and `game/shaders/` contain the original Dawnkeep floating terrace, road arrangement, carved shrine ribs, crystal assembly, tower silhouettes, heraldic standard, original effects, and visual integration. All rights in the original artwork, scene, design, content, recipes and integration are reserved under the case's LICENSES.md; the repository's general MIT grant does not cover this case's original work. Imported KayKit assets retain their separate CC0 provenance. The original meshes were created using native Blender 4.3.2 Python, not Blender MCP; the native work must not be represented as typed MCP execution.

Music and sound have their own notices elsewhere in this case and are outside this art inventory.
