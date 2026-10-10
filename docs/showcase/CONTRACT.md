# Showcase entry contract

An entry is not a screenshot with a caption. It is a **claim, a set of
artifacts, and the numbers that let someone else check the claim without
running anything**.

This contract is what separates a sample that can be quoted externally from a
picture nobody can verify.

## Layout

Before production in any DCC, follow the shared [production reuse gate](https://github.com/dcc-mcp/dcc-mcp-core/blob/main/crates/dcc-mcp-gateway/src/gateway/native_resources/agent_workflows.md#production-reuse-gate).
Record bounded discovery and candidate evaluation before implementation.
Blender must reuse the existing `blender-extension-store` provider to
`blender-extensions` host package chain when suitable; see the shared example.

For plugin/asset reuse claims, retain dated evidence for real discovery,
exact-version acquisition and checksum verification, installation/enabling,
MCP capability calls, parameter/seed recipe, native save/reopen, and independent
rebuild from a blank scene. In `validation.json`, bind each completed step to
its actual tool return and measured host/artifact result; inventory retained
evidence in `manifest.json`. Compare rebuild counts, geometry/bounds, materials
and controlled renders against declared tolerances. Record missing steps in
`not_claimed`; structural validation alone cannot certify this production gate.

Separate historical evidence from new acceptance runs. New experiments cannot
retroactively prove old provider discovery/download or zero-scene rebuilding.
Canal v11 remains under quality review with those gaps, without automatic
publication. Internal Unreal scenes must not be publicly distributed.

One directory per entry, named after the proposition slug:

```text
docs/showcase/<slug>/
├── README.md          the report  — human-readable, one claim, real numbers
├── manifest.json      the inventory — every artifact, with sha256 and bytes
├── validation.json    the evidence — machine-readable measurements
├── .gitattributes     only when an artifact must not be line-mangled
└── <artifacts...>     images, scene files, transfer payloads
```

`README.md`, `manifest.json` and `validation.json` are all three mandatory.
An entry missing one of them is a draft, not an entry.

## 1. `README.md` — the report

Written for someone who will not run anything. It must contain, in this order:

1. **A title that is the claim** — one line, not a topic label.
   "Blender to Maya: what survives an OBJ round trip" states a question;
   "Cross-host transfer" does not.
2. **One hero artifact**, shown, immediately under the title.
3. **A lead paragraph** stating what it proves and the headline numbers
   (counts, dimensions, resolutions) with units.
4. **An artifact link row** — every artifact, plus `validation.json` and
   `manifest.json`, linked from one line so nothing is orphaned.
5. **Body sections** carrying the remaining artifacts, each with the
   measurements it supports. Use tables for anything that repeats across
   channels, hosts, or files.
6. **A reproduction section** — what to open, which settings, what to look at.
7. **Boundaries** — what is *not* claimed. This is not boilerplate; it is the
   part that keeps the rest honest.

Rules:

- Every number in the prose must exist in `validation.json` or `manifest.json`.
  If it cannot be traced to one of those two files, delete it.
- Captures are unretouched. Cropping to frame the subject is fine; removing a
  control or a failure read-out is not. Say which, when it matters.
- Failures are reported with the same prominence as passes. An entry that
  shows four walls is worth more than one that shows an unqualified success.

## 2. `manifest.json` — the inventory

Machine-checkable proof that the artifacts are the ones discussed.

```json
{
  "schema_version": 1,
  "reference": "<optional path or URL the sample was built against>",
  "entries": { }
}
```

Top-level keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | `1` for the layout on this page |
| `reference` | What the sample was built from, if any |
| `<host>_application` / `<host>_version` | One pair per host that actually ran |
| `capture_provider` | How screens were captured (`host-native` / `dcc-cua` / `desktop`) |
| `files[]` | One record per artifact (see below) |

Each `files[]` record carries `path`, `sha256` and `bytes` — always. Images
additionally carry `width`, `height` and `bit_depth`. Binary payloads carry
whatever identifies them structurally (node counts, dependency lists,
container kind).

`sha256` is over the committed bytes. A reader can re-hash a file and know
they are looking at the same artifact the report describes.

## 3. `validation.json` — the evidence

The measurements. Shape is free; the standard is that **each value is
measurable and was measured**, not asserted.

What it must capture:

- **Environment**: host names and versions, adapter/core versions, render or
  export engine, resolution, sample count — whatever governs the numbers.
- **Counts**: objects, meshes, vertices, faces, images, nodes.
- **Geometry**: bounding boxes with a unit suffix on every key
  (`bbox_min_m`, `dims_m`) so the unit can never be inferred wrongly.
- **Conservation results**, for a cross-host entry: the same quantity measured
  at each stage, with a `match: true | false` per stage pair.
- **Explicit verdicts**: a `checks[]` array, one item per claim, each with
  `name`, `result` (`pass` / `fail`) and the observed values. A `fail` carries
  `expected` and `observed`.
- **Boundaries**: a `not_claimed[]` array. Say plainly what the run did not
  establish.

There is no requirement that every check passes. An entry whose `checks[]`
contains four `fail` results, each with observed values, is a better entry
than one with a single unqualified `pass`.

## 4. Artifact specs

| Kind | When | Spec |
| --- | --- | --- |
| Still PNG / JPG | scenes, materials, renders, failure read-outs | width ≤ 1600; above 400 KB convert to JPEG q82 |
| GIF | animation, simulation, turntable, process | ≤ 12 fps, width 900, looping, ≤ 8 MB |
| Video MP4 | multi-step flows, cross-host chains, narration | H.264, width 1280, ≤ 60 s |
| Before / after | gap propositions | side-by-side or split screen, "expected vs actual" |

Prefer host-native capture — a host viewport grab or render output proves the
host really executed, and it is worth more than a desktop screenshot of the
same thing. Desktop captures are the fallback, and they are the ones that leak
absolute paths and tokens into the frame. **Read every capture back before
committing it.**

Large media goes through Git LFS or an external link. This repository is meant
to stay cheap to clone.

## 5. Verification level

Every entry states the deepest level it actually reached:

| Level | Means |
| --- | --- |
| **in-host** | the host really executed the operation |
| **gateway** | the instance registered and routed |
| **real tool return** | the tool returned real values, not a wrapped `success` over a backend error |
| **cross-host conservation** | data survived a transfer — counts, bounding boxes, units, up-axis |

`in-host` alone is not `real tool return`. Saying "it exported" is a weaker
claim than "it is orchestratable over MCP", and only the first is proven until
the second one is measured.

## 6. Verifying an entry

```bash
python scripts/validate_entry.py docs/showcase/<slug>
```

Checks that the three mandatory files exist, that `manifest.json` covers
exactly the artifacts on disk with matching sha256 and byte counts, that
`validation.json` carries the required top-level keys, and that no image
exceeds the size spec. Exit code 0 means the entry is structurally complete.
It does not mean the numbers are right — only that they are present and
traceable.

## Model and effort attribution

Every selected case must include nonempty `model_attribution` and
`revision_notes` arrays. Add `model_attribution` rows with `stage_id`, `stage`, `model`,
`reasoning_effort`, `record_status`, `basis` and `scope`. Separate planning,
creation, code, reference generation, post-production and independent review.
The stable IDs `planning`, `creation`, `code`, `reference` and `post_production`
are required, plus at least one of `review`, `review_visual` or `review_technical`.
Use both separate review rows when their scopes differ. Display labels remain
independent of these IDs. IDs and display labels must be unique.
Use `unknown` records with an exact unknown model and effort value (for example
`Unknown` or `未知`, not a model name with an unknown qualifier) when production
evidence is absent. `configured` requires an accepted task configuration
record actually checked by the reviewer; a report's self-description or a
later reviewer's configuration is insufficient. The validator checks structure,
not the factual authenticity of that record. `receipt_bound` is not supported
and must fail validation until a receipt-reference and result-binding contract
is implemented. Do not infer historical creation from a current review or
publish private prompts, task IDs, or execution paths such as absolute workspace,
temporary-directory, or home-directory paths.

Add dated `revision_notes` (`version`, ISO `date`, `change`) for documentation,
review or asset updates. Keep old native files and evidence. A documentation
revision or a new visual version retains the same case slug and case count.
