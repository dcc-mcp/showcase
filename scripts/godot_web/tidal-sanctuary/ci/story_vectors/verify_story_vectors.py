"""Run committed typed-vector plans through real CLI/gateway/Inkscape tools.

Raw evidence stays in the CI artifact. This is a regression render, not an
assertion that artwork has passed visual review or is ready for publication.
"""

import argparse
import importlib.metadata
from PIL import Image, ImageChops
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plans", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.output.resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    evidence = workspace / "evidence"
    evidence.mkdir()
    env = dict(os.environ)
    for key,name in [("HOME","home"),("XDG_CONFIG_HOME","config"),("XDG_CACHE_HOME","cache"),("XDG_DATA_HOME","data")]:
        owned=workspace/name;owned.mkdir();env[key]=str(owned)
    env.update(
        {
            "DCC_MCP_REGISTRY_DIR": str(workspace / "registry"),
            "DCC_MCP_LOG_DIR": str(workspace / "logs"),
            "DCC_MCP_CHECKPOINT_DIR": str(workspace / "checkpoints"),
            "DCC_MCP_JOB_STORAGE_PATH": str(workspace / "jobs.sqlite"),
            "DCC_MCP_CLI_REQUIRE_GATEWAY": "true",
            "DCC_MCP_AGENT_SESSION_ID": "tidal-story-vector-candidate",
        }
    )
    cli = shutil.which("dcc-mcp-cli")
    gateway = shutil.which("dcc-mcp-server")
    if not cli or not gateway:
        raise RuntimeError("Install the official pinned CLI and Core server first")
    records = []
    count = 0

    def run_cli(name, *arguments):
        nonlocal count
        count += 1
        command = [cli, "--require-gateway", "--agent-session-id", "tidal-story-vector-candidate", *arguments]
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        record = {"command": command, "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        (evidence / ("%02d-%s.json" % (count, name))).write_text(json.dumps(record, indent=2))
        if result.returncode:
            raise RuntimeError("%s failed: %s" % (name, result.stderr))
        return json.loads(result.stdout)

    def call(name, slug, payload):
        request = evidence / (name + "-request.json")
        request.write_text(json.dumps(payload, indent=2))
        result = run_cli(name, "call", slug, "--json-file", str(request), "--timeout-secs", "150")
        if result.get("control_route") != "gateway" or result.get("gateway_stats_recorded") is not True:
            raise RuntimeError("Call did not preserve the required gateway route")
        if result.get("output", {}).get("success") is not True:
            raise RuntimeError("Native tool returned a failure envelope")
        records.append({"name": name, "request_id": result.get("request_id"), "route": result["control_route"]})
        return result["output"]["context"]

    logs = [open(evidence / "gateway.log", "w"), open(evidence / "adapter.log", "w")]
    processes = []
    try:
        processes.append(
            subprocess.Popen(
                [
                    gateway,
                    "gateway",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "9765",
                    "--remote-port",
                    "0",
                    "--registry-dir",
                    env["DCC_MCP_REGISTRY_DIR"],
                    "--gateway-persist",
                    "true",
                ],
                env=env,
                start_new_session=True,
                stdout=logs[0],
                stderr=subprocess.STDOUT,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "dcc_mcp_inkscape",
                    "serve",
                    "--executable",
                    "/usr/bin/inkscape",
                    "--workspace",
                    str(workspace),
                    "--gateway-port",
                    "9765",
                    "--registry-dir",
                    env["DCC_MCP_REGISTRY_DIR"],
                    "--ready-file",
                    str(evidence / "ready.json"),
                ],
                env=env,
                start_new_session=True,
                stdout=logs[1],
                stderr=subprocess.STDOUT,
            )
        )
        deadline = time.monotonic() + 30
        while not (evidence / "ready.json").is_file():
            if any(p.poll() is not None for p in processes) or time.monotonic() > deadline:
                raise RuntimeError("Native gateway/controller did not become ready")
            time.sleep(0.2)
        inventory = run_cli("inventory", "list")
        available = [i for i in inventory["instances"] if i["dcc_type"] == "inkscape" and not i.get("stale")]
        if len(available) != 1:
            raise RuntimeError("Expected one owned Inkscape instance")
        instance = available[0]["instance_id"]
        hits = run_cli("discovery", "search", "--query", "inkscape vector", "--dcc-type", "inkscape", "--limit", "10")[
            "hits"
        ]
        selected = [h for h in hits if h["instance_id"] == instance]
        if not selected or selected[0]["next_step"]["action"] != "load_skill":
            raise RuntimeError("Expected a discoverable unloaded native vector skill")
        skill = selected[0]["next_step"]["arguments"]["skill_name"]
        run_cli("load-skill", "load-skill", skill, "--instance-id", instance)
        slugs = {h["backend_tool"].split("__")[-1]: h["tool_slug"] for h in selected}
        for name in ("capabilities", "document_build", "document_inspect", "document_export"):
            run_cli(name + "-schema", "describe", slugs[name])
        capabilities = call("capabilities", slugs["capabilities"], {})
        assert capabilities["version"].startswith("Inkscape 1.4.4 "), capabilities["version"]
        assert capabilities["executable"] == "/usr/bin/inkscape"
        outputs = []
        frozen=json.loads((args.plans/"inputs.json").read_text())
        assert len(frozen)==7
        for item in frozen:
            label=Path(item["file"]).stem
            original=args.baseline/item["file"]
            assert hashlib.sha256(original.read_bytes()).hexdigest()==item["source_sha256"]
            plan_file=args.plans/(label+".json")
            assert hashlib.sha256(plan_file.read_bytes()).hexdigest()==item["plan_sha256"]
            payload=json.loads(plan_file.read_text())
            baseline=workspace/"baseline"/item["file"];baseline.parent.mkdir(exist_ok=True)
            shutil.copyfile(original,baseline)
            built=call(label+"-build",slugs["document_build"],payload)
            source=payload["output_file"]
            inspected=call(label+"-reopen",slugs["document_inspect"],{"source_file":source})
            # Native SVG export is a distinct saved output, not a host XML rewrite.
            exported="exports/"+item["file"]
            call(label+"-svg-export",slugs["document_export"],{"source_file":source,"output_file":exported,"format":"svg"})
            reopened=call(label+"-exported-reopen",slugs["document_inspect"],{"source_file":exported})
            for variant,input_file in [("old","baseline/"+item["file"]),("new",exported)]:
                call(label+"-"+variant+"-png",slugs["document_export"],{"source_file":input_file,"output_file":"previews/"+label+"-"+variant+".png","format":"png","width":256,"height":256})
            svg=workspace/exported
            tree=ElementTree.parse(svg)
            planned=payload["plan"]["nodes"]
            assert {n["id"] for n in planned}.issubset({e.get("id") for e in tree.iter()})
            image_paths=[workspace/"previews"/(label+"-"+v+".png") for v in ["old","new"]]
            images=[]
            for image_path in image_paths:
                with Image.open(image_path) as im:
                    im.load();assert im.size==(256,256);images.append(im.convert("RGBA"))
            difference=ImageChops.difference(images[0],images[1])
            outputs.append({"file":item["file"],"plan_sha256":item["plan_sha256"],"original_sha256":item["source_sha256"],"native_build":built,"reopen":inspected,"exported_reopen":reopened,"svg_sha256":hashlib.sha256(svg.read_bytes()).hexdigest(),"png_sha256":[hashlib.sha256(p.read_bytes()).hexdigest() for p in image_paths],"pixel_comparison":{"exact":difference.getbbox(alpha_only=False) is None,"channel_maxima":[ext[1] for ext in difference.getextrema()]},"visual_review_pending":True})
        (evidence / "regression-summary.json").write_text(
            json.dumps(
                {
                    "capabilities": capabilities,
                    "outputs": outputs,
                    "component_versions": {name:importlib.metadata.version(name) for name in ["dcc-mcp-inkscape","dcc-mcp-core","dcc-mcp-cli"]},
                    "adapter_source_commit":"d0edb439f6b2d5983cde4c3cc257d33cb2879a8c",
                    "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "calls": records,
                    "visual_acceptance": "not_run",
                    "publication_ready": False,
                    "boundary": "Real native regression artifact; visual review required before showcase submission.",
                },
                indent=2,
            )
        )
    finally:
        cleanup=[]
        for process in reversed(processes):
            # Each service and its native children live in an owned process group.
            record={"pid":process.pid,"owned_process_group":process.pid}
            try:
                os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=5)
            record["parent_returncode"]=process.returncode
            try:
                os.killpg(process.pid,0)
            except ProcessLookupError:
                record["group_remaining"]=False
            else:
                os.killpg(process.pid,signal.SIGKILL)
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    try:
                        os.killpg(process.pid,0)
                    except ProcessLookupError:
                        break
                    time.sleep(.1)
                try:
                    os.killpg(process.pid,0)
                    record["group_remaining"]=True
                    record["status"]="uncertain_remaining_group_may_include_unreaped_children"
                except ProcessLookupError:
                    record["group_remaining"]=False
            cleanup.append(record)
        (evidence/"cleanup.json").write_text(json.dumps(cleanup,indent=2))
        for log in logs:
            log.close()
        if any(record.get("group_remaining") for record in cleanup):
            raise RuntimeError("Owned native process group cleanup remains uncertain; evidence preserved")


if __name__ == "__main__":
    main()
