# Brand gallery publication contract

The existing showcase collection remains independent. `brand-gallery.json`
uses `schema_version: 1`, a boolean `enabled`, `title`, `description`,
`updated_at`, and `items`. Missing or disabled catalogs publish zero brand
files. Enabled catalogs must contain verified items; pending placeholders
are local development content only.

Each item records:

- `slug`, `title`, `family`, `software`, `summary`, `status: "verified"`, and
  an ISO `verified_at`. An optional `version` describes the actual artwork
  revision; do not invent it.
- `previews.light` and `previews.dark`, each with a local `src` and accurate
  `alt`. They must reference validated downloadable variants. Background
  switching previews these delivered files; web code does not redraw logos.
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
