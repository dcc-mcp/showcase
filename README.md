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
python scripts/test_build_site.py
python scripts/build_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

Open the local address in the user's own browser. Before publishing, check the
wall and details on desktop and mobile, filters/search, media, back navigation,
resource links, keyboard access and the empty state. Build/contract checks do
not substitute for browser acceptance.

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
