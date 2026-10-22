# Seismic Lens: GIMP native media and reproduction

This package contains the unchanged qualified 2560 × 1600 GIMP master XCF, its reference PNG, five exact ParaView-rendered input PNGs, a relative input manifest, selected evidence, and public reproduction/proof helpers. The XCF has 19 editable text layers and five independent panel groups. It is an analytic illustration, with illustrative units; it is not measured seismic data or a validated physical model.

The 206-event original composition is retained only as historical reference in `evidence/selected-gimp-receipt.json`. The acceptance basis is the two fresh runs below, both using ordinary environment-aware HTTPX defaults. A separate copied-path native trial passed 42 MCP events while original master/input locations were held aside; all six original file hashes were restored afterward. A fresh full-authoring run passed 45 planned operations and 202 MCP events, produced a byte-identical XCF, and passed its own reopen/pixel/metadata checks. Selected, hash-bound projections are in `evidence/selected-copied-xcf-proof.json` and `evidence/selected-public-full-authoring.json`. An independent comparison also confirms all reference RGBA pixels, exact XCF bytes, 19 saved text parasites, the canonical tree and complete reopened metadata; see `evidence/independent-fresh-native-qualification.json`. These trials used the sealed v1 recipe/media bytes; this v3 copy preserves those recipe/media bytes and adds documentation/evidence. The separately recorded binary review is projected in `evidence/selected-binary-review.json`: exact master bytes passed the pattern audit, and one input-PNG raw-byte match was structurally resolved as compressed pixel data. The native PNG retains its generated timestamp and its own 256 × 160 thumbnail. This bounded evidence is not a mathematical guarantee of absence; visual/publication approval remains separate.

## Contents and rights

- `native/gimp/seismic-lens-master.xcf`: actual native master; SHA256 `8efc1515de37d6e917d0b55bdfa24a8c9faae087f2cbe63b60d0f1aa1c7c09e5`
- `native/gimp/seismic-lens-master.png`: original reference export; SHA256 `43962deba479131f476baaa7c33854292f5d36404420e0c5804c72fbad288594`
- `inputs/`: five byte-bound native input PNGs, canonical relative input manifest, and clearly identified selected ParaView receipt projection
- `evidence/qualified-master-baseline.json`: canonical native layer tree and complete qualified load-time metadata, with original inspection/qualification hashes
- `reproduce/`: authoring recipe, copied-XCF proof, lifecycle, PNG decoder, bounded read-only XCF parasite helper, exact source/package pins, and package integrity checker
- `notices/`: explicit artwork/data rights reservation and DejaVu font notice

No adapter source tree, adapter wheel, font binary, raw MCP trace, private runtime directory, or VTI is distributed in this GIMP portion. The companion ParaView native package supplies the VTI. No new artwork/data license is granted. See `notices/RIGHTS.txt` and `notices/DejaVu-font-notice.txt`.

## Runtime prerequisites

