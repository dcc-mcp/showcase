---
name: dcc-showcase-production
description: Create, revise, or accept a DCC-MCP showcase with real host output, reproducible assets, media and interaction review, and evidence-backed publication boundaries. Use for showcase production and case acceptance, not generic adapter development or site-only styling.
metadata:
  version: 1.1.0
---

# DCC showcase production

Produce a case another person can inspect and reproduce. A render, successful
MCP envelope, model name, or passing structure check alone is not acceptance.
This is the showcase workflow; use the existing `dcc-mcp` Skill for live tool
discovery and execution, and `dcc-mcp-skills-creator` only for a reusable tool
package. Do not build another runtime, installer, or marketplace.

## Start with the right scope

- Locate the showcase checkout and read `docs/showcase/CONTRACT.md`. Keep that
  contract, `collection.json`, the existing manifests, localization and build
  guards authoritative for publication. This Skill is maintained only here.
- For **new work or a material revision**, read [Production](references/production.md):
  current visual research, original concept, official/free-first reuse, real
  host work, and reproducibility. Apply Core's existing production-reuse gate.
- For **review or delivery**, read [Acceptance](references/acceptance.md).
  Inspect actual output and run applicable tests; do not rerun production merely
  to fill a report. Missing access is a blocker, not proof of failure or success.
- For **Godot native menus, HUDs or responsive UI**, read
  [Native UI](references/godot-native-ui.md) before authoring or accepting layout.
  Reuse installed scene/node/Theme tools; separate stored properties, settled
  runtime geometry, visual review and real input evidence.
- For **evidence recording or legacy audit**, read [Evidence](references/evidence.md).
  Keep creation and review attribution separate and unknown where unsupported.
- For **another agent or installation**, read [Discovery](references/discovery.md).

## Working loop

1. Agree the proposition and bounded native/media/interaction outcome. Inspect
   current coverage and open drafts before creating a new case or branch.
2. Research and select the visual idea and reusable capabilities before authoring.
   Record versions, rights, actual MCP calls, seeds/settings and source hashes.
3. Make the native work, save/reopen, export/reopen, and reproduce from its recipe.
   Capture intermediate and final output, including a real video for still work.
4. Review pixels, motion, sound and interaction separately. Record each applicable
   stage as `passed`, `failed`, `not-tested`, or `blocked`, with dated evidence.
   Fix failures and rerun the affected real-host path, not just unit tests.
5. Package only cleared public assets; use the existing site checks and review
   every supported locale. Report remaining gaps before any delivery decision.

From the showcase root, use
`python skills/dcc-showcase-production/scripts/check_showcase.py --repo . --case <slug>`
for a read-only
inventory and optional evidence validation. Add `--decode-video` to decode local
video bytes (single-threaded by default). The checker does not score aesthetics, listen, play the browser,
verify attribution, grant rights, or certify production. No script output is a
replacement for those reviews.

## Authority boundaries

A Skill is guidance, not standing permission to install, buy, log in, upload,
publish, contact others, open PRs, merge, or deploy. Follow the current task's
permissions. Stop the affected action on cancellation, denial, or paused-host
instructions; never change routes to bypass them. An authorized contribution
uses a deduplicated Draft PR on the original organization repository's branch;
review and subsequent authorization precede merge/release/deployment. Keep
private benchmarks and internal Unreal projects out of public evidence.
