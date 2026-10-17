# Tidal Sanctuary Explorer

A light beach explorer: coral cotton shirt, lagoon shorts, bare lower legs, sandals, and a warm canvas sun hat. The recognizable face and compatible 23-bone skeleton are derived from the CC0 KayKit Adventurers Ranger. Clothes, limbs, hat, small compass details, and the swim action were authored in Blender for this asset. The original cape, quiver, armor, weapons, and boots are absent.

## Files

- `../../game/assets/tropical/explorer.glb` (the rebuild writes `export/explorer.glb`): self-contained glTF 2.0 binary; one embedded head texture, no external asset references.
- `explorer.blend`: editable Blender 4.3.2 source; the head texture is packed and uses a relative basename.
- `build_explorer.py`: reproducible headless Blender creation script. Inputs and outputs are CLI arguments.
- `verify_explorer.py`: separate-process reopen, action evaluation, and CPU render check.
- `inspect_glb.py`: binary GLB structure/animation/embedded-resource inspection.
- `verification/reopen-check.json`: independent Blender reopen results.
- `verification/glb-check.json`: exported GLB integrity, source-free path, and animation results.
- Running verification also writes `preview-idle.png` and `preview-swim.png`: actual Blender renders for local asset review, not game screenshots. They are generated outputs rather than bundled source files.
- `SOURCE.json` and `LICENSE-KayKit.txt`: source hashes, original archive hash, official source pages, and original license notice.

## Coordinate contract

Godot/glTF: +Y up, -Z forward, feet at (0, 0, 0). Rest height including hat is 1.20 m. Animated Idle is approximately 1.19 m. The model retains an internal conversion root named `Explorer`, with Y rotation approximately 180 degrees and uniform scale 0.493827. These are intentional imported transforms. Keep them unchanged; rotate a fresh parent wrapper for gameplay heading and posture.

Blender source: +Z up. The source KayKit head faces -Y before the conversion root. The conversion root rotates 180 degrees around Blender Z; the exported complete model therefore faces Godot -Z.

The controller/collision shape is independent of the visual asset. The asset does not include a camera, collision shape, floor, light, or gameplay script.

## Animation contract

Only three exported clips are present, each exactly 1.0 s, with no root translation:

| GLB name | Origin | Use |
| --- | --- | --- |
| `Idle` | KayKit `Idle_A`, normalized to 24 frames | Quiet standing breath |
| `Walk` | KayKit `Walking_A`, normalized to 24 frames | In-place land travel |
| `Swim` | Original keyed action, 24 fps | Broad bilateral strokes and alternating kicks |

Set all three animations to `Animation.LOOP_LINEAR` in Godot; glTF does not standardize loop flags. Suggested transitions are 0.12 s between Idle/Walk and 0.18–0.25 s into/out of Swim. Either AnimationPlayer cross-fades or a three-state AnimationTree works. Change state only when it changes, rather than calling play every frame. Root motion is not needed; the gameplay controller owns translation.

## Swimming posture: apply exactly once

`Swim` is authored against the upright skeleton. It does not contain a prone body rotation. On a separate gameplay visual wrapper, interpolate X rotation from 0 to -PI/2 when entering swimming. Preserve the imported `Explorer` root's own conversion transform. With a yaw wrapper above the pitch wrapper, the body points along the usual -Z heading and its face points down toward the water.

Godot pitch basis for -PI/2 around X, shown in row-major form:

```
[ 1  0  0 ]
[ 0  0  1 ]
[ 0 -1  0 ]
```

Do not combine this wrapper pitch with a second -90-degree bone/root rotation. A visually centered swim pivot can be placed near the body midpoint, with the imported feet-origin mesh locally offset downward before pitch. This is a gameplay layout choice, not an additional rotation. Keeping the pivot at the feet is also valid if its position is compensated. Tune waterline/vertical offset against the actual game camera; do not copy the old primitive-body Y=0.6 offset onto the feet-origin model unchanged.

## Rebuild

```
blender --background --python build_explorer.py -- --source /path/to/KayKit_Adventurers_2.0_FREE --output /path/to/output
blender --background --python verify_explorer.py -- --blend /path/to/output/explorer.blend --output /path/to/output/verification
python inspect_glb.py /path/to/output/export/explorer.glb /path/to/output/verification/glb-check.json
```

The scripts only read the specified local KayKit package and write the specified output directory. They do not download files, install plugins, or start a GUI/display service. Required source filenames and hashes are in `SOURCE.json`.
