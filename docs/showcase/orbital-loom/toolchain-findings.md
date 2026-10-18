# Toolchain findings, reproduced 2026-10-11

## Verified baseline
Official Blender 4.5.14 Linux archive, SHA256 9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3, verified against Blender release checksum list. Official PyPI adapter 0.2.16, Core and Server 0.20.42. Official release CLI 0.20.42 installed using its checksum-checking installation script.

## Version-contract gap
The adapter's current README documents `gateway_remote_port=0`. With Core 0.20.42 this throws during BlenderMcpServer construction: `Installed dcc-mcp-core lacks public remote gateway options; upgrade Core before configuring gateway_remote_host or gateway_remote_port`.
`inspect.signature(DccServerOptions.from_env)` in this exact wheel has neither remote keyword; GatewayOptions has only port, registry_dir, dcc_version, scene, enable_failover, strict_gateway.
Reproducer: start Blender 4.5.14 with a BlockingDispatcher and BlenderMcpServer(port=0, dispatcher=dispatcher, gateway_port=19765, gateway_remote_port=0).
The default gateway enables both loopback19765 and remotewildcard-address:59765. That test was stopped, not retained as the production path.
Safe supported resolution for this run: gateway_port=0 disables the gateway entirely; the embedded MCP endpoint remains bound to loopback on an ephemeral port. This is not evidence of shared-gateway acceptance.
Source: https://github.com/dcc-mcp/dcc-mcp-blender/blob/main/README.md (private-gateway example).

## Sandboxed runtime configuration
A read-only home makes discover_skills fail in get_skills_dir. Isolated writable HOME and XDG_DATA_HOME/XDG_CONFIG_HOME/XDG_CACHE_HOME resolve this through supported environment configuration. No permissions are broadened.

## Direct CLI limitations
CLI load-skill against the embedded endpoint succeeds. CLI call with explicit dcc-type/instance-id gets HTTP404 against that endpoint; forcing MCP reports that MCP requires a gateway slug and direct backend calls need REST routing. The production controller therefore calls the advertised embedded endpoint with standard JSON-RPC tools/call. Typed create_object and get_scene_info both returned isError=false and success=true, including the new cube name and object count. Do not describe this as CLI gateway coverage.

Raw local service logs are intentionally not public deliverables. Public receipts should be reduced to operation, versions, result and artifact hashes.

## Typed driver channel defect
A real isolated MCP probe of `blender_rigging__set_driver` confirmed that `rotation_euler.z` fails with `ValueError: path includes index, must be a separate argument`. The schema does not expose `array_index`, despite its component-path example. Passing only `rotation_euler` instead reports success but creates three drivers, setting only X to the expression and adding Y/Z drivers at zero. At frame 10 the expression `frame/10` evaluated to [1,0,0], with unwanted zero-valued Y/Z drivers. See `driver-probe.json` for sanitized arguments and readback. This is why this production keeps explicit per-axis driver authoring in the declared scripting route. A fix requires indexed channel support and regression tests that assert unrelated channels remain untouched.

### Case-to-fix follow-through

The isolated driver probe led to [draft adapter PR #298](https://github.com/dcc-mcp/dcc-mcp-blender/pull/298), verified head `4f7fa972da11d5319a9a05748d8736b4a54ab62a`. Its explicit array-index contract and sibling-axis preservation are a subsequent repair. It was open and draft when checked; it was not merged, deployed, or installed into this rendering environment. The film continues to represent released adapter 0.2.16 with the disclosed scripting workaround. Consult the PR for its distinct test and CI evidence rather than attributing those results to this production run.
