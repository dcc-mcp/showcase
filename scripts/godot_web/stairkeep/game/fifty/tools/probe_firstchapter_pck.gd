extends SceneTree
## Root-owned headless probe. No UI, browser, storage or action-route acceptance.
## Native capture: --path original/game --script this -- --phase=native ...
## PCK probe: empty owned cwd, --main-pack web/index.pck --script this (no --path).
## Godot consumes engine flags before OS.get_cmdline_args(). The PCK launcher
## supplies --pack and an immutable --launch-receipt with the original argv.

var _checks: Array = []
var _errors: Array = []


func _initialize() -> void:
	var options: Dictionary = _options(OS.get_cmdline_user_args())
	if not options.get("ok", false):
		print(JSON.stringify({"passed": false, "error": "Use --phase=native|pck --manifest=<preparation-manifest.json> --report=<new absolute JSON>; PCK additionally needs --native-reference, --pack and --launch-receipt."}))
		quit(2)
		return
	var report_path: String = str(options["report"]).replace("\\", "/").simplify_path()
	if not report_path.is_absolute_path() or not report_path.ends_with(".json") or FileAccess.file_exists(report_path) or DirAccess.dir_exists_absolute(report_path) or not DirAccess.dir_exists_absolute(report_path.get_base_dir()):
		print(JSON.stringify({"passed": false, "error": "Report must be a new absolute JSON path with an existing parent; no overwrite."}))
		quit(2)
		return
	var phase: String = options["phase"]
	var report: Dictionary = {"schema_version": 1, "suite": "firstchapter_native_pck_source_identity/v1", "phase": phase, "engine": Engine.get_version_info(), "engine_binary_sha256": FileAccess.get_sha256(OS.get_executable_path()), "renderer": str(ProjectSettings.get_setting("rendering/renderer/rendering_method", "")), "main_scene": ProjectSettings.get_setting("application/run/main_scene", ""), "app_name": ProjectSettings.get_setting("application/config/name", ""), "browser_http_acceptance": "not-tested", "native_visual_input": "not-tested", "web_persistence": "not-tested", "checks": _checks, "errors": _errors}
	_probe(options, report)
	report["passed"] = _errors.is_empty()
	report["check_count"] = _checks.size()
	var bytes: PackedByteArray = (JSON.stringify(report, "\t", true, true) + "\n").to_utf8_buffer()
	if FileAccess.file_exists(report_path):
		print(JSON.stringify({"passed": false, "error": "Report appeared before write; preserved."}))
		quit(2)
		return
	var file: FileAccess = FileAccess.open(report_path, FileAccess.WRITE)
	if file == null:
		print(JSON.stringify({"passed": false, "error": "Cannot create new probe report."}))
		quit(2)
		return
	file.store_buffer(bytes); file.flush()
	var error: Error = file.get_error(); file.close()
	if error != OK or FileAccess.get_file_as_bytes(report_path) != bytes:
		print(JSON.stringify({"passed": false, "error": "New report readback failed."}))
		quit(2)
		return
	print(JSON.stringify({"passed": report["passed"], "phase": phase, "check_count": _checks.size(), "errors": _errors, "report_sha256": FileAccess.get_sha256(report_path), "browser_http_acceptance": "not-tested"}))
	quit(0 if report["passed"] else 2)


