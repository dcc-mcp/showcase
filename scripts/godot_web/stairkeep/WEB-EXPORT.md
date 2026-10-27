# Stairkeep Web export preparation

This isolated candidate uses the existing official **Godot 4.7.2** editor,
GDScript and Compatibility renderer. It does not modify the existing Godot
4.6.3 shared showcase runtime, add a gallery entry, publish a site, or establish
browser acceptance.

## Verified official template source

- [Official 4.7.2 stable archive](https://godotengine.org/download/archive/4.7.2-stable/).
- [Official template download](https://godot-releases.nbg1.your-objectstorage.com/4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz), linked by that archive page.
- [Official SHA512-SUMS.txt](https://github.com/godotengine/godot-builds/releases/download/4.7.2-stable/SHA512-SUMS.txt).
- Whole archive: **1,281,349,702 bytes**, SHA-512
  `ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079`.

The current acquisition downloaded the complete archive through 77 strict HTTP
ranges, joined them in order, and matched its SHA-512 before extracting either
template. It did not execute the downloaded archive or its contents.

| Extracted file | Bytes | SHA-256 |
| --- | ---: | --- |
| `web_nothreads_release.zip` | 10,245,903 | `d3ee2f08cef0cf3cf6678a6355a92a8db48ccdd35cbd2e8bfd5f0e8a0b4032a0` |
| `web_nothreads_debug.zip` | 10,232,720 | `08962aefef811b603541d7951ac67ef00413aad2d978855183c28adee98f626a` |
| `version.txt` | 13 | `38885c88f75abbc797a1db7559719800279a00cfb9fa8b2e2868a7f6f84bad2e` |

The template's version is `4.7.2.stable`. The exporter requires the observed
installed editor's exact version `4.7.2.stable.official.ed1daf0bf`, records its
actual executable hash, and checks every exported engine runtime file against
the selected official template. An executable's own reported version is not an
independent attestation of its origin.

## Reproduce

From the showcase root, with Python's standard library and an already authorized
existing Godot executable:

```text
python scripts/godot_web/stairkeep/fetch_web_templates.py --output <template-cache>
python scripts/godot_web/stairkeep/export_web.py --godot <existing-godot-4.7.2> --templates <template-cache> --output <new-empty-output>
```

The fetcher only downloads known official data. The exporter copies source into
an isolated temporary directory, creates isolated user-data/template locations,
runs native import and release export headlessly, rejects script/import errors,
and writes the untouched official HTML loader plus its pack/runtime files.
`export-provenance.json` binds source and output file hashes to this run.

The committed preset disables threads, extensions, PWA and service workers.
No COOP/COEP workaround is used. HTTP, WebGL 2.0, real input, save persistence,
reload/reset, resizing and audio still need an authorized actual-browser test.
An exported pack or successful HTTP response alone does not pass those tests.

## Runtime notices

Godot is MIT, and its binary includes third-party components with their own
notices. Preserve both [Godot LICENSE.txt](notices/godot/LICENSE.txt) and
[Godot COPYRIGHT.txt](notices/godot/COPYRIGHT.txt) with any delivered Web build.
These are copied byte-for-byte from the official `4.7.2-stable` source tag;
the fetcher pins both source file hashes. The exporter copies them to the review
output's `notices/` directory. Asset-pack and demo licenses remain separate.

Only Python syntax checks and pure-data download/hash verification were run
during this preparation. The parent task owns actual Godot export and browser
acceptance; no runtime, browser, GUI or software installation was run here.
