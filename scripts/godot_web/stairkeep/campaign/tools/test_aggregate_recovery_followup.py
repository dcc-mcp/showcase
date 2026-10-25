"""Repeat the original 20 read-only recovery-evidence validator checks.

This uses the original opaque raw queue (SHA 45b905...) and its original raw
JSONL fixtures plus paired .summary.json files. It does not accept sanitized
public archive derivatives as substitutes for those raw byte/hash bindings.
It launches no engine and never modifies the validator, game, queue or fixtures.

Example from the workspace root (Python 3.10+; standard library only):
  python stairkeep-campaign/scripts/godot_web/stairkeep/campaign/tools/test_aggregate_recovery_followup.py \
    --input output/recovery-followup-input.json \
    --source-root stairkeep-campaign/scripts/godot_web/stairkeep/campaign \
    --early-probe output/early-guard-final-probe.jsonl \
    --late-probe output/late-recovery-final-probe.jsonl \
    --old-early-probe output/early-guard-win-smoke-1.jsonl \
    --late-parts output/late-recovery-part-0.jsonl output/late-recovery-part-1.jsonl output/late-recovery-part-2.jsonl output/late-recovery-part-3.jsonl \
    --output output/recovery-aggregator-selftest-cli.json

The new output must not exist. Original raw failure journals referenced by the
queue must remain at its declared relative paths. Each probe contains exactly
one actual full winning recovery. The old early probe is the genuine historical
different-harness fixture used to test rejection, not a fabricated game result.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

FROZEN_AGGREGATOR_SHA256 = "c3584ead2ec227cc7e28d1b4481c96e8d6d6ccad0b24858758bfdfb3244c7226"
BOUND_INPUT_SHA256 = "45b905d9157585ba8a06df612c9a727ad5bbe3ee7c89c4e4bae0253f94c567d0"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--aggregator", type=Path, default=Path(__file__).with_name("aggregate_recovery_followup.py"), help="Exact frozen validator source; defaults to the adjacent tool")
    parser.add_argument("--input", type=Path, required=True, help="Original SHA-bound 45b905... recovery-followup-input.json")
    parser.add_argument("--source-root", type=Path, required=True, help="Campaign project containing the frozen rules, harnesses and canonical data")
    parser.add_argument("--early-probe", type=Path, required=True, help="One-case final-hash early full-win raw JSONL, with its .summary.json")
    parser.add_argument("--late-probe", type=Path, required=True, help="One-case final-hash late full-win raw JSONL, with its .summary.json")
    parser.add_argument("--old-early-probe", type=Path, required=True, help="Historical different-harness early raw probe, with its .summary.json; rejection fixture only")
    parser.add_argument("--late-parts", type=Path, nargs=4, required=True, help="The four official complete raw late shards, with all .summary.json files")
    parser.add_argument("--output", type=Path, required=True, help="A new selftest receipt; no existing file is overwritten")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Refusing to replace an earlier selftest receipt")

    spec = importlib.util.spec_from_file_location("recovery_evidence_validator", args.aggregator)
    if spec is None or spec.loader is None:
        raise SystemExit("Cannot load the supplied validator source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.sha_file(args.aggregator) != FROZEN_AGGREGATOR_SHA256:
        raise SystemExit("Validator source differs from the exact c3584e... freeze tested by this suite")
    if module.sha_file(args.input) != BOUND_INPUT_SHA256:
        raise SystemExit("Original opaque 45b905... recovery input is required; no substituted portable input mode")

    def fresh():
        return module.Validator(args.input, args.source_root)

    def read_case():
        with args.early_probe.open(encoding="utf-8") as file:
            for line in file:
                row = json.loads(line)
                if row.get("kind") == "early_guard_case":
                    return row
        raise ValueError("Actual final-hash early probe has no case")

    def first_record(path):
        with path.open(encoding="utf-8") as file:
            return json.loads(file.readline())

    current_header = first_record(args.early_probe)
    old_header = first_record(args.old_early_probe)
    if old_header.get("kind") != "early_guard_header" or old_header.get("harness_sha256") == current_header.get("harness_sha256"):
        raise SystemExit("The old early probe must be a genuine different-harness early journal")

    checks = []

    def rejected(name, action):
        try:
            action()
        except (ValueError, KeyError, StopIteration) as error:
            checks.append({"name": name, "passed": True, "rejected_reason": str(error)})
        else:
            checks.append({"name": name, "passed": False, "error": "Malformed evidence was accepted"})

    validator = fresh()
    validator.consume(args.early_probe, "early")
    validator.consume(args.late_probe, "late")
    actual = validator.report()
    checks.append({"name": "actual final-hash one early plus one late full-win probes validate", "passed": actual["validation_passed"] and actual["actual_complete_winning_recoveries"] == 2})
    checks.append({"name": "two actual probes do not imply all 1362 measured", "passed": actual["measurement_completed"] is False})
    rejected("same sample journal cannot be counted twice", lambda: validator.consume(args.early_probe, "early"))
    checks.append({"name": "integral JSON numbers normalize but booleans retain type", "passed": module.same(1, 1.0) and not module.same(True, 1) and not module.same(False, 0)})

    def changed(name, mutation):
        row = read_case()
        mutation(row)
        rejected(name, lambda: fresh().early_case(row))

    changed("wrong original index rejected", lambda r: r.update(index=r["index"] + 1))
    changed("boolean cohort offset rejected", lambda r: r.update(cohort_offset=False))
    changed("changed production query budget rejected", lambda r: r["intervention"]["default_preview"]["requested_budgets"].update(max_msec=30000))
    changed("false first loss receipt rejected", lambda r: r["intervention"]["default_preview"]["solver_report"]["receipt"].update(complete=False))
    changed("same-state losing to winning contradiction rejected", lambda r: r["explicit_override"]["preview"].update(classification="known_winning"))
    changed("local or incomplete terminal proof rejected", lambda r: r["actual_terminal_global_proof"].update(complete=False))
    # Keep the original wrong-prefix check meaningful for any supplied one-case
    # fixture rather than assuming it must be the historical case 4/flask.
    changed("wrong six-way prefix rejected", lambda r: r.update(prefix_type=next(prefix for prefix in module.PREFIX_COUNTS if prefix != r["prefix_type"])))
    changed("discontinuous full action chain rejected", lambda r: r["actual_paired_actions"][-1].update(after_full_snapshot_sha256="0" * 64))
    changed("manufactured checkpoint gold rejected", lambda r: r["complete_initial_checkpoint_recovery"]["full_restored_snapshot"]["core_state"].update(gold=1))
    changed("missing actual winning event rejected", lambda r: r["winning_recovery"]["trace"].pop())
    changed("false actual winning final state rejected", lambda r: r["winning_recovery"]["full_final_snapshot"]["core_state"].update(won=False))
    changed("changed winning final inventory rejected", lambda r: r["winning_recovery"]["full_final_snapshot"]["core_state"]["purchases"].update({"f01_shop/edge": 0}))
    rejected("old-hash smoke cannot represent current frozen harness", lambda: fresh().consume(args.old_early_probe, "early"))

    late = fresh()
    for part in args.late_parts:
        late.consume(part, "late")
    late_report = late.report()
    checks.append({"name": "all four actual late shards have exact 26 unique identities and actual complete wins", "passed": late_report["coverage"]["late"]["exact_set_complete"] and late_report["late"]["actual_complete_wins"] == 26})
    checks.append({"name": "late 26 alone cannot imply early 1336 coverage", "passed": late_report["measurement_completed"] is False and late_report["coverage"]["early"]["verified_unique_cases"] == 0})
    rejected("invalid internal byte locator rejected", lambda: module.Validator.require_locator({"path": "case.jsonl", "byte_offset": 0, "line": 1, "byte_length": 2, "line_sha256": "bad"}, {0: {"line": 1, "byte_offset": 0, "byte_length": 2, "line_sha256": "good", "kind": "proof", "index": 24}}, Path("case.jsonl"), "proof", 24))
    if len(checks) != 20:
        raise SystemExit("The retained suite must contain exactly the original 20 checks")

    fixture_paths = [args.input, args.early_probe, args.late_probe, args.old_early_probe, *args.late_parts]
    report = {"schema_version": 1, "suite": "recovery_aggregate_validator_selftest/v1", "passed": all(check["passed"] for check in checks),
              "checks": checks, "check_count": len(checks), "aggregator_sha256": module.sha_file(args.aggregator),
              "selftest_sha256": module.sha_file(Path(__file__)), "input_sha256": module.sha_file(args.input),
              "fixtures": [{"name": path.name, "bytes": path.stat().st_size, "sha256": module.sha_file(path)} for path in fixture_paths],
              "scope": "This CLI execution alone: original raw final-hash native probes and the complete late shards are read-only positive fixtures; deliberately malformed in-memory evidence is rejected. No game/recovery action is executed and early 1336 completion is not inferred. Earlier source/receipt provenance remains separate and is not reassigned to this CLI source."}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "check_count": len(checks), "failed": [check for check in checks if not check["passed"]], "output": str(args.output)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
