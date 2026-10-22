# Reproduce the exact preview wheel

This build was independently repeated in a fresh environment from public base
`ea9270a82bd0821993f0c611d9cad2d36e06405d` plus `preview-only.patch`.
All 69 resulting tracked source files matched the qualified snapshot, and the
wheel reproduced byte for byte:

- File: `dcc_mcp_gimp-0.4.1-py3-none-any.whl`
- Size: 97,073 bytes
- SHA-256: `adb43849349ca54944bd9280a8497d90bca77e6726733c3fca5991164fe1a1ad`
- Patched source tree: `4e855af540036b3ab5ee041be5402f3bc0f98dc7`

The tested build uses CPython 3.12.14 on Linux x86_64 and zlib 1.3.2. The eight
exact build dependency versions are in `build-requirements.txt`. Other toolchain
combinations have not been qualified for the same compressed wheel digest.

Hatchling 1.32.4 uses `1580601600` as its default reproducible timestamp when
SOURCE_DATE_EPOCH is unset. The original qualified wheel used that default. The
fresh repeat explicitly set `SOURCE_DATE_EPOCH=1580601600`; every ZIP entry has
2020-02-02 00:00:00 as its timestamp. Do not substitute a new epoch.

Run from an otherwise new package directory containing this handoff. Use the
qualified Python/zlib combination and make sure `source/` does not already exist:

```sh
git clone https://github.com/dcc-mcp/dcc-mcp-gimp source
git -C source checkout --detach ea9270a82bd0821993f0c611d9cad2d36e06405d
git -C source apply --check ../preview-only.patch
git -C source apply ../preview-only.patch
python3.12 -m venv build-venv
build-venv/bin/python -m pip install -r build-requirements.txt
SOURCE_DATE_EPOCH=1580601600 build-venv/bin/python -m build --no-isolation --outdir dist source
sha256sum dist/dcc_mcp_gimp-0.4.1-py3-none-any.whl
```

The command builds an sdist, then builds the wheel from that sdist. Preserve LF
source bytes. Stop if the output size or SHA-256 differs; do not loosen the digest
or regenerate a native binding to accept an unqualified build.

## Use with a separately supplied native qualification package

The audited native fixture expects the patched repository bytes in relative
`source/` and the exact wheel in relative `dist/`. Supply those directories beside
its original `reproduce/`, `inputs/` and `candidate-binding.json`. Its original six
helper files, input files and binding must stay byte-identical. Install the wheel
into the separately configured, qualified runtime environment before running the
fixture's file-only `--check`; the build-only environment above is insufficient
for native execution.

The binding's `candidate_commit` identifies the historical local candidate used
for the original native qualification. The exact content tree and per-file hashes
remain authoritative even when a separate public PR or release has a different
Git commit identity. Record that later public identity separately after verifying
its bytes; do not rewrite the original qualification record to imply it ran later
public commits.

`reproduce/seal_candidate.py`, when present in that separately supplied package,
is qualification-maintenance tooling. It is not a user reproduction step. Do not
run it to reseal inputs, source or wheels, and do not edit the six audited helper
files. Only the reviewed `--check`/`--run` lifecycle should execute the native
fixture. `wheel-reproduction.json` records the demonstrated fresh-build result.

This source PR handoff contains no native fixture or production artwork. The
separately supplied native package owns those artifacts and its own scope.