Use GIMP 3.0.4 on a normal Linux desktop with DISPLAY, Python 3.12, DejaVu Sans Book (or the discovered native DejaVu Sans name), Core/server/CLI 0.20.41, SDK `mcp` 1.30.0, and the exact dcc-mcp-gimp 0.4.1 candidate. This is a candidate-specific reproduction requirement, not a claim that an arbitrary 0.4.1 release is equivalent. The separately supplied official software source must match all 67 paths and SHA256 values in `reproduce/adapter-source-files.json`; the wheel must match SHA256 `80833767f5ff1fe754bff0de67143f053f60bb5443153c21c96d678265560853`. The 41 adapter files are additionally compared across source, wheel and installation. The recorded local qualification commit `5602aa523d58a2c685966a06c90b71279a0bcfab` and tree `abfd40f62533cf652d767c00781605725c0ce98b` identify historical evidence; they are not public checkout instructions. The recipe validates file content rather than the supplied checkout HEAD. The actual public PR and merge have different commit identities with the same qualified files. The unchanged recipe’s `source_commit` field retains the original qualification label; the public provenance document records the actual public checkout identity. Installed import-shadowing files, symlinks and special nodes are rejected. Existing recognized bytecode is checked against compiled bound source, and native execution uses a fresh empty bytecode lookup prefix with cache writes disabled. The fix is publicly merged in [PR #14](https://github.com/dcc-mcp/dcc-mcp-gimp/pull/14). Use [merged source ea9270a82bd0821993f0c611d9cad2d36e06405d](https://github.com/dcc-mcp/dcc-mcp-gimp/tree/ea9270a82bd0821993f0c611d9cad2d36e06405d). Its Git tree is exactly `abfd40f62533cf652d767c00781605725c0ce98b`, identical to both the reviewed public PR head `e24f1a8e3fa4b418b7fa27e7a33dee45ccca5cde` and historical qualified source. All 67 files and all 41 source/wheel/installed adapter identities match; runtime, tests and documentation each have zero differences from the qualified candidate. See `reproduce/public-source-provenance.json` and `evidence/public-source-equivalence.json`.

An exported source snapshot is sufficient: the scripts do not require a local Git commit or a particular private filesystem path. They verify the pinned full source inventory and all 41 candidate module bytes across source, wheel, and the active interpreter's installed adapter. Source files are read only. Install prerequisites through the official software workflow before running these scripts; they never install or download software.

The complete qualified Python environment version list is recorded in `reproduce/qualified-runtime-versions.txt` for reference.

Run commands with `python -B` from the intended Python environment. Preserve the public package files and verify `package-manifest.json` against the trusted delivery hash. Paths below are placeholders chosen by the operator.

## Obtain the verified public source

Create a separate checkout from the public repository and select the immutable merged commit:

```sh
git clone https://github.com/dcc-mcp/dcc-mcp-gimp.git gimp-source
git -C gimp-source checkout --detach ea9270a82bd0821993f0c611d9cad2d36e06405d
```

Use that checkout as `--source-root`. A complete source archive of the same commit is also accepted because validation uses content hashes. The source tree and wheel remain separate software prerequisites and are not embedded in this media package.

## Rebuild the exact candidate wheel

Fresh isolated builds from both the original complete source snapshot and the actual public merged source reproduced all 91,033 qualified wheel bytes exactly, with 46 identical archive members. No network was used, and no frozen source/runtime was edited. `evidence/selected-wheel-rebuild.json` records the source-manifest hash, tool versions, result and raw-receipt hashes.

The demonstrated build used Python 3.12.14; Hatchling 1.32.4; packaging 26.3; pathspec 1.1.1; pluggy 1.6.0; tomlkit 0.15.1; trove-classifiers 2026.9.21.13; and `SOURCE_DATE_EPOCH=1580601600`. Exact versions and zlib versions are also in `reproduce/wheel-build-tool-versions.json`. Use a fresh build environment with these tools already installed, or obtain them separately through the official package registry. The test populated its fresh environment from existing qualified local distributions and rejected all Python socket events while building.

Make a new copy of the verified complete source, create a new empty wheel output directory outside that source, and run the backend from the source copy. Replace the example paths:

```sh
cd /path/to/new/verified-source-copy
SOURCE_DATE_EPOCH=1580601600 PYTHONDONTWRITEBYTECODE=1 \
  /path/to/fresh-build-env/bin/python -B -c \
  "from hatchling.build import build_wheel; print(build_wheel('/path/to/new/wheels'))"
```

The expected file is `dcc_mcp_gimp-0.4.1-py3-none-any.whl`, SHA256 `80833767f5ff1fe754bff0de67143f053f60bb5443153c21c96d678265560853`. The authoring/proof checks enforce this digest and the source/module bindings; do not drop these checks if a different build does not match. The PR publisher also reported a separately built wheel with SHA256 `0c851dda96e69a6e35803c39093a121b371332f447e276f5a22b745283e3b85b`; those packaging bytes differ and are not accepted by this recipe. Build with the documented versions/epoch to obtain the exact qualified `80833767...` wheel. This package contains the build instructions and pins, not the software wheel or source tree.

## Reproduce all native authoring

First check without launching GIMP:

```sh
python -B reproduce/reproduce_gimp.py --check \
  --source-root /path/to/exact/official/source \
  --wheel /path/to/exact/dcc_mcp_gimp-0.4.1-py3-none-any.whl \
  --source-vti /path/to/paraview-package/native/paraview/data/synthetic-lens.vti
```

Then replace `--check` with `--run` and add `--run-root /path/to/new/gimp-authoring-run`. The root must not exist. The 45 planned authoring operations use real discovered typed MCP tools, preserve source/manifest validation, compare all five imported RGBA panels, save/reopen the XCF, verify all 19 saved text parasites and full pixels, and close owned clean images. Reproduced PNG byte identity is not promised: decoded RGBA is the comparator.

## Verify the packaged XCF at a copied path

```sh
python -B reproduce/verify_copied_xcf.py --check \
  --source-root /path/to/exact/official/source \
  --wheel /path/to/exact/dcc_mcp_gimp-0.4.1-py3-none-any.whl
```

For native verification replace `--check` with `--run` and add a fresh `--run-root`. The helper copies the packaged XCF into that run root and opens only that copy through typed MCP. It compares the qualified canonical tree and complete load-time metadata, exports and compares all 4,096,000 RGBA pixels, verifies all 19 saved native text parasite byte hashes, saves a separate checkpoint only if the owned image became dirty during export, and clean-closes it. It never edits the packaged XCF.

If the operator has already held original master/input locations aside, add `--originals-absent-json /path/to/operator-list.json`. This private JSON is a nonempty array of absolute original locations. The helper only asserts those paths are absent before launch, before each MCP request, and after native work. It never renames or restores anything. A native result with no absence list explicitly does not claim an originals-held-aside test. The operator is responsible for a separately reviewed hold-aside/restoration procedure.

## Lifecycle and evidence boundaries

Both paths use one owned GIMP, two allowed CPUs, ephemeral in-memory/environment auth, loopback listeners, gateway port 0, disabled gateway failover, 600-second total native deadline, 256 MiB aggregate stopping threshold and 1 GiB minimum free space. The threshold is not a filesystem quota. Cleanup uses only normal SIGTERM to the owned Popen host and bounded observation; there is no force-kill or system-policy workaround. Run roots are explicit and private, and raw traces stay there. Do not publish an entire run root.

Public evidence is a selected projection, not the raw evidence. Original qualification/inspection/trace/ParaView-receipt SHA256 values are preserved in the selected documents. The public input manifest binds the selected ParaView projection's own hash and separately identifies the original raw receipt hash. Public package hashes cover the final distributed media, recipes, notices, and selected receipts.

## Component integration

This directory is a self-contained GIMP media/reproduction component. It may be copied unchanged into a combined delivery as `gimp/`; its relative paths and package-integrity contract remain valid. Supply the companion `paraview/` component’s VTI through `--source-vti`. Preserve every component file and its manifest; previews or additional software features belong to separate components.
