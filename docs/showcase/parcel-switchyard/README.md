# Parcel Switchyard: typed MCP authors a playable three-destination sorter

Native screenshot pending: this is an unselected draft, not a visually accepted gallery entry.

A self-contained Godot parcel sorting game with two incoming lanes, three destinations and a six-parcel capacity. Typed gateway calls created, attached and saved the native project; deterministic native execution checked routing, mistakes, keyboard controls and repeated reset. Local pixel rendering is blocked, recorded as a failure rather than a blank success.

[Project](native/project.godot) · [Scene](native/main.tscn) · [Game source](native/parcel_game.gd) · [Export preset](native/export_presets.cfg) · [MCP calls](evidence/mcp-calls.json) · [Logic tests](evidence/logic-tests.json) · [Rights](LICENSES.md) · [Validation](validation.json) · [Manifest](manifest.json)

## What was measured

See validation.json for every observed count and result. Actual request/response evidence identifies gateway routing and host return values. Source bodies in those records are represented by hashes; the final editable source is included. Empty bootstrap project creation and portable packaging were filesystem operations, not MCP calls.

## Reproduce

Open native/project.godot with the recorded Godot version. Press a numbered key or click a destination; press Space or Send parcel to dispatch. A toggles automatic dispatch. R resets the shift. Match each parcel label to its destination. The selected route is latched when dispatching.

Run `godot --headless --path native -- --test` for bounded deterministic checks. Run `godot --path native -- --demo` for the animated demonstration. The portable copy excludes adapter code, install receipts and user cache. To reproduce authoring, install the official Godot adapter into a separate copy, verify matching project identity, discover/load/describe typed script and scene tools, apply the included source, and save the scene.

## Boundaries

Local render_scene_preview correctly rejects the headless dummy renderer. Xorg cannot open local Unix sockets in this cloud sandbox. This draft requests real native captures on a normal CI runner before gallery selection. No screenshot, video, visual approval, mouse acceptance or packaged executable is claimed yet. Native art is drawn by editable GDScript rather than separate scene meshes. No private project or third-party artwork is included.
