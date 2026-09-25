# DCC-MCP Showcase

Curated, reproducible proof of what DCC-MCP can do **inside real DCC hosts**.

Every entry here is a real artifact — a GIF, an image, or a video — produced by running one proposition end to end in a real host, plus one sentence on what it proves and the exact host and adapter versions it was verified on.

## Gallery

| Date | Group | Proposition | Adapter | Skill | What it proves | Preview | Host environment | Verified up to |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| _awaiting first approved entry_ | | | | | | | | |

`Adapter` names the repository the sample was produced against — for example `dcc-mcp/dcc-mcp-blender` — so every row links back to the adapter it proves.

`Skill` names the marketplace package that supplied the capability, or `—` when the sample proves the adapter alone. Together the two columns make each row a cell in the [coverage matrix](coverage.md).

The gallery is empty on purpose. Artifacts are drafted internally and published here one at a time, after review. Nothing lands in this repository by default.

## Coverage

[`coverage.md`](coverage.md) is the ledger: every marketplace skill against every DCC it declares, marked as proven, drafted, open, or blocked. The catalog counts live there and only there — this page links to them instead of copying them, so there is a single place to update when the catalog moves. A proposition that chains one skill through several hosts, or several skills inside one host, closes more than one cell per run — that is the shape we prefer, because the parallel budget is small.

## What counts as an entry

- The artifact was produced in a real host — not a mock, and not a screenshot of a unit test.
- One sentence stating what it proves. An artifact without that sentence is not an entry.
- Host version, adapter and core versions, and the verification level reached:
  - **in-host** — the host really executed it
  - **gateway** — the instance registered and routed
  - **real tool return** — the tool returned real values, not a wrapped `success` over a backend error
  - **cross-host conservation** — data survived a transfer (vertex counts, bounding boxes, units, up-axis)
- Failures are entries too. A reproduction of a wall we hit, with the failure captured, is more useful than a claim.

## What we deliberately do not claim

Each sample was produced on a specific host version with specific adapter and core versions. It is not a blanket "we support X" statement. When you reuse these artifacts, keep the version and the verification level attached — that pairing is what makes a sample honest.

If a sample shows a capability that was partly reached with in-host scripting rather than through the MCP tool surface, the entry says so. "It rendered" and "it is orchestratable over MCP" are different claims, and only the first one is proven until the second one is.

## Repository layout

```text
media/   approved artifacts, grouped by proposition
```

Large media should go through Git LFS or an external link. Do not commit large binaries directly — this repository is meant to stay cheap to clone.

Adapter repositories carry a single hero still, one line of explanation, and a link back here. The heavy media lives in this repository, so adapter repos keep their clone cost and their release cadence to themselves.

## Reproducing an entry

Open an issue with the proposition you tried, the host and version, and the adapter/core versions. Include what you got back from the tool calls — entries are accepted or rejected on real return values, not on a reported success flag.

## License

MIT — see [LICENSE](LICENSE).
