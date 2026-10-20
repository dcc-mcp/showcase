# Ecosystem production migration audit — 2026-10-20

Baseline: [main 7f4389e](https://github.com/dcc-mcp/showcase/commit/7f4389e83430a43f53dbb4bd068f4e8fab72e51c).
This is a source/evidence audit, not a new production run or a declaration that
all historical work lacked MCP. The new structural gate currently blocks all
16 selected cases. No old record is rewritten and no live page is removed.

## Why the previous gate allowed this

Production guidance allowed a disclosed direct script fallback, and the optional
production evidence checker was not a publication prerequisite. Pages validated
structure, hashes, provenance/privacy and claim boundaries, not per-stage
production routes. Real Godot calls could therefore coexist with native-only
Blender production. Honest disclosure was necessary but insufficient.

## Full selected-case triage

All 16 selected cases lack the new mandatory ecosystem production graph, so all are publication-blocked by the proposed gate. This is not a claim that all lacked historical MCP. The machine-readable baseline is [ecosystem-gate-baseline.json](ecosystem-gate-baseline.json).

| Case | Existing scoped evidence / remaining review |
|---|---|
| brass-pendulum-denoise | Genuine MCP edits and official dcc-media-enhance documented. Native display transform and FFmpeg delivery route require whole-stage provenance review. |
| houdini-procedural-study | `calls.json`, recipe and replay evidence support typed modeling/render. Shell JPEG derivative production must be accounted for separately. |
| crate-lookdev | Historical source report claims MCP, but complete original calls and adapter/core versions not public. Later film MCP summary is separate, not retroactive proof. |
| painted-wood | Historical Designer MCP claim, incomplete original calls/version evidence; webpage derivatives and generated reference are separately scoped. |
| crystal-freight-native-film | Actual OpenSCAD/Blender/Kdenlive MCP excerpts and separate REAPER score evidence. Verify every original and added derivative/mux/export stage. |
| brass-relay | Actual FreeCAD/Blender/Kdenlive MCP excerpts and later REAPER score; FFmpeg mux/derivatives need route review. |
| seismic-lens | ParaView/GIMP raw evidence exists; recent GIMP review is not a replay of original ParaView creation. Bind exact pinned builds and derivatives. |
| orbit-post-office | GIMP/Godot/Kdenlive case evidence and later REAPER score; verify original route and final FFmpeg mux lineage independently. |
| trail-and-air | Typed gateway workflow and raw MCP excerpts exist; audit per-asset outputs and public derivatives. |
| rainroom-two-hours | Sanitized selected MCP results, not complete raw trace. Verify all rendering/post-production stage scope. |
| resonance-atlas | Native Inkscape CLI/Gateway evidence exists; README explicitly describes Pillow composition and FFmpeg encoding. Those production routes need audit/remediation, not Inkscape attribution. |
| sonic-loom | Typed Godot script/scene evidence exists; direct runtime verification is distinct from production. Audit export/media derivation. |
| prism-tide | Historical `evidence/mcp-calls.json` exists; bind authored project to selected native/web/media artifacts and post-production. |
| orbital-loom | MCP summary exists; full source/call/film stage graph not established in this audit. |
| parcel-switchyard | Actual MCP calls exist; trace native/web/media stages, not just interactive test success. |
| dawnkeep-defense | Confirmed mixed route above: real Godot MCP and direct Blender/GLB preparation. |

Two archive entries outside selected collection also exist: `blender-mcp-gimbal-turntable` and `blender-to-maya-obj`. They are not silently counted among the 16 published selections; the latter explicitly reports direct Maya import after adapter startup failure. A future selection must pass the same gate.


## Migration order and acceptance

1. Stop promoting native-only stages as fully ecosystem-compliant work. Keep
   historical statements and existing public pages unchanged while migrating.
2. Inventory all stages, including mesh/animation preparation, font transforms,
   renders, native/web export, image derivatives, film editing and encoding.
   Read-only decoding, browser input and measurement are separate verification.
3. Map genuine existing raw calls and version-pinned evidence to exact output
   hashes. Do not turn a later review or one successful host call into earlier
   production evidence for a different host or artifact.
4. For confirmed bypasses, use current discovered official ecosystem tools and
   retain a separately dated lineage after authorized re-production. Missing
   evidence is a distinct category and may need recovery rather than redoing work.
5. When a real capability fails, retain the schema/request/result/versions,
   deduplicate the owning issue or Draft PR, and qualify a fix with actual host
   replay. An unavailable session alone is not a missing-feature diagnosis.
6. Independent review must inspect raw invocations/results and complete recipe
   scope. Only then record the review bound to the entire production graph.

Both the structural gate and actual-call review are required. Passing a
self-authored JSON structure cannot authenticate its claims. The initial gate
failure is not to be bypassed for green CI; this Draft must not deploy until
migration and publication authorization are complete.
