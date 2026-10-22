# Prism Tide: bounded native repair qualification

This candidate uses the official Godot MCP editor-script and play-scene tools.
It does not claim that the historical movie or PCK was produced through MCP.
The existing five source files are frozen in source-inputs.json and are not edited.

The hosted job uses Godot 4.6.3 stable official Linux x86_64, Core 0.20.46,
and the explicit unmerged Godot adapter candidate 0c99ee85. Its wheel and
installed payload are checked against their frozen hashes. Pillow 13.0.0 is
available from official PyPI; the Linux CPython 3.12 wheel is hash-locked.
Local lifecycle tests ran with the local Python environment, not that hosted
Pillow installation.

Production is limited to:
1. A three-frame qualification through native Movie Maker, followed only on
   success by the original 450-frame, 30 fps demo at 1280 x 800.
2. A native PCKPacker source pack containing exactly the five original files.

Each capture requires a real matching child process, normal writer completion,
exact frame inventory, and complete independent PNG decoding. The source-packed
PCK is independently reopened by the native engine with the original 17 checks.
That reopen is acceptance, not a production CLI fallback. It is not a preset
export and does not imply support for arbitrary imported project resources.

No MP4, new hero, or whole-case compliance is claimed by this job. Encoding and
visual review remain separate real production/acceptance stages. No successful
native execution has occurred when this candidate is first introduced.

The owned editor and every observed Movie Maker runtime have explicit cleanup.
Unknown process state is not treated as exit. Failure artifacts are retained on
ordinary job failure and best-effort cancellation; runner destruction cannot be
guaranteed to preserve artifacts. Raw hosted artifacts require a later public
privacy review before inclusion in the Showcase site.

Run host-free checks with: python scripts/prism_ecosystem/test_lifecycle.py
Only the manually selected prism_native_repair workflow input runs native work;
the ordinary site workflow and its fail-closed ecosystem gate are unchanged.
