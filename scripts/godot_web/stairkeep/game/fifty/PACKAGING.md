# First-chapter source and Web preparation

Use the existing Godot project. The original `project.godot`, main scene, old
three-floor export, 21-floor laboratory, evidence and shared templates stay
unchanged. The coordinator's `prepare_firstchapter_export.py prepare` copies a
bounded production allowlist to a new owned output. Only that copy receives the
preview main scene `res://fifty/view/preview.tscn`, independent preview app name
and Web preset. Its source ZIP includes the portable project, recipes and full
license/source notices, without tests/tools/evidence or private QA reports.

The existing official 4.7.2 no-thread release ZIP is 10,245,903 bytes, SHA-256
`d3ee2f08cef0cf3cf6678a6355a92a8db48ccdd35cbd2e8bfd5f0e8a0b4032a0`.
Selected template and notice bytes are freshly checked against the inherited
whole-archive verification receipt. No download, install or template upgrade is
part of this preparation. MIT engine notices, bundled third-party copyright,
Kenney CC0, pinned official demo MIT and project MIT notices are retained.

The preset uses Compatibility, GDScript, `script_export_mode=0`,
`variant/thread_support=false`, `variant/extensions_support=false`, and PWA off.
Text mode is necessary because the runtime hashes the original `res://*.gd`
bytes. The official 4.7.2 enum assigns Text to 0; the GDScript export plugin
converts other modes to `.gdc`. See the official
[preset enum](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/editor/export/editor_export_preset.h)
and [export plugin](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/modules/gdscript/register_types.cpp).
The complete original `content.json`, including witnesses, is copied byte for
byte. Size reduction must not change authoritative content or rule hashes.

Preparation only copies/checks data. The explicit `export` subcommand and the
Windows-only portable `agent_launch_firstchapter_probe.py` start the
coordinator-provided existing Godot executable. They isolate
APPDATA/LOCALAPPDATA/XDG caches inside the owned
output. The export subcommand uses the verified custom templates and runs headless import followed by
headless Web release export. Thread validation requires the literal HTML
`GODOT_THREADS_ENABLED = false`, exact JS/WASM/worklet bytes from the verified
no-thread template, and parsing every imported/defined WASM memory with no shared
flag. The raw `emscriptenPoolSize=8` / `godotPoolSize=4` defaults remain recorded:
the official exporter writes these hints independently of the thread toggle, so
nonzero hints are not evidence of enabled threads. Extension libraries must be
empty, isolation headers false and PWA/service-worker configuration/files absent.
See the official [Web exporter](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/platform/web/export/export_plugin.cpp).
The recipe retains notices
and rechecks original sources and preset. Nothing is published or served.
Each version/import/export phase uses a hidden BelowNormal process, records
actual WinAPI priority/process times and dynamic private owner receipts, and
requires exit 0 with stderr 0. There is no automatic deadline or process kill;
the coordinator observes progress and owns intervention. Sources and declared
protected files are checked before and after every phase.

The external `probe_firstchapter_pck.gd` has two coordinator-executed phases.
First use the portable launcher to capture real native runtime identities and
complete seed-1 snapshots for both explicit modes from the original project.
Then use its PCK phase to run the original engine with
`--main-pack <new index.pck>` and the external script, from an empty owned working
directory with no source-project `--path`. Godot consumes engine flags before
exposing filtered `OS.get_cmdline_args()`; that filtered list cannot prove the
original launch flags. See [main.cpp](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/main/main.cpp).
The launcher writes an immutable receipt before Popen containing the real argv,
empty-cwd assertion, pack/probe/manifest/wrapper hashes. The helper receives
explicit `--pack` and `--launch-receipt`, validates these bindings, requires an
empty packed resource root and no source fallback, and rechecks receipt bytes
after the complete probe. It never asks the reviewer to invent a launch receipt.
That phase verifies packed raw GD/data/
license/source bytes, confirms the old main scene and QA directories are absent,
exercises explicit mode selection, and compares complete identity/snapshot
results with the real native reference. This prevents a source-project fallback
from being mistaken for PCK validation.

The export-02 pool-hint postcondition failure and export-03 filtered-argv probe
failure are retained with their original measured source archives. They are
validator failures, not passing PCK acceptance or gameplay counterexamples.
The corrected launcher/probe recipes require a fresh measured run; this document
does not declare the upcoming export-04 accepted.

Preparation is not an export receipt. Export and a headless PCK probe are not
browser HTTP play, native pixel/input, CJK glyph, audio or Web storage acceptance.
Floors 1–10 are a first chapter toward a 50-floor target; floors 11–50 are not
implemented. Original concepts are reference images, not new runtime captures.
