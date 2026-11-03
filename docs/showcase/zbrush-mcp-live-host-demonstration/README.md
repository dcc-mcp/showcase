# Live ZBrush 2027 host demonstration

This case is **not** a generated picture, a capability inventory, or a record of
loading MCP skills. It is a machine-readable ledger of one real ZBrush 2027.0.1
GUI session in which `dcc-mcp-zbrush` actually did work on a real scene and
returned real values from real tool calls. The scene work ran through the
adapter's socket-bridge JSON-RPC layer; MCP `tools/call` succeeded only for
`affinity: any` tools, so this is **not** a completed MCP capability
demonstration (see **Acceptance boundary**).

## What really happened

A signed `ZBrush.exe` (ProductVersion `2027, 0, 1, 1`, Authenticode `Valid`) was
launched from a clean process state. A disposable user-assets directory loaded the
unmodified socket bridge on the host main thread through the ZBrush startup hook.
A sidecar MCP server was started against that live bridge. The run then exercised
three layers, ending with a graceful close that left no ZBrush process and no
listeners behind.

| Layer | Transport | Real calls | What it proves |
| --- | --- | --- | --- |
| 0 | direct in-host invocation | 5 | Real `zbrush.commands` SDK values and a real reversible state mutation |
| 1 | JSON-RPC over the socket bridge | 10 | The main-thread pump dispatches real SDK handlers: import, subdivide, measure, export |
| 2 | MCP `initialize` / `tools/list` / `tools/call` over `/mcp` | 7 | A real MCP server bound to the live host returns 3 real tool results and 4 real main-affinity errors |

### Layer 0 — inside the real host VM

`get_session_info`, `get_scene_info` and `list_subtools` returned real host state.
The host reported `zbrush_info(0) = 2027.0009765625`, `zbrush_info(1) = 2`,
embedded Python `3.11.9`, and 149 public `zbrush.commands` callables. A real
`execute_python` call performed a get / set / read / restore on `Draw:DrawSize`:
`64.0` → `64.05000305175781` → `64.0`, with `changed = true` and
`reversible = true`.

`inspect_active_mesh` **failed honestly** with
`ValueError: Unable to begin a Script tool editing-session.` The session starts on
`SimpleBrush`, which is not a `Polymesh3D`, so `query_mesh3d` legitimately refuses.
The failure is retained, not hidden.

### Layer 1 — real work on a real mesh

A real quad cube (`live_input_cube.obj`, 8 vertices / 6 faces) was imported with
`import_to_scene`. `inspect_active_mesh` then returned 8 points, 6 faces and area
`24.0`. `refine_active_subtool` performed one real subdivision
(`subdivision_levels = 1`). The next `inspect_active_mesh` returned 26 points,
24 faces and area `11.936315536499023`. `export_active_subtool_obj` wrote the
mutated mesh to `live_exported.obj` (26 vertices / 24 quad faces). Both OBJ files
are published here with their SHA-256 hashes.

### Layer 2 — real MCP tool returns

The sidecar answered a real MCP `initialize` (`dcc-mcp-zbrush` `0.2.32`, protocol
`2025-06-18`) and `tools/list` (32 tools on page 1, `nextCursor` `3332`). Three
real `tools/call` results succeeded: `list_skills` returned the running catalog,
`load_skill` registered `zbrush_dialog__get_active_dialog` and
`zbrush_dialog__click_dialog_button`, and `zbrush_dialog__get_active_dialog`
returned `success: true`, `bridge_state: ready`, `zbrush_blocked: false` — a real
MCP tool return that reaches the live host bridge.

