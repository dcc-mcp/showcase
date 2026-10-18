# Agent-readable cases and evaluation planning

A case can be useful to artists and agents without becoming a released dataset.
Keep the small optional `dcc-showcase-production/v1` record beside the existing
case evidence. The same record is the machine-readable entry point; a future
site may link it through the existing selected-public inventory. No new public
API, automatic dataset export, or separate benchmark platform is needed here.

## Fields

- `task.goal`: observable target, with a sanitized reusable brief rather than a
  private prompt. `task.inputs` are hashed public-safe input files (empty is valid
  for original work); `task.capabilities` are the actual covered capabilities,
  not every capability advertised by the software. Inputs may reuse licensed
  assets outside the case inventory. If an external input cannot be publicly
  redistributed, link a hashed public-safe provenance receipt containing its
  source URL and original content hash instead; label it as a receipt, not as
  the asset bytes. This checker never fetches the external asset.
- `task.reproduction_budget`: `estimated_seconds`, `measured_seconds`, and
  `cost_ceiling`, all null until known. A measured duration needs hashed
  `evidence`; a known cost ceiling is `{ "amount": ..., "currency": "..." }`.
  Estimates, observed cost/time and user-approved spending limits are different.
  No budget value authorizes a purchase or an unbounded GPU/render job.
- `environment`, `recipe` and real-MCP check references identify the software,
  plugins, calls/operations and reproduction steps. Keep exact versions and
  source hashes. A sequence is complete only when actual traces establish it;
  do not synthesize missing calls from the end result.
- `outputs`: hashed delivered output files, selected from that case's existing
  manifest (or its explicitly selected `play/<slug>/` Web inventory). A different
  case's file, shared engine, or repository license is not this case's output.
  The manifest remains the full inventory. Do not hash the manifest back into
  a record that it hashes, creating a circular dependency.
- `failure_recovery`: empty when none is recorded, otherwise stage/status,
  hashed `minimal_reproducer`, optional fix repository/PR/commit, and hashed
  `real_regression`. A recorded `passed` recovery needs both reproducer and real
  regression evidence; unit-test success alone cannot prove host recovery.

This is an index, not a performance score. Separate correctness, visual judgment,
interaction, reproducibility and resource usage. Record the checked revision,
criteria, test mode, provenance and limits. An unavailable host or unrun browser
is a blocker/unexecuted stage, not a zero-quality score. Comparisons need matched
inputs, settings and scope before their numbers can support a conclusion.

## Three independent permissions

`usage_rights.display`, `.training` and `.evaluation` each carry explicit
`status` (`granted`, `not-granted`, `unknown`) and hashed evidence. A claimed
`granted` requires recorded terms or specific permission identifying the actual
assets and permitted purpose. Store authoritative URLs, date, scope, attribution,
restrictions and any expiration in that evidence file. The checker can check
its bytes, not interpret or authenticate a legal grant. Reports retain
`rights_verified=false` and an explicit declared-evidence scope even when
a record says `granted`.

Defaults are display `unknown`, training/evaluation `not-granted`: no relevant
grant has been recorded by this index. This does not revoke or rewrite an
existing license. Do not infer these permissions from download availability,
site-code MIT, a source repository's generic license, or prior public display.
Asset/source/media licenses and third-party obligations remain separate.
Training permission does not imply evaluation permission or vice versa. Unknown
or absent rights must not be exported as positive dataset permission.

New public evaluation records may describe one authorized case's task, outputs
and measured checks after evidence/privacy/rights review. Dataset publication,
new licensing and distribution require separate authorization. Existing private
competing-tool benchmarks, private prompts, credentials and internal Unreal
projects stay private and outside the site's selected files/source packages.
