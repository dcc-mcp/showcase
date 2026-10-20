# Dawnkeep: isolated ecosystem asset repair

This is a **Draft repair package**, not a replacement for the deployed game or a
whole-case ecosystem certification. It contains nine newly reconstructed original
assets. Historical native-only recipes, receipts, attribution and live assets are
unchanged. Nothing here is copied into the playable build by this change.

## Rights and provenance

Copyright 2026 dcc-mcp contributors, **all rights reserved**, under
[the case notice](../../LICENSES.md). The general repository MIT license does not
cover these original models or production recipes. These nine models do not
contain KayKit models, textures, animations, audio or font data. Do not label them
CC0, MIT, a third-party work, or as newly attributed to a model identity.

The geometry follows the existing [original recipe](../build_dawnkeep.py), SHA-256
`3769bfe07a1d8b44a5ac796632a4e360a95a6b1e3b95c320f6e8ee5f49298dd4`,
seed 18026. Original design and historical native-only production remain recorded
in [the art README](../README.md) and [art rights](../../ART-LICENSES.md).
This new run used Blender 4.5.13, official dcc-mcp-blender 0.2.22 and
core 0.20.46 through the connected official host, not Blender CLI production.

## Actual production and scope

1. An explicitly disclosed official in-host script calculated the unchanged
   numerical recipe using `mathutils`. Its in-memory collectors did not create
   native scene objects, read old GLBs, export, render or launch subprocesses.
2. A fresh empty scene was checked. Typed tools created 30 materials and 64 meshes,
   assigned material slots, set material properties, exported nine GLBs, restored
   display offsets and saved a native scene. Construction used 341 real calls.
3. One narrow official in-host script assigned per-face material indices after
   checking every object's topology, slots and index bounds. This is **not fully
   typed coverage**. The confirmed missing typed operation has a minimal test in
   [Blender issue #316](https://github.com/dcc-mcp/dcc-mcp-blender/issues/316).
4. A separate reviewer performed an actual new-scene/open-saved-scene sequence
   and read-only verification: 64 meshes, 3,674 vertices, 2,655 faces, 30 materials,
   exact polygon indices/material assignments and expected world transforms.
   This is an independent reviewer and fresh scene reopen in the same official
   Blender host, not a newly launched process.
5. Each of the nine new GLBs was really imported into its own empty scene through
   typed import. Read-only verification checked exact object names, world-space
   vertex point sets and material presence. It does not establish triangulation
   identity or rendered appearance. Offline GLB checks complement this by checking
   geometry against the numerical recipe and PBR material values against old GLBs.

The first native verifier wrongly required non-emissive colors to be black.
Actual defaults were white with zero strength, consistent with the original
recipe. That failed check was retained; the verifier was independently corrected
to require zero emission strength and then passed. Emissive materials still
require both the expected color and strength. No production asset was changed to
satisfy this correction.

## Evidence and remaining work

[Stage evidence](stage-evidence.json) binds the delivered bytes and readable
receipts. The ordered call ledger is a public-safe summary, not a raw private
transcript or a cryptographic backend attestation. Detailed private execution
records are retained separately; private paths, endpoints and task identifiers
are not published. The saved native file is retained but not delivered here
because it embeds machine-specific paths; its hash is recorded without claiming
that a reader can reopen an omitted file.

Passed: real production; saved native reopen; actual nine-asset GLB reimport;
numerical geometry and material-value comparisons. Not tested: new visual renders,
composition, animations, game integration, browser interaction, physical devices.
No render was made in this run. Historical screenshots/gameplay cannot accept
these new bytes. See [remaining migration](MIGRATION.md) before any live replacement.

## Reproduction using the official ecosystem

`recipes/recipe-data.json` is the exact numerical output of the actual run.
The parameterized script copies differ only in how local paths are supplied;
they are not misrepresented as a new executed run. First discover/verify the
installed official tool schemas and required skills. Do not start a parallel host
or replace typed calls with a native CLI.

- Execute `calculate_recipe_data.py` using official `execute_python`, with context
  `source_recipe_path` pointing to the original recipe and `recipe_data_path` to a
  fresh output file. Compare its SHA-256 with the supplied numerical data.
- `python recipes/build_tool_plan.py <absolute-package-directory>` emits the
  ordered construction plan. It makes **no calls**. Use the connected official MCP
  client, a fresh `output/` directory and one exclusive scene owner. Check each
  real success envelope and stop on any error/uncertain result; never replay an
  uncertain mutation. Require empty scene after `get_scene_info`, and require
  `report.passed` plus complete material resource checks after validators.
- Reopen the saved scene with typed `open_scene`, then execute the read-only
  verifier with `evidence_directory` containing the exact `recipe-data.json`.
  For each GLB, typed new/import followed by `verify_imported_group.py` with
  `group` and `evidence_directory` verifies its bounded import contract.

The plan uses official in-host `execute_python` for the face-index script rather
than the original execution's `execute_script_file`; both are disclosed script
operations, not typed face assignment. This portable plan needs an independent
connected-host replay before it can be called a newly verified reproduction.
