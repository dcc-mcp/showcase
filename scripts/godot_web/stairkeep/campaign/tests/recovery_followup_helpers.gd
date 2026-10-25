class_name RecoveryFollowupHelpers
extends RefCounted
## Test-only evidence I/O and optional isolated planning. No runtime/source edits.

const BaseRules = preload("res://scripts/base_rules.gd")
const Variants = preload("res://scripts/campaign_variant.gd")
const Campaign = preload("res://scripts/campaign_rules.gd")
const MAX_QUEUE_BYTES: int = 33554432
const MAX_LINE_BYTES: int = 67108864
const FROZEN_FILES: Dictionary = {
	"source_data_sha256": "res://data/levels21.json",
	"base_rules_sha256": "res://scripts/base_rules.gd",
	"variant_sha256": "res://scripts/campaign_variant.gd",
	"navigation_sha256": "res://scripts/campaign_navigation.gd",
	"simulation_sha256": "res://tests/simulate_campaign.gd",
	"campaign_rules_sha256": "res://scripts/campaign_rules.gd",
	"campaign_save_v2_sha256": "res://scripts/campaign_save_v2.gd",
	"purchase_guard_sha256": "res://scripts/purchase_guard.gd",
	"failure_replayer_sha256": "res://tests/replay_campaign_failures.gd",
}
const REQUIRED_BASELINE: Array[String] = ["source_data_sha256", "base_rules_sha256", "variant_sha256", "navigation_sha256", "simulation_sha256"]


static func load_queue(path: String) -> Dictionary:
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > MAX_QUEUE_BYTES:
		return {"ok": false, "error": "Input queue is unavailable or exceeds the bounded JSON size."}
	var json: JSON = JSON.new()
	var text: String = file.get_as_text()
	file.close()
	if json.parse(text) != OK or not (json.data is Dictionary):
		return {"ok": false, "error": "Input queue is not a complete JSON dictionary."}
	var input: Dictionary = json.data
	if input.get("schema_version", -1) != 1 or not (input.get("source_bindings") is Dictionary) or not (input.get("source_files") is Dictionary):
		return {"ok": false, "error": "Unsupported recovery queue schema or missing source bindings."}
	var path_contract: Dictionary = input.get("input", {})
	if path_contract.get("path_base_relative_to", "") != "input_file_directory":
		return {"ok": false, "error": "Recovery path base must be relative to the input-file directory."}
	var absolute_input: String = ProjectSettings.globalize_path(path)
	if not absolute_input.is_absolute_path():
		return {"ok": false, "error": "Pass an absolute path or a resolvable Godot resource/user path for the input queue."}
	var base_dir: String = absolute_input.get_base_dir().path_join(str(path_contract.get("path_base", "."))).simplify_path()
	return {"ok": true, "input": input, "base_dir": base_dir, "input_sha256": FileAccess.get_sha256(path), "input_file": absolute_input.get_file(), "input_bytes": text.to_utf8_buffer().size()}


static func verify_source_bindings(input: Dictionary) -> Dictionary:
	var expected: Dictionary = input.get("source_bindings", {})
	var observed: Dictionary = {}
	var errors: Array = []
	for field: String in REQUIRED_BASELINE:
		if not is_hash(expected.get(field)):
			errors.append("Missing baseline source hash: " + field)
	for field: String in FROZEN_FILES:
		if not expected.has(field):
			continue
		var actual: String = FileAccess.get_sha256(FROZEN_FILES[field])
		observed[field] = actual
		if not is_hash(expected[field]) or actual != str(expected[field]).to_lower():
			errors.append("Frozen source differs from the original input: " + field)
	return {"ok": errors.is_empty(), "errors": errors, "observed": observed, "frozen_parent_commit": expected.get("faf_commit", ""), "rules_fingerprint": Campaign.rules_fingerprint()}


static func verify_raw_sources(cases: Array, source_files: Dictionary, base_dir: String) -> Dictionary:
	var wanted: Dictionary = {}
	var observed: Dictionary = {}
	var errors: Array = []
	for item: Dictionary in cases:
		for field: String in ["trace_locator", "verification_locator", "full_terminal_proof_locator"]:
			if item.get(field) is Dictionary:
				wanted[str(item[field].get("path", ""))] = true
	for relative: String in wanted:
		if relative.is_empty() or not source_files.has(relative):
			errors.append("Locator is not bound by source_files: " + relative)
			continue
		var resolved: Dictionary = resolve_bound_path(relative, base_dir)
		if not bool(resolved["ok"]):
			errors.append(str(resolved["error"]))
			continue
		var path: String = resolved["path"]
		var expected: Dictionary = source_files[relative]
		var file: FileAccess = FileAccess.open(path, FileAccess.READ)
		if file == null:
			errors.append("Original raw source is unavailable: " + relative)
			continue
		var size: int = file.get_length()
		var first: String = file.get_line()
		file.close()
		var hash: String = FileAccess.get_sha256(path)
		var expected_hash: String = str(expected.get("raw_sha256", expected.get("sha256", "")))
		if not is_hash(expected_hash) or hash != expected_hash or (expected.has("bytes") and int(expected["bytes"]) != size):
			errors.append("Original raw bytes/hash differ: " + relative)
		var parsed: JSON = JSON.new()
		var engine_matches: bool = true
		var source_matches: bool = true
		if parsed.parse(first) != OK or not (parsed.data is Dictionary) or parsed.data.get("kind", "") != "replay_header":
			errors.append("Original raw source does not start with its replay header: " + relative)
			continue
		var header: Dictionary = parsed.data
		for field: String in ["major", "minor", "patch", "status", "build", "hash"]:
			engine_matches = engine_matches and header.get("engine", {}).get(field) == Engine.get_version_info().get(field)
		for field: String in REQUIRED_BASELINE:
			source_matches = source_matches and header.get("source_hashes", {}).get(field, "") == FileAccess.get_sha256(FROZEN_FILES[field])
		if not engine_matches or not source_matches:
			errors.append("Original replay engine or baseline source identity differs: " + relative)
		observed[relative] = {"raw_sha256": hash, "bytes": size, "engine_matches": engine_matches, "baseline_sources_match": source_matches}
	return {"ok": errors.is_empty(), "files": observed, "errors": errors}


