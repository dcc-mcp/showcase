
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, default=None,
                    help="dcc-mcp-zbrush checkout for source-invariant recheck")
    args = ap.parse_args()
    m = load("recovery_lifecycle_matrix.json")
    checks = []
    checks.append(check("verdict_states_integrity",
        len(m["verdict_states"]) == 4 and set(m["verdict_states"]) ==
        {"ready", "busy", "blocked", "unreachable"},
        "4 probe verdict states are declared: ready / busy / blocked / unreachable."))
    checks.append(check("error_code_map_integrity",
        len(m["error_codes"]) == 3 and m["error_codes"]["-32002"] == "ZBRUSH_TIMEOUT_STILL_RUNNING",
        "3 client-visible bridge codes are mapped, including -32002 for the unknown-outcome path."))
    u = m["unknown_outcome"]
    checks.append(check("unknown_outcome_invariant",
        u["error_code"] == -32002 and u["retryable"] is False
        and u["execution_state"] == "unknown",
        "Post-submit connection loss is classified as execution_state=unknown and non-retryable."))
    checks.append(check("retryable_busy_invariant",
        m["retryable_busy"]["error_code"] == -32001
        and "blocked" in m["retryable_busy"]["condition"],
        "Only a refused-but-servable -32001 busy verdict is retried; blocked never is."))
    checks.append(check("blocked_label_integrity", m["blocked_label"] == "ZBRUSH_BLOCKED",
        "A blocked host surfaces ZBRUSH_BLOCKED instead of being retried or auto-answered."))
    codes = m["lifecycle_exit_codes"]
    checks.append(check("lifecycle_exit_codes_integrity",
        len(codes) == 6 and sorted(codes.values()) == [0, 10, 20, 30, 40, 50],
        "6 distinct lifecycle exit codes: 0 / 10 / 20 / 30 / 40 / 50."))
    checks.append(check("runtime_modes_integrity",
        len(m["runtime_modes"]) == 2 and set(m["runtime_modes"]) == {"embedded", "sidecar"},
        "2 runtime modes expose the same typed tools and progressive stages."))
    if args.source_root is None:
        checks.append({"name": "source_invariant_recheck", "result": "not_run",
                       "observed": "No --source-root supplied; the adapter source literals were not re-read."})
    else:
        missing = []
        for inv in m["source_invariants"]:
            f = args.source_root / inv["file"]
            if not f.is_file() or inv["literal"] not in f.read_text(encoding="utf-8", errors="replace"):
                missing.append(inv["id"])
        checks.append(check("source_invariant_recheck", not missing,
            f"{len(m['source_invariants'])} source literals rechecked against the adapter checkout; "
            f"missing: {missing}."))
    p = privacy([HERE / "recovery_lifecycle_matrix.json"])
    checks.append(check("no_private_paths_or_ids", not p, f"Private-pattern hits: {p}."))

    result = {
        "schema_version": 1,
        "slug": "zbrush-mcp-recovery-and-lifecycle",
        "verdict": "pass" if all(c["result"] == "pass" for c in checks) else "fail",
        "checks": checks,
        "counts": {
            "verdict_states": len(m["verdict_states"]),
            "error_codes": len(m["error_codes"]),
            "runtime_modes": len(m["runtime_modes"]),
            "lifecycle_exit_codes": len(codes),
            "bridge_only_tools": len(m["bridge_only_tools"]),
            "ui_capabilities_not_registered": len(m["ui_capabilities_not_registered"]),
            "source_invariants": len(m["source_invariants"]),
        },
        "source_recheck_performed": args.source_root is not None,
        "live_typed_tool_returns_claimed": False,
    }
    return emit(result, "recovery_lifecycle_result.json")


if __name__ == "__main__":
    raise SystemExit(main())
