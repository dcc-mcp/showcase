# Seismic Lens

A synthetic scalar field becomes three comparable sections, two equal-scale isolines and an editable exhibition plate. ParaView creates the numerical views through typed DCC MCP operations. GIMP imports the five native images, builds five panel groups and nineteen editable text layers, and exports a website preview from a temporary native copy.

This is an analytic illustration with illustrative units. It contains no measured seismic data and supports no physical, geological or engineering inference. The formulas, sampling and tested limits are in `METHODS.md`.

## Open the editable work

- Open `gimp/native/gimp/seismic-lens-master.xcf` in GIMP 3.0.4. The 2560 × 1600 master retains editable text and layer groups. Its adjacent PNG is the qualified full-size reference.
- Open any of the five `.pvsm` files in `paraview/native/paraview/` in ParaView 5.13.2. Keep the adjacent `data/` directory with them; choose it in Load State if requested. Each state contains one of the authored views of the same field.
- The smaller website PNG is a native GIMP preview. It is an output, not the editable master.

The native inputs are unchanged copies of the qualified files. Their hashes, the recipes and selected evidence are listed in the combined manifest. No software binary, font binary, credentials or private execution log is included.

## Reproduce the pipeline

1. Verify the combined archive inventory and the component manifests before use.
2. Follow `paraview/reproduce/BUILD_AND_RUN.md` to build the pinned public adapter, install its stated runtime into an isolated environment, and run the actual MCP authoring recipe against the included VTI. The recipe verifies native geometry, scalar ranges, saved presentation, five image exports and relocated-state reopen.
3. Follow `gimp/README.md` to build the separately pinned GIMP adapter, then run the typed authoring recipe. Supply `paraview/native/paraview/data/synthetic-lens.vti` as the source VTI. The included input images are the exact ParaView outputs. The recipe verifies their pixels, the native layer hierarchy, all nineteen text metadata records and the final XCF/RGBA reopen.
4. Follow `preview/README.md` for the separately qualified native preview increment. Its exact-base adapter patch and reproducible wheel instructions are included; the supplied fixture compares the source and output through real MCP calls.
5. The copied-XCF helper in `gimp/reproduce/` independently opens a new copy, checks the same editable content and compares the full image. Its optional original-path absence test is explicitly scoped; it does not move the operator's files.

Each recipe requires its documented native host, exact source/wheel and runtime versions. A current public commit may have a different identity from an earlier native run. The source-continuity receipts state exactly which content is unchanged; historical trace identities are retained. The work does not imply that the enhanced adapters have been released on PyPI.

## What was actually checked

- Current public ParaView source: 210 SDK events, 52 adapter operations and 36 completed jobs. All 510,705 input points independently satisfy the formulas. Five saved and five relocated views preserve measured presentation and exact PNG bytes without reapplying settings.
- GIMP full composition: 202 events and 45 planned authoring operations. The editable master, full RGBA, imported images and nineteen native text metadata records match after reopen. A separate 42-event trial validates the copied XCF without its declared original input locations.
- Corrected native GIMP preview: 195 records, with 52 successful jobs and one intended non-PNG rejection. The 1600 × 1000 output reopens with identical RGBA; original full-size pixels and measured editable state are preserved. Small transparent fixtures verify no upscaling, aspect rounding and alpha retention.

Events include discovery and polling; they are not all creative operations. PNG container metadata can vary in GIMP, so its image comparison uses decoded RGBA. The original XCF is hash-bound; auxiliary saved checkpoints are not claimed byte-identical. The preview helper’s corrected nested active-image check and bounded cleanup finalizer were rerun in a fresh native02 session; the earlier missing-value comparison is not credited. These checks do not qualify every tool, every platform or cross-machine pixel identity.

## Rights

No additional license or public-domain dedication is granted for this case's artwork, original data, native assets or production recipes. See `RIGHTS.md`. Existing upstream software and font notices retain their own scope and do not relicense the case material.