static func resolve_bound_path(relative: String, base_dir: String) -> Dictionary:
	if relative.is_empty() or relative.is_absolute_path() or relative.begins_with("res://") or relative.begins_with("user://"):
		return {"ok": false, "error": "A raw locator must use a workspace-relative path."}
	var clean_base: String = base_dir.replace("\\", "/").trim_suffix("/")
	var path: String = clean_base.path_join(relative.replace("\\", "/")).simplify_path()
	var comparison: String = path.to_lower()
	if comparison != clean_base.to_lower() and not comparison.begins_with(clean_base.to_lower() + "/"):
		return {"ok": false, "error": "Raw locator escapes its bound workspace root."}
	return {"ok": true, "path": path}


static func read_bound_line(locator: Dictionary, base_dir: String, source_files: Dictionary = {}) -> Dictionary:
	var relative: String = str(locator.get("path", ""))
	var resolved: Dictionary = resolve_bound_path(relative, base_dir)
	if not bool(resolved["ok"]):
		return resolved
	if not whole(locator.get("byte_offset")) or not whole(locator.get("byte_length")) or int(locator["byte_offset"]) < 0 or int(locator["byte_length"]) < 1 or int(locator["byte_length"]) > MAX_LINE_BYTES or not is_hash(locator.get("line_sha256")):
		return {"ok": false, "error": "Invalid bounded byte locator: " + relative}
	if not source_files.is_empty():
		if not source_files.has(relative):
			return {"ok": false, "error": "Raw locator has no source-file binding: " + relative}
		var expected: String = str(source_files[relative].get("raw_sha256", source_files[relative].get("sha256", "")))
		if locator.has("source_raw_sha256") and locator["source_raw_sha256"] != expected:
			return {"ok": false, "error": "Locator/file raw hash bindings disagree: " + relative}
	var file: FileAccess = FileAccess.open(resolved["path"], FileAccess.READ)
	if file == null or int(locator["byte_offset"]) + int(locator["byte_length"]) > file.get_length():
		return {"ok": false, "error": "Raw locator is outside the existing file: " + relative}
	file.seek(int(locator["byte_offset"]))
	var bytes: PackedByteArray = file.get_buffer(int(locator["byte_length"]))
	file.close()
	var hasher: HashingContext = HashingContext.new()
	hasher.start(HashingContext.HASH_SHA256)
	hasher.update(bytes)
	var hash: String = hasher.finish().hex_encode()
	if bytes.size() != int(locator["byte_length"]) or hash != locator["line_sha256"]:
		return {"ok": false, "error": "Exact original line SHA-256 mismatch: " + relative}
	var json: JSON = JSON.new()
	if json.parse(bytes.get_string_from_utf8()) != OK or not (json.data is Dictionary):
		return {"ok": false, "error": "The bound raw line is not a JSON dictionary: " + relative}
	return {"ok": true, "record": json.data, "raw_sha256": hash, "byte_length": bytes.size(), "path": relative, "locator": locator.duplicate(true)}


static func same(a: Variant, b: Variant) -> bool:
	var left: String = Variants.canonical_json(a)
	return not left.is_empty() and left == Variants.canonical_json(b)


static func core_equal(a: Dictionary, b: Dictionary) -> bool:
	# The canonical serializer only normalizes the declared cleared-ID set;
	# floor/position, every resource and exact purchase count remain present.
	return same(a, b)


static func budget(state: Dictionary) -> Dictionary:
	return {"floor": int(state["floor"]) + 1, "pos": state["pos"].duplicate(), "hp": int(state["hp"]), "atk": int(state["atk"]), "def": int(state["def"]), "gold": int(state["gold"]), "keys": state["keys"].duplicate(true), "cleared_count": state["cleared"].size(), "purchases": state["purchases"].duplicate(true), "won": bool(state["won"])}


static func planning_game(actual: RefCounted) -> Dictionary:
	if actual.has_method("is_active") and not bool(actual.is_active()):
		return {"ok": false, "error": "A terminal campaign is not an active planning authority."}
	var core: Dictionary = actual.state
	var planner = BaseRules.new("")
	planner.data = actual.data
	if not planner._valid_state(core):
		return {"ok": false, "error": "The actual complete core state failed the frozen validator."}
	planner.state = core.duplicate(true)
	return {"ok": true, "game": planner, "actual_core_sha256": Variants.content_hash(core), "scope": "An isolated validated BaseRules planning copy; only the actual CampaignRules may execute the selected actions."}


static func sequence_equal(a: Dictionary, b: Dictionary) -> bool:
	for field: String in ["content_id", "canonical_content_sha256", "rules_version", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "attempt_index", "variant_draw_count", "floor_mirrors", "resolved_start", "transformed_content_sha256"]:
		if not same(a.get(field), b.get(field)):
			return false
	return true


static func whole(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and abs(float(value)) <= 9007199254740991.0


static func is_hash(value: Variant) -> bool:
	if not (value is String) or value.length() != 64:
		return false
	for letter: String in value:
		if not "0123456789abcdef".contains(letter):
			return false
	return true
