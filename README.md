# DCC-MCP Showcase

A collection of real DCC-MCP work, with reusable prompts, process images,
software versions, evidence boundaries and downloadable source resources.

GitHub Pages destination: [dcc-mcp.github.io/showcase](https://dcc-mcp.github.io/showcase/).
Deployment is produced from `main` by the repository's existing Pages workflow.
The collection is part of [the DCC-MCP project](https://dcc-mcp.github.io/),
with [installation and agent setup](https://dcc-mcp.github.io/zh/agents),
[Core / Gateway / CLI](https://github.com/dcc-mcp/dcc-mcp-core), and each
case's software adapter linked from the site. The official site's broader
[examples](https://dcc-mcp.github.io/examples) remain distinct from the
collection's downloadable, individually documented case records.

The collection combines a procedural Houdini studio study produced in this
round through DCC-MCP with two published Substance 3D Designer studies: a
weathered crate with Blender lookdev, and a procedural painted-wood material.
Each detail page distinguishes actual execution from historical evidence.
The historical studies were not reproduced in this round; their original
conversation prompts and complete MCP traces were not published, so their
prompts are clearly labeled adaptations for future reproduction.

The Houdini study records actual modeling, materials, lighting, rendering,
saved-project reopening and OBJ export/reimport. Its public records explain
trace coverage and the observed Mantra resolution issue. The native HIP is
retained privately because automatic saved-file metadata contains personal
machine information; the public reproduction resources do not include it.
The public package supplies the verified OBJ and an ordered typed MCP replay
for editable reconstruction. This is not a native HIP download. The current
official save APIs were investigated without finding a validated complete
metadata sanitizer. PNG author metadata is removed through the adapter's
MCP automation tool; compressed image data and decoded pixels remain identical.

## Browse and reproduce

The wall supports software and capability filters and a text search. Each
static detail page provides the goal, prompt, process, intermediate and final
images, tools and version records, measured checks, source links and attribution.
Source files remain in their original repositories; web images are optimized
derivatives whose provenance and hashes are recorded beside each entry.

`collection.json` is the publication inventory. Only its selected cases and
their explicit public references enter the Pages artifact. Older experimental
reports remain available in this repository but are outside the collection:
some used direct host scripting and do not establish an end-to-end MCP run.

## Build and check

Python 3.12 or later; no build dependencies.

```powershell
python scripts/validate_entry.py docs/showcase
python scripts/test_validate_collection.py
python scripts/validate_collection.py
python scripts/test_validate_brand_gallery.py
python scripts/validate_brand_gallery.py
python scripts/test_brand_manifest.py
python scripts/test_brand_build.py
python scripts/test_build_site.py
python scripts/build_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

Open the local address in the user's own browser. Before publishing, check the
wall and details on desktop and mobile, filters/search, media, back navigation,
resource links, keyboard access and the empty state. Build/contract checks do
not substitute for browser acceptance.

## Brand gallery

The [brand gallery](https://dcc-mcp.github.io/showcase/brands/) separately
selects resources without changing the three-case collection. The first core
release contains eight verified files. Incremental batches add Maya,
3ds Max, Blender, Houdini, ZBrush, Photoshop, MotionBuilder, Nuke and OpenUSD
families with 16 files each, plus three actual core currentColor SVGs:
ten actual families and 155 files out of 37 planned families. All artwork
is authored and exported through DCC-MCP in Inkscape; family names identify
referenced workflows, not the software used for these production calls.
Other Core variants, nine software-family currentColor outlined SVGs and the remaining 27
families are pending. Plans have no placeholder download links.

`brand-gallery.json` points to the producer's authoritative
`docs/brands/brand-family-v2/manifest.json` public snapshot. The builder derives
page data at runtime; it does not keep a second hand-maintained asset inventory.
Original SVG/PNG bytes remain unchanged. The snapshot preserves the original
manifest hash and documents removal of private routing, paths and process IDs.
155 real successful gateway requests/responses (49 builds and 106 exports),
per-file family QA and the geometric/raster review are published with explicit
evidence coverage. This site integration
did not rerun Inkscape production. The installed development adapter and its
public draft source are distinct from a released integration. Actual per-output
revisions remain recorded: 118 outputs use the historical `7657bafe` source,
37 use the repaired `fd5a71d4` source. Its source tree differs from the older
implementation; old outputs are not represented as new-version reruns.

Live-text native SVGs retain editable Montserrat text; editing that text
requires the corresponding font. Outlined native and release SVGs edit glyphs
as paths and display independently of that installation. Project-owned
geometry is MIT, font inputs retain SIL OFL notices, and brand/trademark rights
remain reserved. The old reference image is not redistributed in this batch.
The corrected core has a partial native GUI observation; the complete canvas
and the software families and new core currentColor files have not passed full
GUI acceptance. Final design approval
is still awaiting user feedback. C1's checks establish G1 within rounding and
do not establish G2 or uniform thickness.

For local layout review only:

```powershell
python scripts/build_site.py --preview-brands --out _site-brand-preview
python -m http.server 8766 --bind 127.0.0.1 --directory _site-brand-preview
```

This explicitly marked development preview uses pending text, with no asset
images or download links, and is excluded from the normal Pages workflow.
The preview flag refuses the production output directory. See the
[brand contract](docs/brands/CONTRACT.md) for the asset handoff and publication
checks. In production each mark includes background previews, verified SVG
and PNG downloads, file hashes, source provenance, rights, software versions,
actual MCP tools and evidence boundaries. A missing or disabled brand catalog
adds zero brand files to production. The site code's MIT license does not
relicense software vendors' trademarks or source artwork.

## Add a case

Follow [the entry contract](docs/showcase/CONTRACT.md). Record actual DCC-MCP
tools and host versions, preserve intermediate and final artifacts, and state
precisely what was measured. Mark unknown versions and missing evidence as
unrecorded. A successful build confirms structure and file integrity, not a
new host run or the truth of every historical measurement.

Retain authorship and asset licenses. Check images and text for credentials,
private paths, internal addresses and unrelated content before selecting a
case. New DCC work must use DCC-MCP; do not present direct host scripts or
external software automation as an MCP run.

## Native projects and reproduction packages

Case pages link to native scene and material files when available. Keep large
engineering packages in a release of this repository rather than preloading
them with the gallery. Each package should include its original authorship,
asset-specific license, software and plugin requirements, reproduction steps,
actual MCP call records, a file inventory and SHA-256 checksums. Verify archive
extraction and references; report whether opening the saved project was tested.
Do not redistribute commercial libraries merely because a scene references
them. Keep private execution logs outside the public package and describe any
redactions in its public evidence record.

## License

Site code is [MIT](LICENSE). Each case records its source license and any
separate reference-input limitations; the site license does not relicense
third-party inputs.
