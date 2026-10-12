# Orbital Loom

An original tabletop kinetic sculpture in petrol enamel, satin brass and ivory ceramic. Three nested gimbals turn at different rates over a calibrated plinth, while a constrained camera travels around the object. The film is made from consecutive Blender renders, with real changing geometry and camera transforms.

## Reproduce

Use the tested Blender 4.5.14 LTS host (newer host versions were not validated for these reproduction scripts), with official dcc-mcp-blender 0.2.16 and dcc-mcp-core 0.20.42. Open `orbital-loom.blend` and play its timeline. The native project keeps editable meshes, three live expression drivers, a Track To camera constraint, PBR materials and studio lights. No external textures or asset downloads are needed.

For exact reconstruction, place `build_scene.py` in a writable project directory and execute it through the official adapter's `blender_scripting__execute_script_file` tool. This is the supported scripting escape hatch, not a claim of typed-only modeling. Load `blender-scene`, `blender-animation`, and `blender-render`; open the scene with `blender_scene__open_scene`; set the output to 960×540, 24 fps, Cycles CPU, 16 samples and denoising. For each frame from 1 through 360, call `blender_animation__set_current_frame` and `blender_render__render_scene`, writing zero-padded PNGs. Encode those frames at 24 fps using H.264/yuv420p with faststart. The final native file uses a relative render directory.

The embedded adapter endpoint was loopback-only, with gateway_port=0. The safe local setup and observed gateway option mismatch are documented in `toolchain-findings.md`. Gateway-mediated CLI calls were not accepted as evidence for this run.

## Verified tool failure

The typed driver tool in the tested release cannot target the requested Z channel using its advertised component-path style. A vector fallback silently adds zero-valued drivers to other channels. The isolated regression probe and readback are published in `driver-probe.json`; production uses the declared scripting path with explicit axis indices.

## Evidence and boundaries

- `validation.json` contains measured scene, clearance, export, native reopen and video checks.
- `mcp-summary.json` is a reduced list of actual successful calls. It is not a full private trace.
- `orbital-loom-animated.glb` bakes the three drivers to rotation keys. It excludes the studio, camera and native text. It was imported again into Blender and its three animated objects were found. This does not establish cross-renderer material fidelity.
- `orbital-loom.blend` preserves the live drivers and the complete studio. A metadata-sanitized compressed copy was reopened and inspected.
- Mechanical clearances are visualization checks. Intentional shaft/bearing connections are not treated as collisions. This is not a fabrication-ready engineering certification.
- The work was created and rendered headlessly. GUI operation, screen recording of the UI, and end-user acceptance are not claimed.

## Iteration

The first preview had a tight lower crop and incorrect shaft orientation caused by a missing transform update before parenting. Those were corrected in the scene. The camera was moved back, its target lowered, and the bearing columns moved outward. The final animated hoop envelope clears both the plinth and the columns; actual BVH overlap checks supplement the analytical envelope.

## References and licensing

See `references.md` for current public inspiration and the official extension/skill check. Reference artwork was not copied, downloaded, or traced. The sculpture, native scene and rendered images are original. No new license is granted for the original artwork, native assets, rendered media or reproduction scripts; their rights are reserved. The repository’s existing site-code MIT license remains separate. Blender's built-in font was used for the native plinth label. No third-party imagery, music or fonts were imported.

A full-timeline projection of the evaluated surface vertices also verified that the sculpture stays within the camera canvas. A first conservative bounding-box test flagged empty corners around the circular plinth; testing the actual mesh surface resolved that false positive. The measured minimum visible-geometry margin is recorded in the framing evidence rather than inferred from a few selected stills.