func _probe(options: Dictionary, report: Dictionary) -> void:
	if not _check(DisplayServer.get_name() == "headless" and not OS.has_feature("web"), "original_engine_headless_probe_only"):
		return
	var version: Dictionary = Engine.get_version_info()
	if not _check(version.get("major") == 4 and version.get("minor") == 7 and version.get("patch") == 2 and version.get("status") == "stable" and str(version.get("hash", "")).begins_with("ed1daf0bf"), "expected_original_472_engine_version"):
		return
	var manifest: Dictionary = _read_json(options["manifest"])
	if not _check(manifest.get("schema_version") == 1 and manifest.get("script_export_mode") == 0 and manifest.get("threads") == false, "expected_text_single_thread_manifest"):
		return
	var phase: String = options["phase"]
	if phase == "pck":
		if not _launch_guard(options, manifest, report):
			return
		if not _check(ProjectSettings.get_setting("application/run/main_scene", "") == manifest["main_scene"] and ProjectSettings.get_setting("application/config/name", "") == manifest["app_name"], "packed_preview_scene_and_independent_name"):
			return
		if not _check(not FileAccess.file_exists("res://main.tscn"), "old_default_scene_absent_no_source_fallback"):
			return
		for prefix: String in manifest["excluded_prefixes"]:
			if not _check(not DirAccess.dir_exists_absolute("res://" + prefix), "excluded_pck_directory_" + prefix):
				return
	var files: Array = manifest["critical_native_files"] if phase == "native" else manifest["required_pck_files"]
	for row: Dictionary in files:
		var path: String = "res://" + str(row["path"])
		if not _check(FileAccess.file_exists(path) and FileAccess.get_sha256(path) == row["sha256"], "exact_readable_bytes_" + str(row["path"])):
			return
	if not _check(ProjectSettings.get_setting("rendering/renderer/rendering_method", "") == "gl_compatibility", "compatibility_renderer"):
		return
	var runtime_script: Variant = load("res://fifty/scripts/runtime.gd")
	var geometry: Variant = load("res://fifty/scripts/d4.gd")
	if not _check(runtime_script != null and geometry != null, "packed_runtime_scripts_load"):
		return
	var cases: Dictionary = {}
	for mode: String in ["classic_restart", "practice_checkpoint"]:
		var runtime = runtime_script.new()
		var loaded: Dictionary = runtime.load_content("res://fifty/data/content.json")
		if not _check(loaded.get("ok", false) == true and runtime.export_snapshot().get("mode") == "unselected", mode + "_content_starts_unselected"):
			return
		var chosen: Dictionary = runtime.choose_mode(mode, 1)
		if not _check(chosen.get("ok", false) == true, mode + "_explicit_seed1_choose"):
			return
		var snapshot: Dictionary = runtime.export_snapshot()
		var validated: Dictionary = runtime.validate_snapshot(snapshot)
		if not _check(validated.get("ok", false) == true, mode + "_complete_snapshot_authoritatively_validates"):
			return
		cases[mode] = {"runtime_identity": runtime.runtime_identity(), "snapshot": snapshot, "snapshot_sha256": geometry.content_hash(snapshot)}
	report["cases"] = cases
	if phase == "pck":
		var reference: Dictionary = _read_json(options["native-reference"])
		if not _check(reference.get("passed") == true and reference.get("phase") == "native", "actual_passed_native_reference"):
			return
		report["engine_metadata_number_types"] = {"reference_major_typeof": typeof(reference.get("engine", {}).get("major")), "actual_major_typeof": typeof(report["engine"].get("major")), "comparison": "Geometry.canonical_json normalizes JSON integral numbers; binary SHA remains exact"}
		if not _check(geometry.canonical_json(reference.get("engine")) == geometry.canonical_json(report["engine"]) and reference.get("engine_binary_sha256") == report["engine_binary_sha256"], "same_original_engine_as_native_reference"):
			return
		for mode: String in cases:
			if not _check(geometry.canonical_json(cases[mode]) == geometry.canonical_json(reference["cases"].get(mode)), mode + "_identity_and_complete_snapshot_equal_native"):
				return
		_check(FileAccess.get_sha256(options["launch-receipt"]) == report["launch_proof"]["receipt_sha256"], "immutable_launch_receipt_unchanged_after_full_probe")


