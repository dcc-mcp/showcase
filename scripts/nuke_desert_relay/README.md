# Desert Relay: prepared assets, awaiting native Nuke production

This directory is a preproduction package. The eight-second live-action excerpt,
two actual ImageGen outputs and an existing CC0 sword are included. No Nuke or
Blender session has run for this case, and no final composite is supplied.

- [Shot design and native verification recipe](../../docs/showcase/nuke-desert-relay/RECIPE.md)
- [Current measured evidence](../../docs/showcase/nuke-desert-relay/validation.json)
- [Exact plate candidates and copyright research](plate-candidates.json)
- [Plate/encoding measurements](plate-analysis.json) and [offline motion analysis](motion-analysis.json)
- [Actual sky generation](generation-sky.json) and [actual ruins generation](generation-ruins.json)
- [Asset reuse audit](asset-reuse.json), [source notices](LICENSES.md)
- [Nuke builder](build_nuke.py), [Nuke preflight contract](TEMPLATE-NOTES.md), [Blender scene builder](build_prop_scene.py)

The generated ruins have red/yellow edge contamination. They require actual
Nuke alpha/premultiplication and edge-color work before acceptance. They are
retained unchanged as a source candidate. The sky and ruins are raster layers,
not generated geometry. Codex orchestrated the image tool; its backend model
identity and remaining image quota were not returned.

Only execute the native builders after a fresh task-owned instance, valid
software entitlement and a serial resource window have been assigned. Discover
current official DCC-MCP tools and schemas; these filesystem scripts are not
evidence that a typed host call occurred. Never substitute an existing shared
host, change gateway locks/ACLs, bootstrap components or add Hyper3D requests.

`prepare_plate.py` and `analyze_motion.py` are ordinary offline media preparation
and analysis. Reproduction needs the exact original NPS source hash recorded in
`plate-analysis.json`; the original full-length video is linked rather than
duplicated. OpenCV is optional and was already installed for this analysis.

The film is planned at 1280×720, 30 fps, frames 1–240. The foreground 3D insert
may deliberately hold one rendered frame while the original plate and Nuke
atmosphere change over time. This would be an offline composite, with no claimed
3D animation, live simulation, real-time interaction or solved camera.
