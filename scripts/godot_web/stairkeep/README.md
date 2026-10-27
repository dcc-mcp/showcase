# Stairkeep / 阶塔 — working title, renameable

A new, isolated three-floor isometric tower slice. Open `game/project.godot`
with the existing Godot 4.7.2 standard editor. Rendering is Compatibility;
all gameplay is GDScript. No C#, GDExtension or downloaded executable plugin.

This is an original grid/resource game built on the official Godot isometric
demo's projection and character animation, with a selected Kenney environment
pack. The official demo is a component, not a complete tower game. The original
showcase projects, shared 4.6.3 Web runtime and gallery selection are untouched.

## Play

Begin expedition, then use WASD or the on-screen NW/NE/SW/SE compass. The logical
grid has four neighbors. Click an adjacent tile to interact; hover or select a
distant object to inspect it. Approach walks through clear tiles and stops at
an encounter. Press E on a stair landing to travel back. Escape opens the menu.

Read the HP cost before fighting. You strike first; the final enemy does not
retaliate after being defeated. A fight is permitted only when the hero retains
positive HP. Armor that cannot be penetrated is explicitly blocked. The exact
same `combat()` result is used for inspection and actual resource deduction.

Yellow and blue keys open one matching gate. Open gates, defeated foes and
collected items remain changed when returning to another floor. The forge sells
limited attack, defense and healing stock. Resource ordering matters: spending
health before upgrading can exhaust a run. Save before committing; Load restores
the manual save, and Restart starts over without deleting that save. A blocked
fight never spends health or keys. Some resource choices are losing strategies;
the simulation report includes concrete counterexamples.

This candidate targets a 1280 × 800 desktop composition. Portrait phone layout,
physical devices, browser input and IndexedDB persistence are not accepted yet.
The slice intentionally has no sound. English is the current gameplay UI;
Chinese design/source metadata is retained. Full game localization is pending.

## Reproduce

```text
godot --headless --path game --script res://tests/test_rules.gd
godot --headless --path game -- --layout-test
godot --headless --path game --script res://tests/simulate.gd -- --runs=10000 --seed=20261025
```

Use an isolated user-data directory for QA. Tests exercise real rule actions;
they are instrumented headless tests, not human keyboard/mouse acceptance.
[Web build](WEB-EXPORT.md), [simulation](SIMULATION.md),
[21-floor design](CAMPAIGN-21-DESIGN.md).

The downloadable Web candidate must be extracted and served over HTTP, for
example `python -m http.server 8741 --bind 127.0.0.1` from its folder, then opened
at `http://127.0.0.1:8741/`. Do not use `file://`. It contains the actual official
Godot WebAssembly runtime and exported pack, with threads/extensions/PWA off.
It has not been run in an actual browser under the current host restrictions.

## Rights and reuse

- Official Godot demo: MIT, tag `4.7-6ad6167`, commit
  `6ad6167e0577fe3622c18546138f456b107ce93c`. Retained notices and per-file
  adaptation/hash records are in `game/vendor/godot-isometric/`.
- Kenney Isometric Miniature Dungeon: downloaded package identifies itself as
  Dungeon Pack 2.3, CC0. Ten selected, unedited PNGs plus its actual License.txt
  and hashes are in `game/assets/kenney/`.
- Godot runtime 4.7.2: MIT plus bundled third-party notices, retained in
  `notices/godot/`. [Template source/hashes](TEMPLATE-SOURCE.json).
- Bespoke rules, HUD symbols and level layout: repository MIT license.
- Review concept art is AI generated via built-in ImageGen, not a screenshot or
  a Kenney/Godot asset. It illustrates a direction; it does not prove final art.

No copied commercial tower maps, uncleared clones, paid assets or Hyper3D assets
are included. No software was installed. No merge or live deployment is part of
this candidate. See the showcase case report for measured outcomes and gaps.
