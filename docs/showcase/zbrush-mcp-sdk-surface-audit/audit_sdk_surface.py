
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


def parse_tools_yaml(path):
    rows, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("- name:"):
            cur = {"name": s.split(":", 1)[1].strip().strip("\"'"), "source_file": None}
            rows.append(cur)
        elif cur is not None and s.startswith("source_file:") and cur["source_file"] is None:
            cur["source_file"] = s.split(":", 1)[1].strip().strip("\"'")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skills-root", type=Path, default=None,
                    help="dcc-mcp-zbrush skills directory for contract recomputation")
    args = ap.parse_args()
    host = load("live_2027_sdk_callables.json")
    backing = load("sdk_tool_backing.json")
    available = set(host["sdk_public_callables"])
    rows = backing["rows"]
    distinct = sorted({c for r in rows for c in r["sdk_calls"]})
    package_calls = backing["package_sdk_calls"]
    package_missing = sorted(set(package_calls) - available)
    missing = sorted(set(distinct) - available)
    tools = {r["tool"] for r in rows}
    bridge_only = sorted(r["tool"] for r in rows if r["backing_kind"] != "zbrush_commands")
    ui_absent = all(
        name.lower().replace(" ", "_") not in {t.lower() for t in tools}
        and name.lower().replace(" ", "_") not in {c.lower() for c in available}
        for name in host["absent_ui_capabilities"])
    checks = []
    calls = host["sdk_public_callables"]
    checks.append(check("host_callable_inventory_integrity",
        len(calls) == host["sdk_public_callable_count"] == len(set(calls)) == 149
        and calls == sorted(calls) and host["host"]["executed_this_run"] is False,
        f"{len(calls)} unique public callables from the retained real-host probe; "
        f"declared count {host['sdk_public_callable_count']}; no new host run this time."))
    checks.append(check("tool_backing_rows_integrity",
        len(rows) == backing["row_count"] == 17 and len(tools) == 17
        and all(not r["source_file"].startswith(("/", "\\")) and ":" not in r["source_file"]
                and r["sdk_call_count"] == len(r["sdk_calls"]) for r in rows),
        f"{len(rows)} tool rows, {len(tools)} unique tool names, all source paths repository-relative."))
    checks.append(check("sdk_calls_resolve_in_real_host",
        len(distinct) == 17 and len(package_calls) == 22
        and set(distinct) <= set(package_calls) and not missing and not package_missing,
        f"{len(package_calls)} distinct SDK calls across the whole adapter package "
        f"({len(distinct)} inside typed-tool sources); {len(package_missing)} missing from the "
        f"real host surface. Missing list: {package_missing}."))
    checks.append(check("bridge_only_tools_declared",
        len(bridge_only) == 3 and all(not r["sdk_calls"] for r in rows if r["tool"] in bridge_only),
        f"{len(bridge_only)} tools operate through the socket bridge, window OCR or the embedded "
        f"interpreter and declare no direct zbrush.commands call: {bridge_only}."))
    checks.append(check("ui_only_capabilities_absent", ui_absent,
        "Selection Sets / Bake Current / UV Apply/Cancel have no dedicated callable and no typed tool."))
    ident = host["identity"]
    checks.append(check("identity_gate_evidence",
        ident["fixed_version_string"] == "2027.001" and ident["fixed_edition"] == 2
        and ident["identity_consistent_genuine"] is True
        and ident["old_buggy_would_rollback"] is True
        and len(ident["tamper_rejections"]) == 4,
        "Retained real-host identity: 2027.001 / edition 2, consistent, old formula would roll back, "
        "4 tamper shapes rejected."))
    if args.skills_root is None:
        checks.append({"name": "contract_recompute_from_skills_root", "result": "not_run",
                       "observed": "No --skills-root supplied; the shipped tools.yaml contracts were not re-read from an adapter checkout."})
        recomputed = None
    else:
        recomputed = {}
        for skill_dir in sorted(args.skills_root.iterdir()):
            if not skill_dir.is_dir() or not skill_dir.name.startswith("zbrush-"):
                continue
            for r in parse_tools_yaml(skill_dir / "tools.yaml"):
                f = skill_dir / r["source_file"]
                recomputed[r["name"]] = sorted(set(re.findall(
                    r"\bzbc\.([a-z_][a-z0-9_]*)",
                    f.read_text(encoding="utf-8", errors="replace"))))
        same = all(recomputed.get(r["tool"]) == r["sdk_calls"] for r in rows)
        checks.append(check("contract_recompute_from_skills_root",
            same and len(recomputed) == 17,
            f"Re-derived {len(recomputed)} tool source files from the adapter checkout; "
            f"all per-tool SDK call lists match the published ledger: {same}."))
    p = privacy([HERE / "live_2027_sdk_callables.json", HERE / "sdk_tool_backing.json"])
    checks.append(check("no_private_paths_or_ids", not p, f"Private-pattern hits: {p}."))

    result = {
        "schema_version": 1,
        "slug": "zbrush-mcp-sdk-surface-audit",
        "verdict": "pass" if all(c["result"] == "pass" for c in checks) else "fail",
        "checks": checks,
        "counts": {
            "real_host_public_callables": len(calls),
            "distinct_sdk_calls_used": len(distinct),
            "package_sdk_calls_used": len(package_calls),
            "typed_tools": len(rows),
            "tools_with_sdk_backing": len(rows) - len(bridge_only),
            "tools_without_direct_sdk_calls": len(bridge_only),
            "missing_sdk_callables": len(missing),
            "registered_ui_only_capabilities": 0,
            "sdk_keyword_callables": len(host["sdk_keyword_callables"]),
            "tamper_rejections": len(ident["tamper_rejections"]),
        },
        "missing_sdk_callables": missing,
        "zero_gap": not missing,
        "recompute_performed": recomputed is not None,
        "live_typed_tool_returns_claimed": False,
    }
    return emit(result, "sdk_surface_audit_result.json")


if __name__ == "__main__":
    raise SystemExit(main())
