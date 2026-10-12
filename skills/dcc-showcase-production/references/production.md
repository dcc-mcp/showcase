# Production: idea to reproducible native output

## Research before authoring

Read the live `gateway://docs/agent-workflows` resource when available, checking
its `dcc-mcp-production-reuse/v1` section, or use the
[canonical Core guide](https://github.com/dcc-mcp/dcc-mcp-core/blob/main/crates/dcc-mcp-gateway/src/gateway/native_resources/agent_workflows.md#production-reuse-gate).
The gateway returning some text does not prove that the installed version has
the contract. Core main was verified to contain v1 when this Skill was authored;
check the source actually used on the new run. If unavailable, continue planning
and read-only research, but report the dependency before production. The CLI's
tool-call transport does not automatically read resources or execute this gate.

Search current trends and relevant artist/technical work before proposing an
original idea. Keep queries, dates, direct sources, what was learned, and why
the concept suits the host. Inspiration is not a license to reproduce artwork.
Translate the concept into a few observable goals: silhouette/material hierarchy,
lighting, framing, temporal arc, interaction or readable information design.
Avoid mandatory fashions or a fixed visual style across unrelated cases.

Follow Core's bounded reuse discovery: installed skills/providers, the DCC-MCP
marketplace, official host extension/plugin stores, then trusted upstreams.
Prefer suitable quality free capabilities, not free price at the expense of the
brief. For each credible candidate record identity, version, source/checksum,
fit, maintenance, public API coverage, host compatibility, cost and rejection or
selection reason. A generic web search cannot stand in for the official store.
Unknown compatibility/rights remain unresolved; don't invent an install success.
If no option fits, explain the gap and use the smallest authorized native bridge.

Check license terms separately for software, trial/free tier, generated output,
fonts, sound, textures, models and source redistribution. Record authoritative
terms, date and obligations per item. “Free,” “noncommercial project,” access to
an asset, or the site's MIT license does not grant output or redistribution
rights. A commercial application's free/trial entitlement must be checked for
this use, platform and current terms. Ask before new payment or legal acceptance.

## Production run

- Verify the task-owned host/session and installed host, adapter, Core/gateway,
  renderer, extension and skill versions. Distinguish source checkout, installed
  package and released version; preserve the exact build/commit when applicable.
- Discover actual tools through `dcc-mcp`, follow search/describe/load/call, and
  validate real returned values and host effects. Retain sanitized request and
  response evidence. `success: true` with an embedded backend failure is a failure.
  A direct script fallback must be explicit and cannot prove typed MCP coverage.
- Record the recipe, parameters, seeds, dependencies, color management, units,
  export settings and source SHA-256. Preserve native editable files and useful
  intermediate views. Reopening and a blank-scene recipe rebuild are separate
  tests: compare outputs with stated tolerances and report differences.
- Save, close/reopen in the actual host, check missing dependencies, and reopen
  the exported format in its intended consumer. Check archive extraction and
  relinkability on the delivered source package, not only the working directory.
- Design shot pacing, cuts, motion and sound together. Choose suitable score,
  sound effects and dynamics for each work; do not hard-cut the same track across
  unrelated films. Intentional silence is valid when documented and reviewed.
  Numeric audio metrics are not listening review.
- Still work also needs real viewport/process/turntable video. A single still
  with fabricated camera motion does not prove native execution. Capture real
  consecutive rendered or recorded frames, and retain timing/provenance. Keep
  a promotional edit separate from the native-evidence clip if their roles differ.

## Failures and coverage

Capture the smallest reproducible failure with exact versions, discovered tool
schema, sanitized arguments, expected/observed host result, and reproducible
artifact. Search existing issues and Draft PRs before proposing a fix. Under the
authorized scope, fix the owning adapter/Core tool in a separate Draft PR, run
its tests, and replay the actual host case on the fixed build. A mocked response
or passing unit test alone cannot close the production regression. Preserve the
original failed run and identify which later build fixed it. Stop if access or
action is denied; alternate transport is not permission.

Read `coverage.md` as a dated ledger, not today's installed-software inventory.
Reconcile the current official catalog and real environment before extending
coverage. Track software/skill, supported platform, license/access, actual MCP
run, reopen/export, video, interaction and review status independently. Legacy
cases without video remain “missing video”; don't silently delete or promote
them. A later review is a revision of the same slug, not a new case count.
