# Brand gallery publication contract

The existing showcase collection remains independent. The actual first-batch
`brand-gallery.json` uses `schema_version: 1`, a boolean `enabled`, a safe local
`manifest` pointer and its `manifest_sha256`. The producer's schema-2 manifest
is the single authoritative asset inventory. Its public snapshot retains the
original snapshot hash and declares metadata redactions; artwork files remain
byte-identical. Do not maintain a duplicate webpage asset map.

`scripts/brand_manifest.py` derives the renderer's schema-1 catalog at build
time. It cross-checks actual family/file counts, the two-theme output matrix,
per-output successful MCP responses and hashes, recorded versions, visual
review and precise acceptance limits. This mapping supports the reviewed core
and six software families. Later families require their own completed handoff and
an explicit reviewed mapping; extra files in the producer directory are never
selected by crawling. Missing or disabled catalogs publish zero brand files.
Pending placeholders are local development content only.

For legacy fixtures the validator also accepts the direct catalog shape:
`title`, `description`, `updated_at`, and verified `items`. The following
fields describe the derived renderer data, not a second production manifest.

Each item records:

- `slug`, `title`, `family`, `software`, `summary`, `status: "verified"`, and
  an ISO `verified_at`. An optional `version` describes the actual artwork
  revision; do not invent it.
- `previews.light` and `previews.dark`, each with a local `src` and accurate
  `alt`. They must reference validated downloadable variants. Background
  switching previews these delivered files; web code does not redraw logos.
- Optional `small_previews` requires the actual light/dark 128px PNGs with
  `src`, `alt`, `width` and `height` matching the validated variants. Show
  them at their original 128px CSS width instead of downscaling a large export.
- `variants`: `label`, local `url`, `format` (`svg` or `png`), actual `bytes`,
  SHA-256, and `rights_ids`. PNGs include actual `width` and `height`; SVGs
  include the actual numeric `viewBox`. Each file has a `source` object or
  `source_id` referencing `sources`.
- `prompt` (`kind`, `text`, `note`), `environment` (`label`, `value`),
  `tools` (`name`, `description`), `steps` (`title`, `description`, optional
  validated image), and `checks` (`name`, `result`, `observed`). State real
  Inkscape, adapter and DCC-MCP Core versions, and evidence limits.
- `evidence` (`label`, `url`), including at least one local JSON record of
  the actual successful tool requests and responses with explicit scope.
  Every listed tool must be supported by the record. A tool-name list is
  insufficient. Keep private raw logs outside this repository.
- `sources`: `id`, `label`, `url`, and either a full 40-character source
  commit pinned in the URL or SHA-256 of the original material.
- `rights`: `id`, `holder`, `license`, `scope`, `url`, and `notice`.
  Attribute user-contributed DCC-MCP artwork separately from source originals
  and any vendor trademarks. Composite assets can reference multiple rights.
- `contributors` and `limitations`, including the actual scope of visual,
  geometric, export and re-open validation.

Produce logo construction and software exports through DCC-MCP. Record
the real tool calls. Ordinary web tools may implement this gallery, but
must not manufacture a purported DCC production trace or corrected asset.

Review the source reference and corrected C curves visually before selecting
assets. Check family consistency, dimensions, vector geometry, delivered
light/dark variants and small-size readability. Run the contract tests,
validator, build integration guards and normal site build before publishing.
The contract rejects unverified items, inconsistent hashes/dimensions, private
paths and addresses, active SVG content, external SVG dependencies, missing
  rights and inadequate MCP records. It checks consistency of supplied evidence;
it does not establish authenticity or visual quality by itself.

Use the user's PC8 browser to verify gallery navigation, combined family and
software filters, search/empty/reset, desktop/mobile overflow, decoded media,
background switching, detail/back, keyboard access and downloaded file hashes.
Record browser ownership accurately. Only then enable the catalog, use the
normal repository PR/Pages process, and verify the actual public URL again.

The core-first release has eight actual files. The incremental snapshot adds
six software families with 16 files each: seven partially delivered families
out of 37 planned, with 104 actual files. Core's remaining variants, each new
family's currentColor outlined SVG and the other 30 families are not completed.
CurrentColor native SVGs retain live text; their raster exports are fixed
black PNGs and cannot inherit CSS color. Normal release SVGs are outlined.
New family QA and source/rights records must match actual file bytes, motifs,
output receipts and optical 128 × 60 PNGs. Old drawing briefs are plans, not
final geometry evidence. Show progress and plans as text without dead
downloads. Production source and public draft commits share the `src` subtree;
their complete repository trees differ by a test-fixture change. Do not claim
the public review commit was the production runtime, partial core GUI
observation was complete canvas or six-family GUI acceptance, or the user has
already approved the design. Original reference
imagery whose redistribution terms are not established stays outside this
publication batch.
