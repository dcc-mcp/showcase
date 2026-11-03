
import argparse, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PRIVATE_RE = re.compile(
    r"[A-Za-z]:[\\/]|\\\\[\w.-]+[\\/]|/(?:Users|home)/|"
    r"\bPIP-\d+\b|\bHALLONG\b|\bmat_[A-Za-z0-9]+\b|\brez_local_cache\b|"
    r"\b_thm\b|\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", re.I)


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def privacy(paths):
    hits = []
    for f in paths:
        for m in PRIVATE_RE.finditer(f.read_text(encoding="utf-8")):
            hits.append(f"{f.name}:{m.group()[:24]}")
    return hits


def emit(result, out_name):
    text = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    (HERE / out_name).write_text(text, encoding="utf-8", newline="\n")
    failed = [c["name"] for c in result["checks"] if c["result"] != "pass"]
    print(f"verdict={result['verdict']} checks={len(result['checks'])} failed={failed}")
    return 1 if failed else 0


def check(name, ok, observed):
    return {"name": name, "result": "pass" if ok else "fail", "observed": observed}


def main():
    ledger = load("capability_coverage.json")
    exp = ledger["expected"]
    cov = ledger["coverage"]
    slugs = {c["slug"] for c in ledger["cases"]}
    checks = []
    checks.append(check("expected_inventory_integrity",
        len(exp["typed_tools"]) == 17 and len(exp["skills"]) == 8
        and len(exp["stages"]) == 7 and len(exp["runtime_modes"]) == 2
        and len(exp["lifecycle_exit_codes"]) == 6 and len(exp["demo_steps"]) == 12
        and len(exp["read_only_tools"]) == 6 and len(exp["destructive_tools"]) == 11
        and ledger["case_count"] == len(slugs) == 4,
        "Expected inventory: 17 tools / 8 skills / 7 stages / 2 modes / 6 exit codes / "
        "12 demo steps / 6 read-only / 11 destructive / 4 cases."))
    uncovered = {}
    for key, expected in exp.items():
        items = list(expected if not isinstance(expected, dict) else expected.keys())
        rows = {r["item"]: r["cases"] for r in cov[key]}
        gaps = [i for i in items if not rows.get(i) or not set(rows[i]) <= slugs]
        if gaps:
            uncovered[key] = gaps
        checks.append(check(f"{key}_coverage", not gaps,
            f"{len(items)} expected items, {len(items) - len(gaps)} covered by at least one "
            f"case in the set; uncovered: {gaps}."))
    part_ok = (set(exp["read_only_tools"]).isdisjoint(exp["destructive_tools"])
               and len(exp["read_only_tools"]) + len(exp["destructive_tools"]) == 17
               and set(exp["read_only_tools"]) | set(exp["destructive_tools"]) == set(exp["typed_tools"]))
    checks.append(check("read_only_destructive_partition", part_ok,
        "6 read-only and 11 destructive tools are disjoint and partition the 17 typed tools."))
    checks.append(check("declared_uncovered_is_empty", ledger["declared_uncovered"] == [],
        "The ledger declares no uncovered capability."))
    p = privacy([HERE / "capability_coverage.json"])
    checks.append(check("no_private_paths_or_ids", not p, f"Private-pattern hits: {p}."))

    result = {
        "schema_version": 1,
        "slug": "zbrush-mcp-capability-coverage",
        "verdict": "pass" if all(c["result"] == "pass" for c in checks) else "fail",
        "checks": checks,
        "counts": {
            "case_count": len(slugs),
            "typed_tools": len(exp["typed_tools"]),
            "skills": len(exp["skills"]),
            "stages": len(exp["stages"]),
            "runtime_modes": len(exp["runtime_modes"]),
            "lifecycle_exit_codes": len(exp["lifecycle_exit_codes"]),
            "demo_steps": len(exp["demo_steps"]),
            "read_only_tools": len(exp["read_only_tools"]),
            "destructive_tools": len(exp["destructive_tools"]),
            "uncovered_categories": len(uncovered),
        },
        "uncovered": uncovered,
        "zero_gap": not uncovered,
        "live_typed_tool_returns_claimed": False,
    }
    return emit(result, "capability_coverage_result.json")


if __name__ == "__main__":
    raise SystemExit(main())
