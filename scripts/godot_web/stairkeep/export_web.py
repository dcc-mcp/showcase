#!/usr/bin/env python3
"""Export Stairkeep with verified official 4.7.2 non-threaded Web templates.

Requires an existing authorized Godot executable; never installs/launches a GUI
or browser. Source and user data are isolated. The output is a local review
candidate, not a site publication, browser acceptance, or production deploy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = "4.7.2.stable.official.ed1daf0bf"
ARCHIVE_SHA512 = "ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079"
EXPECTED_MEMBERS = {
    "web_nothreads_release.zip": "d3ee2f08cef0cf3cf6678a6355a92a8db48ccdd35cbd2e8bfd5f0e8a0b4032a0",
    "web_nothreads_debug.zip": "08962aefef811b603541d7951ac67ef00413aad2d978855183c28adee98f626a",
    "version.txt": "38885c88f75abbc797a1db7559719800279a00cfb9fa8b2e2868a7f6f84bad2e",
    "LICENSE.txt": "b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80",
    "COPYRIGHT.txt": "cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d",
}


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_inventory(project: Path) -> list[dict]:
    return [{"path": str(p.relative_to(project)).replace("\\", "/"), "bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(project.rglob("*"))
            if p.is_file() and ".godot" not in p.parts and "__pycache__" not in p.parts]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--godot", required=True, help="Existing authorized official Godot 4.7.2 executable")
    ap.add_argument("--templates", type=Path, required=True, help="Verified fetch_web_templates.py output folder")
    ap.add_argument("--output", type=Path, required=True, help="New/empty review directory outside the project")
    args = ap.parse_args()
    editor = Path(shutil.which(args.godot) or args.godot).resolve()
    templates = args.templates.resolve()
    output = args.output.resolve()
    project = HERE / "game"
    if output == project or output.is_relative_to(project):
        raise SystemExit("Output must be outside source project")
    if output.exists() and any(output.iterdir()):
        raise SystemExit("Output must be empty; preserve previous review builds")
    proof = json.loads((templates / "template-provenance.json").read_text(encoding="utf-8"))
    if not proof.get("whole_archive_verified") or proof.get("archive_sha512") != ARCHIVE_SHA512:
        raise SystemExit("Whole official archive verification receipt is required")
    # A receipt is not a byte check. Re-hash the full archive and selected members.
    archive = templates / "Godot_v4.7.2-stable_export_templates.tpz"
    if digest(archive, "sha512") != ARCHIVE_SHA512:
        raise SystemExit("Official export archive SHA-512 mismatch")
    for name, expected_sha in EXPECTED_MEMBERS.items():
        if digest(templates / name) != expected_sha:
            raise SystemExit("Extracted template SHA-256 mismatch: " + name)
    if (templates / "version.txt").read_text().strip() != "4.7.2.stable":
        raise SystemExit("Template version mismatch")
    original = source_inventory(project)
    with tempfile.TemporaryDirectory(prefix="stairkeep-export-") as temp:
        tmp = Path(temp)
        env = os.environ.copy()
        for key, leaf in (("APPDATA", "roaming"), ("LOCALAPPDATA", "local"), ("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_CACHE_HOME", "cache")):
            env[key] = str(tmp / leaf)
            (tmp / leaf).mkdir()
        version_run = subprocess.run([str(editor), "--version"], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        version = version_run.stdout.strip()
        if version_run.returncode or version != VERSION:
            raise SystemExit("Expected exact existing Godot " + VERSION + "; got " + version)
        # Both locations keep Windows and XDG platforms independent of user installs.
        for base in (tmp / "roaming/Godot/export_templates/4.7.2.stable", tmp / "data/godot/export_templates/4.7.2.stable"):
            base.mkdir(parents=True, exist_ok=True)
            for name in ("web_nothreads_release.zip", "web_nothreads_debug.zip"):
                shutil.copyfile(templates / name, base / name)
        copied = tmp / "game"
        shutil.copytree(project, copied, ignore=shutil.ignore_patterns(".godot", "__pycache__"))
        preset = copied / "export_presets.cfg"
        release = (templates / "web_nothreads_release.zip").as_posix()
        debug = (templates / "web_nothreads_debug.zip").as_posix()
        preset.write_text(preset.read_text(encoding="utf-8") + f'\ncustom_template/release="{release}"\ncustom_template/debug="{debug}"\n', encoding="utf-8")
        output.mkdir(parents=True, exist_ok=True)
        logs = []
        for flags in (("--editor", "--import", "--quit"), ("--export-release", "Web", str(output / "index.html"))):
            run = subprocess.run([str(editor), "--headless", "--path", str(copied), *flags], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            log = run.stdout + run.stderr
            logs.append(log.replace(str(tmp), "<isolated-export>").replace(str(HERE), "<stairkeep-source>"))
            if run.returncode or any(marker in log for marker in ("SCRIPT ERROR", "Parse Error", "ERROR:")):
                raise SystemExit(logs[-1])
        page = (output / "index.html").read_text(encoding="utf-8")
        match = re.search(r"const GODOT_CONFIG = (\{.*?\});", page)
        if not match:
            raise SystemExit("Official export HTML lacks GODOT_CONFIG")
        config = json.loads(match.group(1))
        if config.get("threadPoolSize") not in (None, 0) or config.get("ensureCrossOriginIsolationHeaders") is True:
            raise SystemExit("Export unexpectedly requires threaded/isolation support")
        if any(output.glob("*service.worker*")) or any(output.glob("*service-worker*")):
            raise SystemExit("Service worker is outside this candidate's scope")
        (output / "export.log").write_text("\n".join(logs), encoding="utf-8")
        notices = output / "notices"
        notices.mkdir()
        for name in ("LICENSE.txt", "COPYRIGHT.txt"):
            shutil.copyfile(templates / name, notices / ("GODOT-" + name))
        shutil.copyfile(project / "assets/kenney/License.txt", notices / "KENNEY-CC0.txt")
        shutil.copyfile(project / "vendor/godot-isometric/LICENSE.md", notices / "GODOT-DEMO-MIT.txt")
        shutil.copyfile(HERE.parents[2] / "LICENSE", notices / "STAIRKEEP-MIT.txt")
        # Match the actual exported runtime bytes to the selected official template.
        runtime = []
        with zipfile.ZipFile(templates / "web_nothreads_release.zip") as z:
            # HTML is expanded by the exporter; service workers/offline pages
            # are deliberately excluded. Only these engine bytes are copied.
            for name in ("godot.js", "godot.wasm", "godot.audio.worklet.js", "godot.audio.position.worklet.js"):
                if name in z.namelist():
                    suffix = name[len("godot"):]
                    delivered = output / ("index" + suffix)
                    if delivered.is_file():
                        expected_hash = hashlib.sha256(z.read(name)).hexdigest()
                        if digest(delivered) != expected_hash:
                            raise SystemExit("Export runtime differs from official template: " + name)
                        runtime.append({"path": delivered.name, "bytes": delivered.stat().st_size, "sha256": expected_hash, "template_member": name})
        if not any(row["path"].endswith(".wasm") for row in runtime):
            raise SystemExit("Verified official WebAssembly runtime is missing")
        executable = editor.with_name(editor.name.replace("_console.exe", ".exe")) if editor.name.endswith("_console.exe") else editor
        record = {"candidate": "stairkeep", "engine": version, "editor_file": editor.name, "editor_sha256": digest(editor), "engine_binary": {"file": executable.name, "bytes": executable.stat().st_size, "sha256": digest(executable)}, "renderer": "gl_compatibility", "language": "GDScript", "threads": False, "extensions": False, "pwa": False, "service_worker": False, "browser_http_acceptance": "not-tested", "official_release": proof["official_release"], "archive_sha512": ARCHIVE_SHA512, "template_files": proof["files"], "runtime_license_sources": proof.get("licenses", []), "sources": original, "runtime": runtime, "files": [{"path": p.relative_to(output).as_posix(), "bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(output.rglob("*")) if p.is_file()]}
        (output / "export-provenance.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if source_inventory(project) != original:
        raise SystemExit("Source changed during export; candidate is not accepted")
    print(json.dumps({"output": str(output), "engine": VERSION, "threads": False, "browser_http_acceptance": "not-tested"}), flush=True)


if __name__ == "__main__":
    main()
