# Public workflow catalog

The gallery is the primary experience. `/agents/` is a secondary view for
readers who want to inspect production records. `/data/catalog.json` is a
discoverability index of the same selected public cases, not a released
training dataset, accepted benchmark, model leaderboard, or new license grant.

## Build contract

`scripts/agent_pages.py` exposes `generate(root, cases, demos)`, returning two
maps: HTML page inputs and generated machine-readable text. The site builder
must validate the collection and playable manifests before calling it. The
HTML enters the existing exact-text localization pipeline. The JSON is emitted
once at `data/catalog.json`, without translating original titles, provenance,
prompts, model names, checks, credits, or license text.

The catalog has its own identifier, `dcc-showcase-catalog/v1`, and numeric
`schema_version: 1`. It does not implement a production-record schema or depend
on an optional production skill or unmerged production records. An optional
production record can appear as an ordinary source reference only when it is
already part of a selected public manifest and referenced by the collection.
Its contents are not interpreted or copied into a new authority.

## Selection and integrity

- The caller supplies the already selected cases. The generator never discovers
  additional cases or crawls directories.
- The catalog reads only explicit selected-case manifests and the validated
  playable manifest. It never reads artifact, log, prompt-file, native-project,
  or archive contents. Existing prompt and workflow metadata come from the
  caller's selected collection records. The HTML page separately reuses the
  site's existing share-image helper to read cover dimensions.
- `public_references.files` contains only that case's inventoried paths. SHA-256
  and byte counts are copied exactly from the manifest and marked
  `hash_source: "manifest"`. The parent validator verifies those artifact bytes.
- `public_references.manifest` includes its exact public URL and a SHA-256 over
  the manifest bytes, marked `hash_source: "manifest-bytes"`.
- Required case reports and validation records remain linked when the existing
  publication contract selects them outside `files[]`. They are marked
  `selected-required-record-not-in-file-inventory` and receive no inferred hash.
- External source links retain their exact original URL and are marked
  `external-reference-only`; the catalog does not download or verify those
  external targets.
- Explicit local resource links must resolve inside selected inventories or
  to mandatory selected-case records. Playable links use the existing validated
  play inventory. Unknown source fields are not automatically exported.
- Selected metadata is checked with the existing private-path/credential scan.
  Unsafe paths, escaping symlinks, missing files, or malformed hash records fail
  the build. Error messages do not repeat unsafe metadata values.

Generation creates no new asset bundle, redistribution permission, or download
selection. Hashes establish byte identity, not authorship, quality or rights.

## Rights and benchmark status

Every record separates publication from rights:

```json
{
  "publication_status": "selected-public-record",
  "rights_verified": false,
  "usage_rights": {
    "display": {"status": "unknown", "evidence": []},
    "training": {"status": "not-granted", "evidence": []},
    "evaluation": {"status": "not-granted", "evidence": []}
  },
  "benchmark": {"status": "not-an-accepted-benchmark"}
}
```

`selected-public-record` says only that the existing publication selected the
record. It is not evidence of a verified display license. Training and
evaluation are separate purposes; neither is authorized by inclusion in JSON,
an accessible media URL, an unknown value, or an MIT/CC0 label elsewhere.
`not-granted` describes this catalog's lack of a verified grant, not a legal
reinterpretation or revocation of the original notices. The generator never
upgrades these fields, even if an unfamiliar input field asserts permission.

`credits` and its original `license` and `note` remain separate and unchanged.
Site-code MIT does not automatically relicense artwork or case assets. Some
cases retain independently scoped notices for code, audio, fonts or software;
their scopes must remain intact. No additional rights are granted here.

Model attribution remains stage-specific and unchanged, including unknowns.
An identified later reviewer never becomes the original creator. Check results
include failures and unrun steps; limitations and evidence scope remain visible.
Names, successful checks and publication do not produce model scores or case
acceptance. No public competitive or internal benchmark data is added.

## Future use, not current capability

A future rights-reviewed collection would need explicit, independently verified
permission for each purpose, rights holder, exact file scope and intended use.
Future filters must exclude unknown, not-granted and out-of-scope records;
display permission must not imply training or evaluation permission. Only after
that review could separate acceptance criteria, environment/version pins,
validation, and benchmark governance be considered. This index has no accepted
benchmark cases and does not claim an available dataset.

Run focused regression tests with `python scripts/test_agent_pages.py`.
