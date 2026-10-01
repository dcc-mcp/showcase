# DCC-MCP Showcase

A collection of real DCC-MCP work, with reusable prompts, process images,
software versions, evidence boundaries and downloadable source resources.

GitHub Pages destination: [dcc-mcp.github.io/showcase](https://dcc-mcp.github.io/showcase/).
Deployment is produced from `main` by the repository's existing Pages workflow.

The first collection brings together two published Substance 3D Designer
studies: a weathered crate with Blender lookdev, and a procedural painted-wood
material. Their detail pages distinguish the original public evidence from
this collection's integration work. Neither was reproduced in this round.
Original conversation prompts and complete MCP call traces were not published;
the prompts here are clearly labeled adaptations for future reproduction.

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

## License

Site code is [MIT](LICENSE). Each case records its source license and any
separate reference-input limitations; the site license does not relicense
third-party inputs.
