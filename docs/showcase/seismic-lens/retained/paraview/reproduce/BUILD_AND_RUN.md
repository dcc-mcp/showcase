# Reproduce from the merged public ParaView source

This recipe pins public commit
`4c4939b1a6ee6785d86f74461ea97ff2a34815a9`, tree
`75f8aa79611f97bdbee4c6337f713dbb7e6c7049`, from
https://github.com/dcc-mcp/dcc-mcp-paraview.
It does not use a development checkout or a published package release.

The checked build used Linux, Python 3.12.14 and Hatchling 1.32.4. Two local
wheel builds produced identical bytes. The canonical build timestamp is the
public commit timestamp, `SOURCE_DATE_EPOCH=1791093173`.

## Build the exact wheel

Use a new build environment and source directory. The following commands use
only the public repository and ordinary package-index dependencies:

```sh
python3 -m venv build-env
build-env/bin/python -m pip install 'hatchling==1.32.4'
git init paraview-src
git -C paraview-src fetch --depth=1 https://github.com/dcc-mcp/dcc-mcp-paraview.git 4c4939b1a6ee6785d86f74461ea97ff2a34815a9
git -C paraview-src checkout --detach FETCH_HEAD
test "$(git -C paraview-src rev-parse HEAD)" = 4c4939b1a6ee6785d86f74461ea97ff2a34815a9
test "$(git -C paraview-src rev-parse HEAD^{tree})" = 75f8aa79611f97bdbee4c6337f713dbb7e6c7049
BUILD_PYTHON="$(pwd)/build-env/bin/python"
cd paraview-src
SOURCE_DATE_EPOCH=1791093173 PYTHONHASHSEED=0 "$BUILD_PYTHON" -m hatchling build -t wheel
printf '%s\n' '167b1c73796746853c348a03e4918a96eed4a24b7328587217bad0a45b516077  dist/dcc_mcp_paraview-0.1.0-py3-none-any.whl' | sha256sum -c -
cd ..
```

Expected wheel: `dcc_mcp_paraview-0.1.0-py3-none-any.whl`, 41,124 bytes,
SHA256 `167b1c73796746853c348a03e4918a96eed4a24b7328587217bad0a45b516077`.
If the hash differs, stop and compare build inputs; do not replace the binding
with an unverified hash.

## Install into a separate runtime

Use supported Python 3.12, native ParaView 5.13.2 and `ffmpeg`. The existing
proxy configuration is retained by the SDK's default HTTP transport. Install
SOCKS transport support when preparing dependencies:

```sh
python3 -m venv runtime-env
runtime-env/bin/python -m pip install \
  paraview-src/dist/dcc_mcp_paraview-0.1.0-py3-none-any.whl \
  'dcc-mcp-cli==0.20.41' 'mcp==1.30.0' 'httpx[socks]' jsonschema psutil
```

The adapter pins Core and server to 0.20.41. The recipe independently checks
Core, server and CLI 0.20.41, SDK 1.30.0, the supplied wheel hash and all 24
installed package-file hashes before creating a native session. The binding
includes the corrected skill/schema text: `scalar_bar_thickness=12` means 12
native points, not a guarantee of 12 rendered pixels. Host, font and DPI affect
pixel extent.

## Run in the owned graphical lane

Run only in the separately provisioned graphical environment with the intended
`DISPLAY`, `pvpython` and `ffmpeg` available. The recipe owns a new adapter host;
it does not attach to an existing ParaView session. Choose a new output path and
retain at least 1 GiB of free space:

```sh
mkdir -p outputs
runtime-env/bin/python reproduce/reproduce_paraview.py \
  --wheel paraview-src/dist/dcc_mcp_paraview-0.1.0-py3-none-any.whl \
  --input native/paraview/data/synthetic-lens.vti \
  --output outputs/public-paraview-run
```

The input must have SHA256
`43ade20b1f2b78149e7d948894568b599db55f5aa8f9a5ceb62050e970e93d9d`.
Existing geometry, scalar-range, decoded-pixel, native-state reopen, relocated
input, presentation equality and cleanup checks are retained. Five states are
reopened and captured again after copying the unchanged native states/data and
making the original input path unavailable. No style is reapplied during either
restore sequence. The recipe keeps file logging, jobs and checkpoints enabled,
telemetry disabled, gateway port zero and failover disabled.

The output records the public commit/tree, exact wheel, recipe hash, binding
hash and all 24 installed-file bindings alongside the native results. A source
or wheel check is not native qualification. The completed native run is preserved verbatim in `PUBLIC_NATIVE_PROOF.json`
with its original public commit, wheel and recipe identities. The current
commit changes one external documentation line only. `SOURCE_CONTINUITY.json`
verifies all package bytes are unchanged, and the new wheel differs only in ZIP
timestamps. This v3 recipe was checked by file comparison, not run in a new
native session; do not relabel the historical 210-event trace as a new run.

Coverage remains the measured presentation subset. CameraClippingRange is
explicitly unavailable through the ParaView 5.13.2 interface. Native cancellation
can leave staging files and cannot undo an already-published artifact. The input
is a synthetic illustration with illustrative units, not measured seismic data
or physics validation. Generated raw traces and logs are local validation output
and should not be published without a separate privacy review.