func _read_json(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null: return {}
	var json: JSON = JSON.new(); var text: String = file.get_as_text(); file.close()
	if json.parse(text) != OK or not (json.data is Dictionary): return {}
	return json.data


func _launch_guard(options: Dictionary, manifest: Dictionary, report: Dictionary) -> bool:
	var pack_path: String = str(options["pack"])
	var receipt_path: String = str(options["launch-receipt"])
	if not _check(pack_path.is_absolute_path() and receipt_path.is_absolute_path(), "explicit_absolute_pack_and_launch_receipt"):
		return false
	var receipt_sha: String = FileAccess.get_sha256(receipt_path)
	var receipt: Dictionary = _read_json(receipt_path)
	if not _check(_digest(receipt_sha) and receipt.get("schema_version") == 1 and receipt.get("phase") == "pck" and receipt.get("argv") is Array, "immutable_root_launch_receipt_schema"):
		return false
	var argv: Array = receipt["argv"]
	for value: Variant in argv:
		if not _check(value is String, "original_argv_is_string_array"):
			return false
	var separator: int = argv.find("--")
	var engine_args: Array = argv.slice(0, separator if separator >= 0 else argv.size())
	var pack_index: int = engine_args.find("--main-pack")
	var has_path: bool = false
	for argument: String in engine_args:
		if argument == "--path" or argument.begins_with("--path="): has_path = true
	if not _check(engine_args.count("--main-pack") == 1 and pack_index >= 0 and pack_index + 1 < engine_args.size() and not has_path and _same_absolute_path(str(engine_args[pack_index + 1]), pack_path), "original_launch_main_pack_argument_without_source_path"):
		return false
	if not _check(receipt.get("source_project_path_supplied") == false and receipt.get("cwd_empty_before") == true and receipt.get("cwd") is String and str(receipt["cwd"]).is_absolute_path() and DirAccess.dir_exists_absolute(receipt["cwd"]), "owned_empty_cwd_original_launch_binding"):
		return false
	var cwd: String = str(receipt["cwd"]).replace("\\", "/").simplify_path()
	if not _check(not FileAccess.file_exists(cwd.path_join("project.godot")) and not FileAccess.file_exists(cwd.path_join("main.tscn")) and not FileAccess.file_exists(cwd.path_join("fifty/scripts/runtime.gd")), "owned_cwd_has_no_plaintext_source_project"):
		return false
	var pack_sha: String = FileAccess.get_sha256(pack_path)
	var probe_sha: String = FileAccess.get_sha256(get_script().resource_path)
	var manifest_sha: String = FileAccess.get_sha256(options["manifest"])
	if not _check(_digest(pack_sha) and _digest(probe_sha) and _digest(manifest_sha) and _same_absolute_path(str(receipt.get("pack_path", "")), pack_path) and receipt.get("pack_sha256") == pack_sha and receipt.get("probe_sha256") == probe_sha and receipt.get("manifest_sha256") == manifest_sha and _digest(receipt.get("wrapper_sha256")), "launch_pack_probe_manifest_hashes_match_actual_files"):
		return false
	var expected_probe: String = ""
	var probe_rows: int = 0
	for row: Dictionary in manifest.get("source_archive_files", []):
		if row.get("path") == "recipe/probe_firstchapter_pck.gd":
			expected_probe = str(row.get("sha256", "")); probe_rows += 1
	if not _check(probe_rows == 1 and expected_probe == probe_sha, "probe_matches_prepared_source_archive"):
		return false
	var source_root_empty: bool = ProjectSettings.globalize_path("res://").is_empty()
	if not _check(source_root_empty, "packed_resource_root_has_no_source_filesystem_fallback"):
		return false
	if not _check(FileAccess.get_sha256(receipt_path) == receipt_sha, "immutable_launch_receipt_stable_during_read"):
		return false
	report["pck_sha256"] = pack_sha
	report["launch_proof"] = {"receipt_sha256": receipt_sha, "pack_sha256": pack_sha, "probe_sha256": probe_sha, "manifest_sha256": manifest_sha, "wrapper_sha256": receipt["wrapper_sha256"], "original_argv_source": "immutable_root_launch_receipt", "original_launch_has_main_pack": true, "source_project_path_supplied": false, "owned_cwd_empty_before": true, "resource_root_empty": source_root_empty, "filtered_engine_arg_count": OS.get_cmdline_args().size(), "filtered_os_args_used_as_original_argv": false}
	return true


func _same_absolute_path(first: String, second: String) -> bool:
	var a: String = first.replace("\\", "/").simplify_path()
	var b: String = second.replace("\\", "/").simplify_path()
	if not a.is_absolute_path() or not b.is_absolute_path(): return false
	return a.to_lower() == b.to_lower() if OS.get_name() == "Windows" else a == b


func _digest(value: Variant) -> bool:
	if not (value is String) or value.length() != 64: return false
	for index: int in range(value.length()):
		if not "0123456789abcdef".contains(value.substr(index, 1)): return false
	return true


func _check(ok: bool, name: String) -> bool:
	_checks.append({"name": name, "passed": ok})
	if not ok: _errors.append(name)
	return ok


func _options(args: PackedStringArray) -> Dictionary:
	var values: Dictionary = {}; var index: int = 0
	while index < args.size():
		var argument: String = args[index]; var key: String = ""; var value: String = ""
		if not argument.begins_with("--"): return {"ok": false}
		var equals: int = argument.find("=")
		if equals >= 0:
			key = argument.substr(2, equals - 2); value = argument.substr(equals + 1)
		else:
			if index + 1 >= args.size(): return {"ok": false}
			key = argument.substr(2); index += 1; value = args[index]
		if key not in ["phase", "manifest", "report", "native-reference", "pack", "launch-receipt"] or values.has(key) or value.is_empty(): return {"ok": false}
		values[key] = value; index += 1
	if values.get("phase") not in ["native", "pck"] or not values.has("manifest") or not values.has("report"): return {"ok": false}
	if values["phase"] == "pck" and (not values.has("native-reference") or not values.has("pack") or not values.has("launch-receipt")): return {"ok": false}
	values["ok"] = true
	return values
