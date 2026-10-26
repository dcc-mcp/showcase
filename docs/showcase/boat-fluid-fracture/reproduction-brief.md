# Boat fluid fracture: intended reproduction brief

Status: unselected production draft, recorded 2026-10-26. The following sequence and acceptance conditions describe the complete intended workflow. Source geometry save/reopen and Bgeo round-trip checks passed, while the initial material failure and its later native repair are recorded separately. Final boat destruction, fragment flotation and continuous media remain unaccepted.

1. Authenticate the installed Hyper3D provider, submit the generated reference, and retain the actual generation settings, returned model, textures and hashes. Check output rights separately before redistribution. Do not substitute a hand-built boat while claiming Hyper3D generation.
2. Import the returned mesh into Houdini, measure its bounds and units, and inspect topology, hull thickness, intersections and collision suitability. Preserve the source mesh and make any repair an explicit reproducible stage.
3. Prepare named rigid pieces and glue constraints for the timber hull. Confirm the installed node types and repair the observed constraint authoring failure in the owning adapter before relying on the typed tool.
4. Establish a real fluid domain and a floating intact-boat baseline, then introduce a bounded fluid impact. Transfer measured fluid loading into rigid-body forces or constraint loading. Record the coupling method and its limitations; force-driven fracture must remain distinguishable from a frame-triggered release or animated displacement.
5. Continue the rigid-body and fluid solve after breakage. Compute buoyancy from submerged geometry and the fluid surface, with gravity, mass/density, drag and collisions recorded. Retain the changing waterline and rigid-piece motion through a settling interval.
6. Cache real consecutive frames, save and reopen the native scene, reopen an exported result, and rebuild independently from the recorded recipe. Render and inspect the actual impact and settling motion, then encode a continuous evidence video from those frames.

Acceptance targets:

- The generated model and imported mesh have recorded checksums, units, dimensions and topology measurements; reference dimensions are not treated as recovered measurements.
- The intact boat remains supported by simulated water before impact. The evidence records waterline, immersion and rigid-body state.
- At least one glue constraint breaks in response to measured fluid loading. A comparable control with the impact loading removed establishes whether breakage depends on that loading.
- At least one retained timber fragment remains partially submerged through a declared contiguous settling interval. Measure piece identity, density, submerged fraction, displacement and speed across that interval; do not substitute keyframed floating motion.
- The cache, reopened scene, exported result and independent rebuild have explicit counts, bounds and tolerances. Record failures and numerical differences rather than inferring equivalence from file existence.
- A real consecutive-frame video shows the intact state, impact, breakage and later flotation. Decode and review the delivered video, then test the actual gallery media and resource links in both supported languages before claiming public delivery.

Current recovery state: Hyper3D authentication, Rodin generation, Bang splitting, native import with UVs and the constraint-relationship repair have completed. Independent source geometry HIP and Bgeo acceptance passed. The initial portable diffuse binding failed; a later importer candidate passed native diffuse/scalar and save/reopen checks, with its limited scope retained. The independent cube control demonstrates a fluid-feedback response. A blank-scene recipe rebuild passed its first two cached frames with exact geometry/particle comparisons, and its reopened first-frame render matched production's decoded float RGB pixels. Full-sequence equivalence remains untested. The first boat diagnostic retained all parts attached and failed its fracture target. A later final solve and native render batches remain in progress; partial released-part counts do not accept a finished result.

`acceptance-requirements.json` lists the remaining terminal evidence. Keep the case outside `collection.json` until the root owner accepts final media and the measured flotation interval. Browser QA is separately blocked: the official DCC-CUA 1.12.2 owned-browser route refused the elevated runtime before returning any PID/HWND; no UI observation or input occurred. A generic browser route must not substitute for that acceptance.
