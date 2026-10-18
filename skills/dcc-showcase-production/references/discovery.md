# One source, existing ecosystem routes

The canonical source is this repository's
`skills/dcc-showcase-production/`. Maintain instructions, references,
template and checker here; never fork per-agent copies. `AGENTS.md` and the
README are navigation pointers. The existing entry contract remains the
publication schema, and Core remains owner of production reuse and MCP runtime.

## Use from this checkout

- Codex: read the root `AGENTS.md` pointer and load this Skill explicitly. An
  installed copy can be invoked with `$dcc-showcase-production`; start a fresh
  session if its catalog is cached. This repository reserves `.agents/` for
  runtime mounts, so it intentionally does not contain a second source copy.
- Claude Code, Gemini CLI, Cursor, Copilot, OpenCode and other agents: explicitly
  ask “Read AGENTS.md, then use skills/dcc-showcase-production/SKILL.md
  to produce/review this case.” This path works without relying on vendor-specific
  automatic discovery. Follow only the requested case's linked references.
- Agents without filesystem access: read `SKILL.md` and its relative reference
  URLs from one pinned repository commit. The checker requires a checkout;
  missing bytes or a runtime are reported as untested, not re-created evidence.

For a managed agent-host installation, use the ecosystem's existing universal
Agent Skills installer after source review/merge, selecting only this skill:

```bash
npx --yes skills@1.5.22 add dcc-mcp/showcase --skill dcc-showcase-production
```

The pinned installer's local `add . --list` was tested against this source and
discovered exactly `dcc-showcase-production` without installing it. This is an
installation option requiring the user's authorization, not a command
to run automatically. During Draft review use the checked-out source above;
main will not contain this Skill until merge. Verify the installed copy and
restart hosts that discover skills at startup. No ClawHub slug, npm package,
marketplace entry, release archive or cross-agent installation is claimed by
this source change. Those would need separately verified distribution work.

The existing [agent-plugins distribution](https://github.com/dcc-mcp/dcc-mcp-agent-plugins)
continues to own `dcc-mcp`, `dcc-mcp-creator` and `dcc-mcp-skills-creator`.
Install/load `dcc-mcp` for actual host execution; this showcase skill composes
with it rather than duplicating its tool calls. `DCC_MCP_SKILL_PATHS` is an
adapter runtime setting, not agent-host installation. Do not add this workflow
to every adapter or enable publication workflows merely to make it discoverable.

For future distribution integrations, reference this pinned source or generate
byte-identical copies using the owning ecosystem's packaging pipeline and verify
hashes. Keep one editable source, review release/version boundaries first, and
do not imply distribution to a host that has not been tested.

The smallest later ecosystem-discovery integration is a pointer from the public
`dcc-mcp` router/catalog to this reviewed source. A registry requiring an archive
needs a source mapping in its existing release pipeline and byte-equality checks.
Neither registration nor release is performed by adding this repository Skill.
