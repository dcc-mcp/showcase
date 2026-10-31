#!/usr/bin/env python3
"""Prepare licensed first-chapter sources; Godot runs only in explicit export mode.

No downloader, installer, browser, publication or shared-template-cache writer.
The original project is read-only. Each preparation/export has a new owner path.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zipfile

VERSION = "4.7.2.stable.official.ed1daf0bf"
APP_NAME = "Stairkeep · First Chapter Preview"
MAIN_SCENE = "res://fifty/view/preview.tscn"
ARCHIVE_SHA512 = "ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079"
TEMPLATES = {
    "web_nothreads_release.zip": "d3ee2f08cef0cf3cf6678a6355a92a8db48ccdd35cbd2e8bfd5f0e8a0b4032a0",
    "web_nothreads_debug.zip": "08962aefef811b603541d7951ac67ef00413aad2d978855183c28adee98f626a",
    "version.txt": "38885c88f75abbc797a1db7559719800279a00cfb9fa8b2e2868a7f6f84bad2e",
    "LICENSE.txt": "b0435e3b3e4e55238f05f4b306f30524a1b2e20147810d436eaa554fa6855c80",
    "COPYRIGHT.txt": "cb1980c88089573bcacd7221d777c689bb8bbd778799f24c27fca0fe5f774d6d",
}
RULE_PATHS = ["scripts/rules.gd", "fifty/scripts/runtime.gd", "fifty/scripts/content.gd", "fifty/scripts/d4.gd"]
EXCLUDED = {"tests", "tools", "evidence", ".godot", ".git", "__pycache__"}


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(path, root):
    return {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def selected_files(project):
    required = ["project.godot", "scripts/rules.gd", "scripts/world.gd", "scripts/ui_icon.gd", "fifty/data/content.json", "fifty/view/preview.tscn"]
    for name in required:
        need((project / name).is_file(), "Missing current project dependency: " + name)
    paths = {project / name for name in required}
    for prefix in ("assets/kenney", "assets/experience", "vendor/godot-isometric", "fifty/scripts", "fifty/view"):
        for p in (project / prefix).rglob("*"):
            if p.is_file() and not EXCLUDED.intersection(p.relative_to(project).parts):
                need(not p.is_symlink(), "Source symlinks are outside this bounded copy")
                paths.add(p)
    for name in ("fifty/data/manifest.json", "fifty/data/design-budget.json", "fifty/README.md", "fifty/PACKAGING.md", "fifty/SAVE.md", "fifty/REUSE-LICENSES.md", "fifty/reuse_manifest.json", "fifty/CONTENT-DESIGN.md", "fifty/VISUAL-DIRECTION.md"):
        if (project / name).is_file(): paths.add(project / name)
    for name in ("scripts/rules.gd.uid", "scripts/world.gd.uid", "scripts/ui_icon.gd.uid"):
        if (project / name).is_file(): paths.add(project / name)
    need(not any(p.suffix in (".cs", ".dll", ".gdextension", ".so", ".jsonl", ".log") for p in paths), "Unexpected nonproduction dependency")
    return sorted(paths)


def preset(templates=None):
    release = (templates / "web_nothreads_release.zip").as_posix() if templates else ""
    debug = (templates / "web_nothreads_debug.zip").as_posix() if templates else ""
    return '''[preset.0]
name="Web"
platform="Web"
runnable=true
export_filter="all_resources"
include_filter="*.json,*.txt,*.md,*.gd"
exclude_filter="tests/*,tests/**,tools/*,tools/**,evidence/*,evidence/**,fifty/tests/*,fifty/tests/**,fifty/tools/*,fifty/tools/**,fifty/evidence/*,fifty/evidence/**,*.jsonl,*.log,*.csv"
export_path=""
script_export_mode=0

[preset.0.options]
custom_template/release="%s"
custom_template/debug="%s"
variant/extensions_support=false
variant/thread_support=false
vram_texture_compression/for_desktop=true
vram_texture_compression/for_mobile=false
html/canvas_resize_policy=2
html/focus_canvas_on_start=true
html/experimental_virtual_keyboard=false
progressive_web_app/enabled=false
progressive_web_app/ensure_cross_origin_isolation_headers=false
''' % (release, debug)


def verify_templates(folder):
    proof = json.loads((folder / "template-provenance.json").read_text(encoding="utf-8-sig"))
    need(proof.get("whole_archive_verified") is True and proof.get("archive_sha512") == ARCHIVE_SHA512, "Missing historical whole-official-archive proof")
    for name, h in TEMPLATES.items():
        need(sha(folder / name) == h, "Existing selected template/notice bytes differ: " + name)
    need((folder / "version.txt").read_text().strip() == "4.7.2.stable", "Template version mismatch")
    return proof


def prepare(args):
    project, templates, out, license_path = [p.resolve() for p in (args.project, args.templates, args.output, args.repo_license)]
    need(not out.exists() and not out.is_relative_to(project), "Use a new owned output outside the original project")
    need(out.parent.is_dir(), "Output parent must already exist")
    proof = verify_templates(templates)
    paths = selected_files(project)
    before = [record(p, project) for p in paths]
    original_project = (project / "project.godot").read_text(encoding="utf-8-sig")
    need('renderer/rendering_method="gl_compatibility"' in original_project, "Existing Compatibility project required")
    out.mkdir(); stage = out / "project"; stage.mkdir(); (out / "private").mkdir(); (out / "private/pck-probe-cwd").mkdir()
    for p in paths:
        target = stage / p.relative_to(project); target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, target)
    changed = original_project
    for key, value in (("config/name", APP_NAME), ("run/main_scene", MAIN_SCENE), ("config/description", "Original first chapter, floors 1–10; floors 11–50 are not built.")):
        changed, count = re.subn(r"(?m)^" + re.escape(key) + r"=.*$", key + "=" + json.dumps(value, ensure_ascii=False), changed)
        need(count == 1, "Project override is not unambiguous: " + key)
    (stage / "project.godot").write_text(changed, encoding="utf-8")
    (stage / "export_presets.cfg").write_text(preset(templates), encoding="utf-8")
    notices = stage / "notices"; notices.mkdir()
    origins = [(license_path, "STAIRKEEP-MIT.txt", "https://github.com/dcc-mcp/showcase/blob/main/LICENSE", "MIT"),
        (templates / "LICENSE.txt", "GODOT-ENGINE-LICENSE.txt", "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/LICENSE.txt", "MIT"),
        (templates / "COPYRIGHT.txt", "GODOT-ENGINE-COPYRIGHT.txt", "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/COPYRIGHT.txt", "Godot bundled third-party notices"),
        (project / "assets/kenney/License.txt", "KENNEY-CC0.txt", "https://kenney.nl/assets/isometric-miniature-dungeon", "CC0-1.0"),
        (project / "vendor/godot-isometric/LICENSE.md", "GODOT-DEMO-MIT.txt", "https://github.com/godotengine/godot-demo-projects/tree/6ad6167e0577fe3622c18546138f456b107ce93c/2d/isometric", "MIT")]
    experience_licenses = [
        ("assets/experience/fonts/FONT-LICENSE.txt", "EXPERIENCE-FONT-OFL.txt", "https://github.com/notofonts/noto-cjk", "OFL-1.1"),
        ("assets/experience/audio/AUDIO-LICENSE.txt", "EXPERIENCE-MUSIC-CC0.txt", "https://opengameart.org/content/the-field-of-dreams", "CC0-1.0")]
    for relative, name, url, license_id in experience_licenses:
        if (project / relative).is_file():
            origins.append((project / relative, name, url, license_id))
    license_rows = []
    for source, name, url, license_id in origins:
        shutil.copyfile(source, notices / name)
        license_rows.append({"path": "notices/" + name, "sha256": sha(source), "bytes": source.stat().st_size, "source": url, "license": license_id})
    source_notice = {"schema_version": 1, "scope": "Same-project first-chapter source copy; no new download/install or complete-template claim.", "template": proof,
        "licenses": license_rows, "reused_project_sources": [r for r in before if r["path"].startswith(("assets/", "vendor/", "scripts/"))],
        "preserved_sources": ["assets/kenney/SOURCE.json", "assets/kenney/SOURCE.md", "vendor/godot-isometric/SOURCE.json", "fifty/reuse_manifest.json"],
        "script_export_mode": 0, "official_text_mode_source": "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/editor/export/editor_export_preset.h",
        "whole_archive_proof": "Inherited earlier verified receipt; selected extracted members freshly hashed here, not a new whole-archive measurement."}
    for relative in ("assets/experience/fonts/SOURCE.json", "assets/experience/audio/SOURCE.json", "assets/experience/characters/SOURCE.json", "assets/experience/doors/SOURCE.json"):
        if (stage / relative).is_file():
            source_notice["preserved_sources"].append(relative)
    dump(notices / "SOURCE.json", source_notice)
    critical = [record(p, stage) for p in sorted(stage.rglob("*")) if p.is_file() and (p.suffix == ".gd" or p.relative_to(stage).as_posix() == "fifty/data/content.json")]
    readable = critical + [record(p, stage) for p in sorted(stage.rglob("*")) if p.is_file() and p.suffix in (".txt", ".md", ".json") and p.relative_to(stage).as_posix() not in {r["path"] for r in critical}]
    portable_files = {"project/" + p.relative_to(stage).as_posix(): p.read_bytes() for p in sorted(stage.rglob("*")) if p.is_file()}
    portable_files["project/export_presets.cfg"] = preset().encode("utf-8")
    portable_files["LICENSE"] = license_path.read_bytes()
    portable_files["recipe/prepare_firstchapter_export.py"] = Path(__file__).read_bytes()
    portable_files["recipe/probe_firstchapter_pck.gd"] = Path(__file__).with_name("probe_firstchapter_pck.gd").read_bytes()
    portable_files["recipe/agent_launch_firstchapter_probe.py"] = Path(__file__).with_name("agent_launch_firstchapter_probe.py").read_bytes()
    portable_files["README.md"] = ("# Stairkeep first chapter source\n\nThis is a staged copy of the existing project with a separate preview name and main scene. Floors 1–10 are implemented toward a 50-floor target. Run `project/project.godot` with Godot " + VERSION + ". Tests/tools/evidence and historical projects are not bundled. Full QA sources remain in the reviewed repository.\n\nExport uses verified official local no-thread templates, GDScript Text mode 0, Compatibility, no extensions/PWA/service worker. Provide an existing verified template directory to the recipe prepare command; it rewrites only a new copy. The portable preset has no private absolute template paths. Browser play, native pixels/input, CJK glyphs, audio and durable Web saves are not accepted here.\n").encode("utf-8")
    portable_files["README.md"] += ("\nWindows probe reproduction uses the bundled launcher rather than a handwritten launch receipt. Run `python recipe/agent_launch_firstchapter_probe.py --godot <existing-4.7.2-executable> --project <input-project> --prepared <new-preparation> --phase native`, run the export recipe, then invoke the same launcher with `--phase pck`. The launcher records actual original argv, an empty owned cwd, isolated user data, actual BelowNormal priority/process times and immutable PCK launch metadata. It never starts a browser, installs software, overwrites prior evidence or kills a process on a timer. The original-engine PCK probe is not a browser/WASM execution acceptance.\n").encode("utf-8")
    archive = out / "firstchapter-source.zip"
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(portable_files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED; info.create_system = 3; info.external_attr = 0o100644 << 16; z.writestr(info, data)
    with zipfile.ZipFile(archive) as z:
        for name, data in portable_files.items(): need(z.read(name) == data, "Source ZIP readback differs")
    need(before == [record(p, project) for p in paths], "Original sources changed while copying")
    protected = [project / "project.godot", project / "export_presets.cfg", *[p.resolve() for p in args.protected_file]]
    # The portable first-chapter source has only its actual preview main scene.
    # Preserve the historical root main too when preparing from the full game.
    if (project / "main.tscn").is_file():
        protected.append(project / "main.tscn")
    dump(out / "private/inputs.json", {"original_project": str(project), "templates": str(templates), "protected": [{"path": str(p), "sha256": sha(p)} for p in protected]})
    manifest = {"schema_version": 1, "stage": "prepared-not-exported", "engine_expected": VERSION, "app_name": APP_NAME, "main_scene": MAIN_SCENE, "renderer": "gl_compatibility", "language": "GDScript", "script_export_mode": 0, "threads": False, "extensions": False, "pwa": False, "service_worker": False,
        "sources_before": before, "original_sources_unchanged": True, "staged_project_sha256": sha(stage / "project.godot"), "staged_project_overrides": ["config/name", "config/description", "run/main_scene", "export_presets.cfg"],
        "critical_native_files": critical, "required_pck_files": readable, "rule_files": RULE_PATHS,
        "licenses": license_rows, "template_sha256": TEMPLATES, "excluded_prefixes": ["tests", "tools", "evidence", "fifty/tests", "fifty/tools", "fifty/evidence"],
        "source_archive": {"path": archive.name, "bytes": archive.stat().st_size, "sha256": sha(archive)},
        "source_archive_files": [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(portable_files.items())],
        "native_pck_probe": "not-run", "browser_http_acceptance": "not-tested", "native_visual_input": "not-tested"}
    dump(out / "preparation-manifest.json", manifest)
    print(json.dumps({"prepared": True, "output": str(out), "source_archive_sha256": sha(archive), "native_executed": False}))


def windows_resources(process):
    if os.name != "nt":
        return {"actual_priority_class": None, "measurement_error": "This owner recipe requires Windows actual-priority measurement"}
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetPriorityClass.argtypes = [wintypes.HANDLE]; kernel.GetPriorityClass.restype = wintypes.DWORD
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    handle = wintypes.HANDLE(int(process._handle))
    priority = int(kernel.GetPriorityClass(handle))
    creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
    ok = kernel.GetProcessTimes(handle, creation, exit_time, kernel_time, user_time)
    number = lambda v: (v.dwHighDateTime << 32) | v.dwLowDateTime
    return {"actual_priority_class": priority, "actual_below_normal": priority == 0x4000,
            "process_times_available": bool(ok), "creation_filetime": number(creation) if ok else None,
            "cpu_seconds": (number(kernel_time) + number(user_time)) / 10000000 if ok else None}


def wasm_memory_proof(data):
    """Parse every v1 import/defined memory limit; do not execute the module."""
    need(data[:8] == b"\x00asm\x01\x00\x00\x00", "Expected a complete WASM v1 module")
    def byte(pos, end):
        need(pos < end, "Truncated WASM field")
        return data[pos], pos + 1
    def uleb(pos, end, bits=32):
        value, shift = 0, 0
        for _ in range((bits + 6) // 7):
            part, pos = byte(pos, end); value |= (part & 127) << shift
            if not part & 128:
                need(value < (1 << bits), "Out-of-range WASM unsigned field")
                return value, pos
            shift += 7
        raise ValueError("Overlong/truncated WASM unsigned field")
    def name(pos, end):
        size, pos = uleb(pos, end); need(pos + size <= end, "Truncated WASM name")
        return data[pos:pos + size].decode("utf-8"), pos + size
    def value_type(pos, end):
        kind, pos = byte(pos, end)
        if kind in (0x63, 0x64):
            for _ in range(5):
                item, pos = byte(pos, end)
                if not item & 128: return pos
            raise ValueError("Overlong WASM reference heap type")
        need(kind in (0x7f, 0x7e, 0x7d, 0x7c, 0x7b, 0x70, 0x6f, 0x6e, 0x6d, 0x6c, 0x6b, 0x6a, 0x69), "Unknown WASM value/reference type")
        return pos
    def limits(pos, end):
        flags, pos = uleb(pos, end)
        need(flags & ~7 == 0, "Unknown WASM memory/limit flags")
        minimum, pos = uleb(pos, end, 64 if flags & 4 else 32)
        maximum = None
        if flags & 1: maximum, pos = uleb(pos, end, 64 if flags & 4 else 32)
        need(maximum is None or minimum <= maximum, "Invalid WASM memory limits")
        need(not flags & 2 or flags & 1, "Shared WASM memory lacks maximum")
        return {"flags": flags, "shared": bool(flags & 2), "memory64": bool(flags & 4), "min_pages": minimum, "max_pages": maximum}, pos
    pos, imports, memories, sections, seen = 8, 0, [], [], set()
    while pos < len(data):
        section, pos = byte(pos, len(data)); size, pos = uleb(pos, len(data)); end = pos + size
        need(section <= 13 and end <= len(data), "Unknown/truncated WASM section")
        need(section == 0 or section not in seen, "Duplicate WASM standard section")
        seen.add(section); sections.append({"id": section, "bytes": size})
        if section == 2:
            imports, cursor = uleb(pos, end)
            for _ in range(imports):
                module, cursor = name(cursor, end); field, cursor = name(cursor, end); kind, cursor = byte(cursor, end)
                if kind == 0: _, cursor = uleb(cursor, end)
                elif kind == 1: cursor = value_type(cursor, end); _, cursor = limits(cursor, end)
                elif kind == 2:
                    memory, cursor = limits(cursor, end); memories.append({"origin": "import", "module": module, "name": field, **memory})
                elif kind == 3:
                    cursor = value_type(cursor, end); mutable, cursor = byte(cursor, end); need(mutable in (0, 1), "Invalid WASM global mutability")
                elif kind == 4:
                    attribute, cursor = uleb(cursor, end); need(attribute == 0, "Unknown WASM tag attribute"); _, cursor = uleb(cursor, end)
                else: raise ValueError("Unknown WASM import kind")
            need(cursor == end, "Unconsumed WASM import bytes")
        elif section == 5:
            count, cursor = uleb(pos, end)
            for index in range(count):
                memory, cursor = limits(cursor, end); memories.append({"origin": "defined", "index": index, **memory})
            need(cursor == end, "Unconsumed WASM memory bytes")
        pos = end
    need(pos == len(data) and memories, "Incomplete WASM framing or missing memory")
    need(not any(memory["shared"] for memory in memories), "Shared WASM memory is forbidden for this no-thread candidate")
    return {"wasm_v1_parsed": True, "bytes": len(data), "section_count": len(sections), "import_count": imports,
            "all_import_and_defined_memories": memories, "shared_memory_count": 0, "wasm_executed": False}


def verify_web_singlethread(web, templates):
    """Pool hints are retained as data, never mistaken for a thread toggle."""
    template = templates / "web_nothreads_release.zip"
    need(sha(template) == TEMPLATES[template.name], "Unverified no-thread template")
    page = (web / "index.html").read_text(encoding="utf-8")
    matches = re.findall(r"const GODOT_CONFIG = (\{.*?\});", page, re.S)
    need(len(matches) == 1, "Expected one official GODOT_CONFIG")
    config = json.loads(matches[0])
    toggles = re.findall(r"(?m)^\s*const GODOT_THREADS_ENABLED\s*=\s*(true|false)\s*;", page)
    need(toggles == ["false"], "Literal GODOT_THREADS_ENABLED=false is required")
    need(config.get("ensureCrossOriginIsolationHeaders") is False, "Unexpected isolation requirement")
    need(config.get("gdextensionLibs") == [], "Unexpected extension libraries")
    need(config.get("serviceWorker") in (None, ""), "Unexpected configured service worker")
    service_files = [p.name for p in web.iterdir() if "service.worker" in p.name or "service-worker" in p.name or "offline" in p.name or p.name.endswith(".manifest.json")]
    need(not service_files, "Unexpected PWA/service worker files")
    runtime = []
    with zipfile.ZipFile(template) as zipped:
        for member in ("godot.js", "godot.wasm", "godot.audio.worklet.js", "godot.audio.position.worklet.js"):
            path = web / ("index" + member[5:]); need(path.is_file(), "Missing official runtime member")
            expected = hashlib.sha256(zipped.read(member)).hexdigest()
            need(sha(path) == expected, "Runtime differs from verified no-thread template: " + member)
            runtime.append({**record(path, web), "template_member": member, "template_sha256": expected, "byte_hash_equal": True})
    memory = wasm_memory_proof((web / "index.wasm").read_bytes())
    return {"method": "Literal HTML toggle plus exact verified no-thread runtime bytes and complete WASM memory-limit parsing",
            "official_export_source": "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/platform/web/export/export_plugin.cpp",
            "html_threads_enabled": False, "pool_hints": {key: config.get(key) for key in ("threadPoolSize", "emscriptenPoolSize", "godotPoolSize")},
            "pool_hints_are_thread_enable_evidence": False, "raw_godot_config": config, "template_zip_sha256": sha(template),
            "runtime": runtime, "wasm": memory, "extension_libraries": [], "cross_origin_isolation_headers": False,
            "service_worker_files": service_files, "browser_executed": False}


def export(args):
    out, editor = args.prepared.resolve(), args.godot.resolve()
    m = json.loads((out / "preparation-manifest.json").read_text(encoding="utf-8")); inputs = json.loads((out / "private/inputs.json").read_text())
    stage = out / "project"; templates = Path(inputs["templates"]); original = Path(inputs["original_project"])
    recipe_rows = {row["path"]: row for row in m["source_archive_files"]}
    need(sha(Path(__file__)) == recipe_rows["recipe/prepare_firstchapter_export.py"]["sha256"], "Prepared export recipe changed")
    need(sha(Path(__file__).with_name("probe_firstchapter_pck.gd")) == recipe_rows["recipe/probe_firstchapter_pck.gd"]["sha256"], "Prepared probe recipe changed")
    verify_templates(templates)
    for row in m["critical_native_files"]: need(sha(stage / row["path"]) == row["sha256"], "Staged critical source changed")
    need((stage / "export_presets.cfg").read_text() == preset(templates), "Staged preset changed")
    web = out / "web"; need(not web.exists(), "Use a fresh preparation; web output exists"); web.mkdir()
    env = os.environ.copy()
    for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        path = out / "private/user" / key; path.mkdir(parents=True, exist_ok=True); env[key] = str(path)
    for base in (Path(env["APPDATA"]) / "Godot/export_templates/4.7.2.stable", Path(env["XDG_DATA_HOME"]) / "godot/export_templates/4.7.2.stable"):
        base.mkdir(parents=True, exist_ok=True)
        for name in ("web_nothreads_release.zip", "web_nothreads_debug.zip"): shutil.copyfile(templates / name, base / name)
    flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0
    def check_sources():
        for row in m["sources_before"]: need(sha(original / row["path"]) == row["sha256"], "Original source changed: " + row["path"])
        for row in inputs["protected"]: need(sha(Path(row["path"])) == row["sha256"], "Protected file changed")
        for row in m["critical_native_files"]: need(sha(stage / row["path"]) == row["sha256"], "Staged critical bytes changed")
        need(sha(stage / "project.godot") == m["staged_project_sha256"], "Staged project settings changed")
        need((stage / "export_presets.cfg").read_text() == preset(templates), "Staged preset changed")
        verify_templates(templates)
        return True
    def run(label, arguments):
        check_sources()
        stdout_path, stderr_path, owner_path = [out / ("private/" + label + suffix) for suffix in (".stdout.log", ".stderr.log", ".owner.json")]
        need(not any(p.exists() for p in (stdout_path, stderr_path, owner_path)), "Previous phase evidence exists")
        start = time.monotonic()
        owner = {"phase": label, "started_utc": datetime.now(timezone.utc).isoformat(), "complete": False,
                 "creation_flags": flags, "requested_priority": "BelowNormal", "hidden": True,
                 "automatic_timeout_or_kill": False, "sources_and_protected_before_passed": True,
                 "recipe_sha256": sha(Path(__file__)), "editor_sha256": sha(editor)}
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen([str(editor), *arguments], env=env, cwd=out, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, creationflags=flags)
            owner["engine_pid"] = process.pid
            owner["initial_resources"] = windows_resources(process)
            dump(owner_path, owner)
            while process.poll() is None:
                owner["resources"] = windows_resources(process)
                owner["elapsed_seconds"] = round(time.monotonic() - start, 3)
                dump(owner_path, owner)
                time.sleep(5)
            code = process.wait()
            owner["final_resources"] = windows_resources(process)
        owner.update({"complete": True, "ended_utc": datetime.now(timezone.utc).isoformat(), "elapsed_seconds": round(time.monotonic() - start, 3),
                      "exit_code": code, "stdout_bytes": stdout_path.stat().st_size, "stderr_bytes": stderr_path.stat().st_size,
                      "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
                      "actual_below_normal_verified": owner["initial_resources"].get("actual_below_normal") is True,
                      "actual_process_times_verified": owner["initial_resources"].get("process_times_available") is True,
                      "recipe_unchanged": owner["recipe_sha256"] == sha(Path(__file__)), "editor_unchanged": owner["editor_sha256"] == sha(editor)})
        try:
            owner["sources_and_protected_after_passed"] = check_sources()
        except Exception as error:
            owner["sources_and_protected_after_passed"] = False; owner["postcheck_error"] = str(error)
        dump(owner_path, owner)
        text = stdout_path.read_text(encoding="utf-8", errors="replace")
        need(code == 0 and owner["stderr_bytes"] == 0 and owner["actual_below_normal_verified"] and owner["actual_process_times_verified"] and owner["sources_and_protected_after_passed"] and owner["recipe_unchanged"] and owner["editor_unchanged"] and not any(e in text for e in ("SCRIPT ERROR", "Parse Error", "ERROR:")), "Godot phase failed strict owner/checks: " + label)
        return text
    version = run("version", ["--version"]).strip(); need(version == VERSION, "Existing engine version differs")
    run("import", ["--headless", "--path", str(stage), "--editor", "--import", "--quit"])
    run("export", ["--headless", "--path", str(stage), "--export-release", "Web", str(web / "index.html")])
    thread_validation = verify_web_singlethread(web, templates)
    runtime = thread_validation["runtime"]
    need(any(r["path"] == "index.wasm" for r in runtime) and (web / "index.pck").read_bytes()[:4] == b"GDPC", "Missing real WASM/PCK")
    shutil.copytree(stage / "notices", web / "notices")
    check_sources()
    for row in m["critical_native_files"]: need(sha(stage / row["path"]) == row["sha256"], "Staged source changed during import/export")
    phases = []
    for label in ("version", "import", "export"):
        owner_file = out / ("private/" + label + ".owner.json"); owner = json.loads(owner_file.read_text(encoding="utf-8"))
        phases.append({"phase": label, "owner_sha256": sha(owner_file), "exit_code": owner["exit_code"], "stderr_bytes": owner["stderr_bytes"], "elapsed_seconds": owner["elapsed_seconds"], "actual_priority_class": owner["initial_resources"]["actual_priority_class"], "cpu_seconds": owner["final_resources"].get("cpu_seconds"), "sources_and_protected_after_passed": owner["sources_and_protected_after_passed"]})
    result = {"schema_version": 1, "exported": True, "engine": version, "editor_name": editor.name, "editor_sha256": sha(editor), "phases": phases, "renderer": "gl_compatibility", "language": "GDScript", "script_export_mode": 0, "threads": False, "extensions": False, "pwa": False, "service_worker": False, "thread_validation": thread_validation, "runtime": runtime, "files": [record(p, web) for p in sorted(web.rglob("*")) if p.is_file()], "original_sources_unchanged": True, "shared_template_cache_written": False, "native_pck_probe": "not-run", "browser_http_acceptance": "not-tested"}
    dump(out / "export-provenance.json", result)
    print(json.dumps({"exported": True, "output": str(web), "pck_sha256": sha(web / "index.pck"), "browser_http_acceptance": "not-tested"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--project", type=Path, required=True); p.add_argument("--templates", type=Path, required=True); p.add_argument("--repo-license", type=Path, required=True); p.add_argument("--output", type=Path, required=True); p.add_argument("--protected-file", type=Path, action="append", default=[])
    p = sub.add_parser("export"); p.add_argument("--prepared", type=Path, required=True); p.add_argument("--godot", type=Path, required=True)
    args = parser.parse_args(); prepare(args) if args.command == "prepare" else export(args)


if __name__ == "__main__":
    main()
