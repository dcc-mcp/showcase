# Ecosystem production is mandatory

Every selected case, not only newly changed cases, must pass
`python scripts/validate_ecosystem.py` before a subsequent build/publication.
The same check runs inside `build_site.build` before touching the output directory
and before Pages uploads. There is no legacy, warning-only, native fallback, or
changed-files exemption. This change does not remove an existing deployment.

All artwork authoring/adaptation, rendering, export and media post-production
must use DCC-MCP ecosystem components. Official CLI/Skills are valid routes, not
only wire-level MCP. A bare Blender/FFmpeg command or direct `bpy` script is not
made compliant by a wrapper, truthful disclaimer, or unrelated later MCP call.
A component's own documented host/backend execution is not itself a bypass:
retain the official component identity and actual invocation with output lineage.
Read-only checks and playback are distinct from production. Original upstream
assets require source/rights records; adapting them requires an ecosystem stage.

## The rule in plain terms

Use the ecosystem to make the work, and retain enough actual invocation and
artifact evidence to verify that fact. The record below indexes that evidence;
it is not a substitute for production. Existing genuine evidence may be reused.
Do not rerender a conforming work just to fill in a different report template.
Only phases actually performed need stages; unused phases have a short reason.

## Required per-case record

Place `ecosystem-production.json` in the case directory and include it and its
public-safe evidence in `manifest.json`. Schema: `dcc-showcase-ecosystem/v1`.
Do not fabricate records to unblock CI. The initial rollout intentionally blocks
all selected cases without these records; migration requires evidence review,
not relabeling earlier work. Existing `production-evidence.json` remains a
separate optional quality/reproducibility index and cannot satisfy this gate.

Required fields:

- `schema`, `case_slug`.
- `phases`: authoring, rendering, export, post-production. Each has `status`
  `performed`, with actual stages, or `not-applicable` with a concrete reason.
  Inapplicability is reviewed and cannot conceal a performed native-only stage.
- `stages`: nonempty list with unique `id`, `phase`, `status: succeeded`, `route`
  (`mcp`, `ecosystem-cli`, `ecosystem-skill`), and `component` (`version`, official
  `https://github.com/dcc-mcp/<repo>/commit/<40-hex>` or pinned tree `source`), or a version-specific official PyPI release URL.
  For registry URLs, the version must exactly match and the package must appear
  in the validator's reviewed `OFFICIAL_PYPI` ownership map. A `dcc-mcp` name
  prefix alone is never trusted. The initial verified entry is
  [dcc-mcp-blender 0.2.22](https://pypi.org/project/dcc-mcp-blender/0.2.22/),
  tied to the official organization's immutable pyproject source in that map.
  Add other registry packages only after verifying their official ownership.
  The earlier Git-commit-only rule was unnecessarily restrictive for real
  released-package installations. The release pin does not replace actual
  invocation/output verification or prove what was installed.
- Each stage has `request`, `response`, `artifact_measurement`, `inputs`,
  `outputs`: file references use repository-relative `path` and lowercase
  `sha256`. Request/response files preserve actual sanitized invocation/result
  bytes, not a rewritten successful summary. Never publish secrets or private
  paths. Error envelopes or pending jobs are not successful results.
- Measurement JSON binds `request_sha256`, `response_sha256`, exact `outputs`
  references, and `status: succeeded`. Retain measurement provenance and the
  original failed runs. It is a separate artifact measurement, not a fake tool
  response. Referenced production inputs have an upstream stage producer or
  appear in `external_sources` with exact bytes, `origin`, and `license`.
- Every selected media/native/archive output must have a producer, including
  derivatives and selected playable assets. Intermediate sources used by later
  stages must also be retained and bound. Archives additionally require review
  of their member-level production lineage; a ZIP operation cannot launder
  non-ecosystem artwork.
- Non-production administrative files need explicit `reports` references with
  a concrete `reason`; only md/txt/log/json formats are eligible and classification
  is included in independent review. JSON/TXT files are not implicitly exempt: a
  native scene, animation or game level is production, not a report. Fixed entry
  README/manifest/validation and referenced raw evidence are administrative. Raw
  call evidence cannot be a production image/binary. The complete shared play
  manifest is covered across case graphs, including cross-directory dependencies.
- External media/download URLs require a `downloads` entry containing the exact
  `url` and a hash-bound `local` reference to the verified downloaded bytes.
  These bytes also need production/upstream lineage. URLs alone are not proof.
  A non-download external resource instead needs an exact-URL `external_links`
  entry, `kind: reference`, and a reviewed `reason`. No URL extension, query
  string or missing extension silently exempts a resource; classification is
  bound to the review graph. A URL cannot be both reference and download.
- `review`: `status: verified`, `evidence` reference to a distinct review JSON.
  Its `production_graph_sha256` is SHA-256 of canonical JSON of schema,
  case_slug, phases, stages, external_sources, downloads, reports, external_links and selected_outputs (sorted keys,
  compact JSON). selected_outputs is the sorted list of actual selected path/
  SHA-256 pairs excluding the referenced evidence records themselves.
  It includes reviewer/date, `raw_calls_verified: true`, and
  `all_production_steps_covered: true`. The reviewer must actually inspect the
  raw requests/results and whole recipe, compare observed artifacts, reject
  semantic backend errors, and reject omitted/native-only stages.

## What this gate does not prove

Hashes verify file identity and evidence binding, not truth or authorship.
The validator is deliberately named an evidence gate, not an attestation. It
cannot detect every forged transcript, omitted step, archive dependency or false
review assertion. Protected review and real host replay remain necessary; CI
must never be described as proving end-to-end production merely because JSON
is well-formed. Tests are explicitly synthetic, never real production evidence.

## Migration

1. Inventory all production steps and native/delivered artifact hashes.
2. Recover existing real calls where available without changing their dates,
   versions, output hashes or historical failure status.
3. Classify missing evidence separately from confirmed direct-host bypasses.
4. For bypassed steps, discover existing ecosystem capabilities. Replay only
   with authorization and preserve a new, separately dated artifact lineage.
5. If genuinely blocked by a capability, retain the exact tool schema, inputs,
   failure and versions; deduplicate an owning-component issue/Draft PR and
   verify its fix in a real host. Do not guess a bug from an absent session.
6. Review the complete record before changing the publication gate result.
