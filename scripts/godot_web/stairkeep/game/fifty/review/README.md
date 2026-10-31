# First-chapter source and Web review candidate

This candidate contains the original floors 1–10 toward the 50-floor target.
Floors 11–50 are not built. The default original project/three-floor entry and
historical 21-floor fixtures remain separate and unchanged.

[Source ZIP](firstchapter-source.zip) · [Web ZIP](firstchapter-web.zip) ·
[Inventory](manifest.json) · [Native probe](native-probe.json) ·
[PCK probe](pck-probe.json) · [Export](export.json) ·
[Native-evidence independent review](independent-native-evidence-review.json) ·
[Full native evidence](../evidence/native-evidence.zip) · [Licenses](licensing.json)

The source archive is the exact measured source package. Its Windows-only
portable launcher records original argv, isolated user data, actual BelowNormal
priority and an immutable PCK launch receipt. Export uses Compatibility,
GDScript Text, the verified official 4.7.2 no-thread template, no extensions/PWA.
Raw pool hints 8/4 are retained. Literal thread support false, exact official
JS/WASM bytes and all unshared WASM memory declarations provide the static
thread proof. Both explicit modes' complete seed-1 snapshots match actual native
and PCK execution. Phase-owner summaries omit host paths and PIDs.

These checks are not real browser play, rendered pixel/input acceptance, CJK
glyph/audio acceptance or durable Web storage acceptance. The native/PCK probe
runs the original native engine against the exported data, not WebAssembly in a
browser. Browser persistence remains explicitly blocked by the game.

For a future authorized manual HTTP review, extract the Web ZIP and run:

    python -m http.server 8000 --bind 127.0.0.1 --directory extracted-web

Then manually open http://127.0.0.1:8000/. This is documentation only: packaging
did not start a server/browser, publish or deploy. A successful download/HTTP 200
is not gameplay acceptance. Source ZIP recipes are in `recipe/`; they need an
existing authorized Windows Godot 4.7.2 executable and verified local templates.

`history/` preserves validator failures 02/03/04 and their original source ZIPs.
They are not passing PCK probes or gameplay counterexamples. Historical GD is
compressed as text, not installed as another global script class. Raw/current
receipt hashes and archive-root member inventories are recorded in the manifest.
