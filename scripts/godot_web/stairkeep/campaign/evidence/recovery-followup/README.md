# Recovery follow-up public proof audit

This subbundle has an independent manifest. The parent baseline ZIP and manifest
remain byte-exact; their inventory describes the sealed baseline, not this new
follow-up subdirectory. The project target is now 50 floors. This bundle records
the historical 21-floor rules fixture; it does not implement a 50-floor campaign.
The original 10,000 outcomes remain 8,638 wins and 1,362
dead ends. Inspect summary.json for the newly completed measurement, including
separate early guard/original-loss/checkpoint-recovery counts and every retained
failed or unknown checkpoint attempt.

## Two reproducibility levels

Public audit can verify all supplied proof bytes, cohort coverage, source hashes
and exact byte/line/JSON-pointer locators. BASELINE-REFERENCE.json binds historical
sources to exact members of the unchanged baseline public ZIP; no suffix matching
or private old traces are included. New journal headers remove only engine_pid
with equal-length ASCII spaces; all later proof bytes are retained. Public
metadata references are projections with explicit archive_id/member identity.

The exact measured-input.json retains its original SHA-256 and historical paths.
The frozen GD harness additionally pins original private raw journal hashes.
Those hashes intentionally differ after header privacy padding, so rerunning
that exact native measurement requires the original private bytes. The public
projection is for audit and is not a drop-in input for the measured GD harness.
There is no new portable native replay mode in this batch.

The measured input and its public projection retain historical pre-follow-up
"not-tested" flags. New results belong to summary.json and case-receipts, not to
a rewrite of the original case status or the original 10,000 policy outcomes.

## Audit the public package

Extract using Python's standard ZIP_LZMA implementation:

    python -m zipfile -e recovery-evidence.zip extracted
    python extracted/package_recovery_followup.py --audit --output extracted --baseline-zip ../campaign-evidence.zip

The audit command performs data reads and temporary public-byte caching only;
it never launches Godot, another native harness or a browser. Native aggregator
self-tests under source/tools require the original measured private dataset and
their explicit CLI arguments. VALIDATOR-SELFTESTS.json preserves the actual new
20-check CLI execution and the distinct 21-check packaging synthetic execution,
each bound to its own source hash; historical v3 receipts are not substituted.
All new-head CI results are recorded separately.
