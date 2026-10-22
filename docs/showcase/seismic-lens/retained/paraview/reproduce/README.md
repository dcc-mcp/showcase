# Current public-source reproduction files

This packet pins public ParaView adapter commit
`4c4939b1a6ee6785d86f74461ea97ff2a34815a9`, tree
`75f8aa79611f97bdbee4c6337f713dbb7e6c7049`.
[PR #4](https://github.com/dcc-mcp/dcc-mcp-paraview/pull/4) changes one line in an
external qualification document to use generic publisher wording.

All 24 installed package files and all 29 wheel-entry contents remain identical
to the independently verified public-source native run. The freshly built wheel
has SHA256 `167b1c73796746853c348a03e4918a96eed4a24b7328587217bad0a45b516077`.
Its archive hash changes only because the deterministic ZIP timestamp follows
the newer commit. Building current source with the prior timestamp reproduces
the native-tested wheel byte for byte.

- `BUILD_AND_RUN.md` gives public-source fetch, deterministic build, installation
  and recipe commands
- `reproduce_paraview.py` and `paraview-package-bindings.json` pin the current
  commit, tree, fresh wheel and all 24 package files
- `SOURCE_CONTINUITY.json` and `BUILD_RECEIPT.json` record the file-only comparison
- `PUBLIC_NATIVE_PROOF.json` is preserved verbatim, including the actual executed
  commit, wheel and recipe identities, 210 trace records, 52 operations and the
  five original/reopened/relocated panel checks

The recipe differs from the executed version only in its three source/wheel
identity constants. All geometry, scalar-range, pixel, state, relocation and
cleanup checks remain unchanged. This packet does not claim a new native run.

The input dataset, images and native states are supplied by the accompanying
verified artwork bundle; they are not duplicated here. The source wheel is built
from the public repository using the documented hash. No package release or
publication is performed by preparing these files.

`MANIFEST.json` records every payload file except itself. Original execution
evidence and earlier reproduction files retain their separate identities.

`UPSTREAM-ADAPTER-LICENSE.txt` reproduces the upstream `dcc-mcp-paraview` MIT
notice verbatim. It is the notice for upstream ParaView adapter software only.
Including it does not grant MIT, CC0 or other additional rights over this case's
artwork, data, native states or newly authored showcase production recipe. Those
case materials receive no new license grant from this notice. The upstream
software notice and the rights it provides are unchanged.