Four further `tools/call` results returned real `isError: true` responses:
`THREAD_AFFINITY_UNAVAILABLE`. The tools `get_session_info`, `get_scene_info`,
`list_subtools` and `execute_python` declare `thread_affinity=main`. Core is not
the defect: with no host dispatcher attached (`host_dispatcher_attached=False`)
its Rust dispatcher correctly refuses declared main-affinity actions rather than
running them off the host main thread. The missing wiring is in the adapter. In
sidecar mode `dcc-mcp-zbrush` registers only its in-process executor
(`_executor.py` calls `register_inprocess_executor()` and attaches no
`QueueDispatcher` or `BlockingDispatcher`), and the sidecar main loop (`cli.py`)
only sleeps instead of pumping main-thread work. Core's `attach_dispatcher()` is
a no-op in sidecar mode, so `resolve_host_dispatcher()` returns `None` and only
`affinity: any` tools execute over MCP HTTP. **This is an unfixed adapter-side
wiring defect, not a Core design defect and not a demonstration failure.** The
same tools do real work through Layer 1's socket bridge, which has its own host
main-thread pump. Closing this gap requires a separately authorized adapter
change; this entry does not make that change, does not change Core, and does not
claim the defect is fixed.

## Acceptance boundary

**"A complete capability demonstration using MCP to do real work" is NOT closed
by this case.** Only 3 of 7 MCP `tools/call` succeeded, and all 3 were
`affinity: any` catalog or dialog tools. The four real scene-work tools returned
`THREAD_AFFINITY_UNAVAILABLE`. The OBJ import, subdivision, measurement and
export were performed through Layer 1's socket-bridge JSON-RPC, which is a
transport inside `dcc-mcp-zbrush` but is **not** the MCP `tools/call` path.
Socket-bridge success therefore does not establish that MCP HTTP can complete
ZBrush scene work. The case stays a Draft, unlisted, media-free, unmerged and
undeployed evidence archive; no acceptance, approval, gallery selection or
release is claimed.

## What is deliberately not claimed

- No viewport screenshot, render, turntable or video. A content-free GUI window
  diagnostic was collected but reported `proof_passed: false` (`root_overlap`),
  so no host media is claimed. The OBJ artifacts are real geometry, not images.
- No claim that MCP HTTP `tools/call` completed ZBrush scene work, or that the
  "complete capability demonstration" acceptance is met. Only 3 of 7 calls
  succeeded (`affinity: any` catalog/dialog tools); the four `affinity: main`
  scene tools returned `THREAD_AFFINITY_UNAVAILABLE`. The real OBJ import,
  subdivision and export are Layer 1 socket-bridge JSON-RPC, not MCP `tools/call`.
- No gallery selection, merge, deployment or live-page read-back. This case is
  registered as an unlisted review case in `unlisted-cases.json` in the same Draft
  PR.
- No independent exact-head review, CI gate or release authorization.
- No private paths, machine names, loopback addresses, task IDs or credentials.
  The published ledger is a redacted derivation of the privately retained raw
  captures.
- No full raw TCP/MCP capture set and no independently verifiable raw-to-derived
  transform receipt. Only the redacted derived ledger plus recorded hashes are
  published, so a reader cannot re-derive the ledger from this entry alone.

## Reproducing the verification

`verify_live_host_evidence.py` re-checks the published ledger and both OBJ
artifacts without rerunning ZBrush. It validates host identity, the reversible
mutation, the geometry change, artifact hashes and geometry, MCP return counts,
the documented affinity limitation, lifecycle cleanup and a private-data scan.
The result is written to `live_host_evidence_result.json`.

```
python verify_live_host_evidence.py
python scripts/validate_entry.py docs/showcase/zbrush-mcp-live-host-demonstration
```

The verifier checks the **recorded evidence**; it does not re-execute the host
session. Re-running the live session requires a real ZBrush installation, a
disposable user-assets directory and a GUI-capable host.

## Environment

| Item | Value |
| --- | --- |
| Host | ZBrush 2027.0.1 (`2027, 0, 1, 1`) |
| Host Python | 3.11.9 (embedded) |
| Adapter | `dcc-mcp-zbrush` 0.2.32 |
| Core | `dcc-mcp-core` 0.20.52 |
| Sidecar | gateway port 0, MCP on a loopback port, bridge on a loopback port |
| Verification level | `real_host_tool_returns_recorded_and_self_consistency_verified` |
