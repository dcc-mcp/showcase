# Evidence without rewriting history

## Existing publication contract stays authoritative

Do not migrate old `validation.json` checks from `pass`/`fail`, rewrite
`collection.json` history, or backfill attribution. Existing files keep their
shape. Use the optional `production-evidence.json` record for a newly planned
run or review; link it in the entry's manifest when adding it to that directory.
For agent-readable task, output, rights and benchmark-planning fields, read
[Agent data](agent-data.md). No dataset publication is implied.

It is a stage index of hashed evidence, not a replacement for measurements,
MCP transcripts, license notices, the recipe or the existing manifest.

Copy `assets/production-evidence.template.json` outside the public tree while
planning. Replace the case slug/date and evidence references with real values.
The template deliberately starts untested and is not publishable as evidence.
Its schema identifier is `dcc-showcase-production/v1`; the checker implements
this small optional format without adding a dependency or changing the site.

- `environment`: each actual host/adapter/Core and used plugin/skill/renderer,
  exact version and a hashed evidence file. Unknown versions use `unknown` plus
  `reason`; they remain unresolved. The checker requires host, adapter and core
  roles, but a reviewer must also verify the complete real dependency set.
- `recipe`: repository-relative file path and SHA-256 for the reproduction recipe.
- `sources`: native/source file references with SHA-256, including safe delivered
  package inventory. Never include private originals merely to satisfy a field.
- `interactive`: set true for interactive work; Godot always requires interaction
  regardless of this flag.
- `checks`: stages named in the template; add `native_interaction` and
  `web_playable` for Godot. For other interactive hosts add applicable interaction
  stages too. Each has `status`, concrete `summary`, and `evidence` references
  (`path`, lowercase `sha256`), `evidence_origin` (`current-run`, `historical`,
  `not-run`) and a concrete `scope` (native GUI, CI/local browser, production URL,
  physical device, subjective listening, etc.). Historical results never become
  newly executed checks. No public task/session IDs or private receipts.
- `recorded_at`: dated run/review timestamp. Scope every result to the recorded
  host/build/artifact. Do not mark a historical action newly executed.

## Four states

- `passed`: the named real check ran and met its stated criteria, bound to evidence.
- `failed`: the check ran and contradicted its criteria; include expected/observed.
- `not-tested`: no relevant test ran, including a planned or inapplicable stage.
  Explain intentional silence or a truly inapplicable stage; don't use a fake pass.
- `blocked`: the test could not proceed; state the exact dependency/access/license
  blocker and smallest next step, without bypassing it.

The checklist is conservative: a waived/inapplicable stage keeps automatic
readiness false. A human may decide a narrower claim with an explicit reason;
that decision must not be reported as a passed test. Template fields do not
make tests happen, and a forged/mis-scoped record can pass structural validation.

## Attribution

Use existing `collection.json.model_attribution` stage IDs and `record_status`.
Creation, code, reference and post-production are separate from later visual and
technical review. `configured` requires an actually checked accepted configuration
source, with public-safe basis/scope; it is not a backend identity attestation.
A self-described model, the reviewer's current model, or a filename is insufficient.
Leave model and reasoning effort exactly unknown where unverified. Do not invent
`receipt_bound` or claim a premium model proves better visual quality. The checker
only echoes recorded attribution and explicitly never verifies model identity.

## Read-only audit

```bash
python skills/dcc-showcase-production/scripts/check_showcase.py --repo . --case prism-tide --decode-video
python skills/dcc-showcase-production/scripts/check_showcase.py --repo . --case crate-lookdev --require-ready
python skills/dcc-showcase-production/scripts/check_showcase.py --repo .
```

Default exit 0 means the inventory was produced, even when incomplete; exit 2
means malformed/missing input. `--require-ready` exits 1 for missing video,
unrun decode, failed/blocked/untested stages, bad hashes or incomplete records.
Even a true `ready_for_human_decision` is only evidence completeness. It is never
visual approval, license clearance, attribution attestation or publishing authority.
External media remains blocked until separately authorized/materialized locally.
The all-case inventory provides current selected software and missing-video status;
combine it with the dated coverage ledger and current catalog for broader planning.

`optional_record_present=false` means this new index is absent, not that the
case has no historical acceptance. Read `existing_evidence_pointers` and
`declared_playables`, including later `play/manifest.json` revisions that can
supersede an original README. These pointers are located/hashed, not reaccepted.
`record_status` concerns only the index format; `unresolved_stages` concerns this
checker run/index. It is not a verdict against the historical work.

Use `scope_decision` to identify a needed human decision about a narrower claim
or an inapplicable stage (such as intentional silence). Do not fabricate a pass
to make readiness green. Browser/host launch failure before a test starts is
`blocked`, even if a lower-level test runner labels its process exit `failed`.
