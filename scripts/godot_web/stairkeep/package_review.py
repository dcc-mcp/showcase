#!/usr/bin/env python3
"""Package only this isolated candidate and measured, public-safe evidence."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASE = REPO / "docs/showcase/stairkeep"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def log_json(path):
    return json.loads(next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("{")))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    candidate = args.candidate.resolve()
    evidence = args.evidence.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("Preserve existing review bundles; choose a new output name")
    export = json.loads((candidate / "export-provenance.json").read_text(encoding="utf-8"))
    for row in export["sources"]:
        path = HERE / "game" / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise SystemExit("Source no longer matches exported candidate: " + row["path"])
    for row in export["files"]:
        path = candidate / row["path"]
        if not path.is_file() or path.stat().st_size != row["bytes"] or sha(path) != row["sha256"]:
            raise SystemExit("Candidate bytes differ: " + row["path"])
    rules = log_json(evidence / "rules-final.log")
    layout = log_json(evidence / "layout-final-02.log")
    simulation = json.loads((evidence / "simulation-10000.json").read_text(encoding="utf-8"))
    if not rules["passed"] or not layout["passed"] or simulation["invariant_errors"]:
        raise SystemExit("Required headless invariants failed")
    if simulation["source_data_sha256"] != sha(HERE / "game/data/levels.json") or simulation["rule_source_sha256"] != sha(HERE / "game/scripts/rules.gd"):
        raise SystemExit("Simulation does not bind current rules/content")
    CASE.mkdir(parents=True, exist_ok=True)
    write_json(CASE / "rules-checks.json", rules)
    write_json(CASE / "layout-checks.json", layout)
    shutil.copyfile(evidence / "simulation-10000.json", CASE / "simulation-10000.json")
    shutil.copyfile(candidate / "export-provenance.json", CASE / "export-provenance.json")
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    failed = sum(row["dead_end"] for row in simulation["policies"].values())
    won = sum(row["won"] for row in simulation["policies"].values())
    validation = {
        "schema_version": 1, "recorded_at": stamp,
        "environment": {"engine":export["engine"], "engine_binary":export["engine_binary"], "renderer":"Compatibility", "language":"GDScript", "web_threads":False, "native_viewport_px":[1280,800], "route":"existing editor CLI, headless", "adapter":"not used / no typed MCP claim", "core":"not used / no gateway claim"},
        "counts":{"floors":3,"objects":34,"rule_checks":len(rules["checks"]),"projected_cells":len(layout["projection"]),"hud_resource_symbols":6,"simulation_runs":simulation["completed_runs"],"unique_sequences":simulation["unique_decision_sequences"],"combat_comparisons":simulation["combat_preview_actual_comparisons"],"wins":won,"resource_dead_ends":failed},
        "checks":[
            {"name":"native deterministic rules and four strict route budgets","result":"pass","observed":{"checks":len(rules["checks"]),"remaining_hp":[49,78,20,85]},"evidence":"rules-checks.json"},
            {"name":"native projection and settled desktop control bounds","result":"pass","observed":{"roundtrips":len(layout["projection"]),"inspector_compass_overlap":layout["inspector_compass_overlap"]},"evidence":"layout-checks.json"},
            {"name":"real official single-thread Web export","result":"pass","observed":{"runtime_members":len(export["runtime"]),"threads":False,"source_hashes_match":True},"evidence":"export-provenance.json"},
            {"name":"multi-policy real-core invariants","result":"pass","observed":{"runs":simulation["completed_runs"],"preview_comparisons":simulation["combat_preview_actual_comparisons"],"invariant_errors":0},"evidence":"simulation-10000.json"},
            {"name":"all sampled resource orders can win","result":"fail","expected":{"wins":simulation["completed_runs"],"dead_ends":0},"observed":{"wins":won,"dead_ends":failed},"evidence":"simulation-10000.json","interpretation":"Planning failures are retained, not silently balanced away. No universal solvability claim."}
        ],
        "stage_status":{"native_import":"passed","native_rules":"passed","native_scene_geometry":"passed","web_export":"passed","native_pixels":"blocked","native_real_input":"blocked","web_http_browser":"blocked","physical_mobile":"not-tested","sound":"not-tested / intentionally silent","full_21_floor_campaign":"not-implemented"},
        "not_claimed":["Rendered native gameplay screenshots, animation/occlusion or subjective visual acceptance", "Human/native or actual HTTP browser input and IndexedDB persistence", "Typed DCC-MCP execution, gateway routing or automated provider install", "Every reachable resource state is solvable; the sampled counterexamples are real", "21 implemented floors, hours of measured play, death/mirror/respawn or save-v2", "Mobile/portrait localization or physical-device performance", "Publication, deployment, merge or release"]
    }
    write_json(CASE / "validation.json", validation)
    attribution = []
    for stage in ["planning","creation","code","reference","post_production","review_technical","review_visual"]:
        attribution.append({"stage_id":stage,"stage":stage.replace("_"," "),"model":"Unknown","reasoning_effort":"Unknown","record_status":"unknown","basis":"No accepted public-safe configuration receipt retained for identity attribution.","scope":"Current candidate; no model identity inferred from self-description."})
    write_json(CASE / "model-attribution.json", attribution)
    write_json(CASE / "review-status.json", {"recorded_at":stamp,"status":"draft candidate","selected_in_collection":False,"gallery_or_play_manifest_changed":False,"browser":{"status":"blocked","action":"Run exact exported game over loopback HTTP with real pointer/keyboard input","target":"stairkeep Web candidate","reason":"Coordinated host/browser window is not currently authorized; existing desktop/browser restriction is retained","outcome":"not attempted"},"next":"Review native pixels and actual browser first; resolve sampled losing-route UX/balance, then implement the 21-floor design."})
    (CASE / "README.md").write_text('''# Three floors share one deterministic combat rule

![AI-generated visual concept, not a native gameplay screenshot](concept.jpg)

**Draft candidate — 阶塔 / Stairkeep is a working title and can be renamed.**
The native Godot slice has 3 floors and 34 fixed objects. Its 42 rule checks and
34 projection round-trips passed. The actual Compatibility/GDScript Web export
uses the verified official single-thread runtime. Native pixels, real input and
HTTP browser acceptance remain blocked. The image above is concept art only.

[Native project](../../../scripts/godot_web/stairkeep/game/project.godot) ·
[Recipe and controls](../../../scripts/godot_web/stairkeep/README.md) ·
[Rules](rules-checks.json) · [Layout](layout-checks.json) ·
[Simulation](simulation-10000.json) · [Export](export-provenance.json) ·
[Validation](validation.json) · [Manifest](manifest.json) ·
[Review status](review-status.json) · [Attribution](model-attribution.json) ·
[Concept prompt](concept-prompt.txt) · [Repository checks](repository-checks.json) ·
[Technical review](technical-review.json)

## What ran

The existing Godot 4.7.2 editor imported the licensed native source, ran the
headless scene and exported a real WebAssembly build. Tests cover a key consumed
once, repeated/opened gates, bidirectional stairs, cleared floor state,
preview equal to HP spent, armor/HP impossibility, finite shop stock and strict
save/load/reset with invalid-save rejection. Four full routes replay every
resource ledger event and finish with 49, 78, 20 and 85 HP.

The scene test measured settled native Control rectangles at 1280 × 800 and
round-tripped all object cells through the reused official TileSet projection.
This is a geometry check after Container sorting, not a rendered visual review
or an input test. The native HUD uses one six-symbol stroke system and Theme.

## Resource choices have consequences

The real GDScript rules ran 10,000 seeded simulations across five policies,
yielding 7,970 different decision sequences and 69,968 combat comparisons with
zero preview/resource invariant errors. There were 9,980 wins and 20 exhausted
resource states, all in the randomized policy. The report retains a complete
counterexample: fighting before buying attack spends health inefficiently, then
limited healing stock runs out before the warden. No currency or merchant stock
was silently changed to turn this into a perfect score. Save/reload/restart is
available; explicit losing-route explanation and balance review remain needed.
The sample is not a proof over every state or a substitute for the planned
21-floor solver/seed acceptance gate.

## Reuse and visual direction

The official MIT isometric demo is pinned to commit
`6ad6167e0577fe3622c18546138f456b107ce93c` (Godot 4.7 tag). Its real TileSet
projection and goblin SpriteFrames are used. Ten unchanged Kenney CC0 PNGs form
the sandstone environment and wanderer. New native systems supply the grid,
floor persistence, keys/gates, forge, resource decisions, combat and saves.
Retained notices, exact source hashes and modifications are in the
[project source](../../../scripts/godot_web/stairkeep/README.md#rights-and-reuse).

The AI-generated concept establishes ink-blue masonry, warm sandstone, cyan
stairs and brass HUD accents. It is not accepted evidence of final game quality.
The current gameplay UI is English; full localization, portrait/mobile and sound
are outside this slice's accepted scope. The game is deliberately silent.

## Reproduce and review

Use [the native recipe](../../../scripts/godot_web/stairkeep/README.md), the
[Web export recipe](../../../scripts/godot_web/stairkeep/WEB-EXPORT.md), and the
[pending browser checklist](../../../scripts/godot_web/stairkeep/BROWSER-ACCEPTANCE.md).
The delivered review ZIP contains an editable native project, exported browser
game, all applicable licenses and this evidence. Serve its web folder over HTTP;
do not open index.html using file://. Source and runtime hashes are recorded.

The existing showcase games and shared runtime remain untouched. This draft is
not selected in collection.json or the play manifest, and is not deployed.
The [21-floor design](../../../scripts/godot_web/stairkeep/CAMPAIGN-21-DESIGN.md)
is a follow-on specification; those floors, death variants and play duration are
not implemented or accepted in this package.
''', encoding="utf-8")
    manifest_files = []
    for path in sorted(CASE.iterdir()):
        if not path.is_file() or path.name in {"manifest.json","README.md","validation.json"}:
            continue
        row = {"path":path.name,"bytes":path.stat().st_size,"sha256":sha(path)}
        if path.name == "concept.jpg":
            row.update(width=1536,height=1024,bit_depth=8,role="AI-generated concept, not gameplay capture")
        manifest_files.append(row)
    write_json(CASE / "manifest.json", {"schema_version":1,"godot_application":"Godot standard editor CLI","godot_version":export["engine"],"capture_provider":"none; concept generated, native pixels unobserved","files":manifest_files})
    items = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and not {".godot","__pycache__"}.intersection(path.parts):
            items.append((path,"Stairkeep/source/scripts/godot_web/stairkeep/"+path.relative_to(HERE).as_posix()))
    items.append((REPO / "LICENSE","Stairkeep/source/LICENSE"))
    for path in sorted(CASE.iterdir()):
        if path.is_file():
            items.append((path,"Stairkeep/source/docs/showcase/stairkeep/"+path.name))
    for path in sorted(candidate.rglob("*")):
        if path.is_file():
            items.append((path,"Stairkeep/web/"+path.relative_to(candidate).as_posix()))
    quickstart = "Stairkeep / 阶塔 — working title, renameable\n\nREVIEW CANDIDATE, not browser-accepted or deployed.\n\nPLAY: extract, open a terminal in Stairkeep/web, run\npython -m http.server 8741 --bind 127.0.0.1\nthen open http://127.0.0.1:8741/ in a WebGL 2 browser.\nDo not use file://. Actual browser acceptance is still pending.\n\nEDIT: open source/scripts/godot_web/stairkeep/game/project.godot\nin existing Godot 4.7.2. Full recipes, source/license records and\n21-floor follow-on design are in the same source folder.\n\nEVIDENCE: source/docs/showcase/stairkeep/README.md.\n42 rule checks, 34 projection round-trips, 10000 seeded policy runs.\n20 randomized resource dead ends are retained and documented.\n\nControls: WASD / compass; click adjacent to interact, inspect distant\nobjects and Approach; E on stairs; Esc menu. Save/Load/Restart native UI.\nDesktop 1280x800 composition; silent English UI; mobile unaccepted.\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("Stairkeep/README.txt",quickstart)
        for path, name in items:
            z.write(path,name)
        z.writestr("Stairkeep/FILES.json",json.dumps([{"path":name,"bytes":p.stat().st_size,"sha256":sha(p)} for p,name in items],indent=2))
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:
            raise SystemExit("Review archive CRC failure")
        for path,name in items:
            if hashlib.sha256(z.read(name)).hexdigest() != sha(path):
                raise SystemExit("Review archive content mismatch")
    result = {"file_name":output.name,"bytes":output.stat().st_size,"sha256":sha(output),"source_export_hashes_match":True,"archive_crc_and_hashes_match":True,"browser":"blocked / not run","items":len(items)+2}
    write_json(output.with_suffix(".json"),result)
    print(json.dumps(result),flush=True)

if __name__ == "__main__":
    main()
