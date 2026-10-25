class_name PurchaseGuard
extends RefCounted
## Optional, bounded purchase analysis around the authoritative campaign buy().
## Tickets are private one-shot capabilities, never caller-authored query data.
## Crypto entropy is separate from layout generation and the campaign sequence.

const Campaign = preload("res://scripts/campaign_rules.gd")
const Variants = preload("res://scripts/campaign_variant.gd")
const Solver = preload("res://tests/campaign_solver.gd")
const MAX_PENDING: int = 64
const GUARD_PATH: String = "res://scripts/purchase_guard.gd"
const SOLVER_PATH: String = "res://tests/campaign_solver.gd"
const NAVIGATION_PATH: String = "res://scripts/campaign_navigation.gd"
const FIXED_BINDINGS: Array[String] = ["content_id", "canonical_content_sha256", "rules_version", "rules_sha256", "variant_spec", "root_seed", "campaign_seed", "sequence_state", "attempt_index", "variant_draw_count", "floor_mirrors", "resolved_start", "transformed_content_sha256"]
const QUERY_DEFAULTS: Dictionary = {"max_expanded": 5000, "max_states": 20000, "max_msec": 15000, "navigation_max_nodes": 0}
const QUERY_CAPS: Dictionary = {"max_expanded": 5000, "max_states": 20000, "max_msec": 30000, "navigation_max_nodes": 100000}
const INSTANCE_CAPS: Dictionary = {"max_queries": 16, "max_total_msec": 120000}
const TIMING_NOTE: String = "Cooperative timing wraps each actual synchronous Solver.solve call, including its initialization. The current call cannot be preempted and may overrun its effective allowance; actual elapsed milliseconds are retained. No later query starts after either instance allowance is exhausted. This is not a global scheduler or hard real-time deadline."

var _game: RefCounted
var _pending: Dictionary = {}
var _crypto: Crypto = Crypto.new()
var _limits: Dictionary = INSTANCE_CAPS.duplicate(true)
var _limits_valid: bool = true
var _limits_error: String = ""
var _queries_used: int = 0
var _total_query_msec: int = 0
var _last_query_msec: int = 0
var _last_requested_budgets: Dictionary = {}
var _last_effective_budgets: Dictionary = {}
var _last_query_overran_effective_budget: bool = false


func _init(game: RefCounted = null, instance_limits: Dictionary = {}) -> void:
	_game = game
	_configure_limits(instance_limits)


func query_stats() -> Dictionary:
	return {
		"queries_used": _queries_used, "total_query_msec": _total_query_msec,
		"limits": _limits.duplicate(true),
		"remaining_queries": maxi(0, int(_limits["max_queries"]) - _queries_used),
		"remaining_total_msec": maxi(0, int(_limits["max_total_msec"]) - _total_query_msec),
		"configuration_valid": _limits_valid, "configuration_error": _limits_error,
		"last_query_msec": _last_query_msec,
		"last_requested_budgets": _last_requested_budgets.duplicate(true),
		"last_effective_budgets": _last_effective_budgets.duplicate(true),
		"last_query_overran_effective_budget": _last_query_overran_effective_budget,
		"timing_mode": "cooperative_solver_wall_time", "timing_note": TIMING_NOTE,
	}.duplicate(true)


func preview(offer: Variant, budgets: Dictionary = {}) -> Dictionary:
	if not _limits_valid:
		return _reply(false, "invalid_instance_limits", _limits_error, {"requested_budgets": budgets.duplicate(true), "effective_budgets": {}, "query_accounting": query_stats()})
	if not _ready_game():
		return _reply(false, "unavailable", "An active campaign with the strict snapshot/clone API is required.")
	if _pending.size() >= MAX_PENDING:
		return _reply(false, "pending_limit", "Cancel or consume an earlier preview before opening another purchase query.")
	if not _valid_budgets(budgets):
		return _reply(false, "invalid_budgets", "Only bounded integer query limits are accepted: max_expanded 1..5000, max_states 1..20000, max_msec 1..30000, navigation_max_nodes 0..100000.", {"requested_budgets": budgets.duplicate(true), "effective_budgets": {}, "query_accounting": query_stats()})
	var requested_budgets: Dictionary = QUERY_DEFAULTS.duplicate(true)
	for field: String in budgets:
		requested_budgets[field] = int(budgets[field])
	var refusal: Dictionary = _limit_refusal(requested_budgets)
	if not refusal.is_empty():
		return refusal
	var before: Dictionary = _game.campaign_snapshot().duplicate(true)
	var before_json: String = Variants.canonical_json(before)
	var before_binding: Dictionary = _binding(_game, before)
	if not _valid_binding(before_binding) or before_json.is_empty():
		return _reply(false, "unbound_campaign", "Current content, rule, solver and guard sources could not be bound exactly.")
	var resolved: Dictionary = _resolve_offer(offer)
	if not bool(resolved.get("ok", false)):
		return _reply(false, str(resolved.get("status", "invalid_offer")), str(resolved.get("message", "No matching adjacent shop offer.")))
	var query: RefCounted = _game.clone_for_search()
	if query == null or not _same(query.campaign_snapshot(), before):
		return _preview_error(before, "clone_mismatch", "An isolated query clone did not equal the full original snapshot.")
	var purchased: Dictionary = query.buy(str(resolved["choice"]))
	if not bool(purchased.get("ok", false)):
		var rejected: Dictionary = _preview_error(before, "purchase_rejected", "The authoritative buy() rejected this offer; the original campaign was not purchased.")
		rejected["buy_result"] = purchased.duplicate(true)
		return rejected
	var after: Dictionary = query.campaign_snapshot().duplicate(true)
	var after_json: String = Variants.canonical_json(after)
	var after_binding: Dictionary = _binding(query, after)
	if not _valid_binding(after_binding) or after_json.is_empty():
		return _preview_error(before, "unbound_purchase", "The proposed purchase could not be bound to the exact active sources.")
	refusal = _limit_refusal(requested_budgets)
	if not refusal.is_empty():
		return refusal
	var effective_budgets: Dictionary = requested_budgets.duplicate(true)
	effective_budgets["max_msec"] = mini(int(requested_budgets["max_msec"]), int(_limits["max_total_msec"]) - _total_query_msec)
	_queries_used += 1
	_last_requested_budgets = requested_budgets.duplicate(true)
	_last_effective_budgets = effective_budgets.duplicate(true)
	var query_started: int = Time.get_ticks_msec()
	var report: Dictionary = Solver.solve(query, effective_budgets.duplicate(true))
	_last_query_msec = maxi(0, Time.get_ticks_msec() - query_started)
	_total_query_msec += _last_query_msec
	_last_query_overran_effective_budget = _last_query_msec > int(effective_budgets["max_msec"])
	var accounting: Dictionary = query_stats()
	var query_now: Dictionary = query.campaign_snapshot()
	if not _same(query_now, after) or not _same(_binding(query, query_now), after_binding):
		var mutated: Dictionary = _preview_error(before, "solver_mutated_query", "The solver changed its supplied query clone or its source binding. No ticket was issued.")
		mutated["solver_report"] = report.duplicate(true)
		mutated["requested_budgets"] = requested_budgets.duplicate(true)
		mutated["effective_budgets"] = effective_budgets.duplicate(true)
		mutated["query_accounting"] = accounting
		return mutated
	var original_now: Dictionary = _game.campaign_snapshot()
	if not _same(original_now, before):
		var changed: Dictionary = _preview_error(before, "preview_mutated_original", "An isolated preview changed the original campaign. Its complete prior snapshot was restored where possible.")
		changed.merge({"requested_budgets": requested_budgets, "effective_budgets": effective_budgets, "query_accounting": accounting, "solver_report": report}, true)
		return changed.duplicate(true)
	if not _same(_binding(_game, original_now), before_binding):
		return _reply(false, "source_changed", "A bound source changed during analysis. The original campaign was not purchased.", {"before_binding": before_binding, "actual_binding": _binding(_game, original_now), "solver_report": report, "requested_budgets": requested_budgets, "effective_budgets": effective_budgets, "query_accounting": accounting})
	var classification: Dictionary = _classify(report, after, after_binding)
	if _last_query_overran_effective_budget:
		classification = {"classification": "unknown", "message": "The synchronous solver call exceeded its cooperative effective time allowance. No known-winning or known-losing purchase claim is made; the original purchase may continue without a safety guarantee."}
	var token: String = _new_token()
	if token.is_empty():
		return _reply(false, "entropy_unavailable", "A private one-shot token could not be created. No RNG or campaign sequence fallback was used.", {"requested_budgets": requested_budgets, "effective_budgets": effective_budgets, "query_accounting": accounting, "solver_report": report})
	var ticket: Dictionary = {
		"token": token, "game_instance_id": _game.get_instance_id(),
		"classification": classification["classification"], "message": classification["message"],
		"offer": resolved["offer"], "shop_id": resolved["shop_id"], "choice": resolved["choice"],
		"offer_definition": resolved["offer_definition"].duplicate(true),
		"before_snapshot": before.duplicate(true), "after_snapshot": after.duplicate(true),
		"before_binding": before_binding.duplicate(true), "after_binding": after_binding.duplicate(true),
		"before_json": before_json, "after_json": after_json,
		"solver_report": report.duplicate(true), "solver_receipt": report.get("receipt", {}).duplicate(true),
		"requested_budgets": requested_budgets.duplicate(true), "effective_budgets": effective_budgets.duplicate(true),
		"query_accounting": accounting.duplicate(true),
	}
	_pending[token] = ticket
	return _reply(true, "previewed", str(classification["message"]), _public_ticket(ticket))


func commit(token: Variant, confirmed: bool = false) -> Dictionary:
	if not (token is String) or not _pending.has(token):
		return _reply(false, "invalid_token", "Only an unconsumed String token issued by this guard can commit.")
	# Consume before every check, including the default losing-purchase block.
	var ticket: Dictionary = _pending[token]
	_pending.erase(token)
	var common: Dictionary = _public_ticket(ticket)
	common["token_consumed"] = true
	common["confirmed"] = confirmed
	common["accepted_known_loss"] = false
	common["expected_after_binding"] = ticket["after_binding"].duplicate(true)
	if _game == null or not _game.has_method("campaign_snapshot") or _game.get_instance_id() != int(ticket["game_instance_id"]):
		return _reply(false, "unavailable", "The original campaign authority is no longer available. The ticket was consumed.", common)
	var current: Dictionary = _game.campaign_snapshot()
	var current_binding: Dictionary = _binding(_game, current)
	if not _same(current, ticket["before_snapshot"]) or not _same(current_binding, ticket["before_binding"]):
		common["actual_after_snapshot"] = current.duplicate(true)
		common["actual_binding"] = current_binding
		return _reply(false, "stale_preview", "The full campaign snapshot or rule/solver/guard source binding changed. No purchase was executed; the ticket was consumed.", common)
	if ticket["classification"] == "known_losing" and not confirmed:
		common["after_snapshot"] = current.duplicate(true)
		common["after_binding"] = current_binding
		common["actual_after_snapshot"] = current.duplicate(true)
		return _reply(false, "blocked_known_loss", "This exact purchase has no ordinary winning continuation under the bound complete solver result. Explicit confirmation is required; no game state changed.", common)
	var actual: Dictionary = _game.buy(str(ticket["choice"]))
	var after: Dictionary = _game.campaign_snapshot()
	var actual_binding: Dictionary = _binding(_game, after)
	common["buy_result"] = actual.duplicate(true)
	common["actual_after_snapshot"] = after.duplicate(true)
	common["after_snapshot"] = after.duplicate(true)
	common["after_binding"] = actual_binding
	if not bool(actual.get("ok", false)) or not _same(after, ticket["after_snapshot"]) or not _same(actual_binding, ticket["after_binding"]):
		var rollback: Dictionary = _restore_before(ticket["before_snapshot"])
		common.merge(rollback, true)
		return _reply(false, "commit_mismatch", "The actual purchase did not equal its exact private preview. A complete rollback was attempted; inspect rollback_ok and rollback_snapshot before continuing.", common)
	if ticket["classification"] == "known_losing":
		common["accepted_known_loss"] = true
		return _reply(true, "accepted_known_loss", "The explicitly accepted purchase was executed. Its known loss was not automatically converted into campaign failure or a respawn.", common)
	if ticket["classification"] == "known_winning":
		return _reply(true, "committed_known_winning", "The purchase was executed and has one verified winning suffix. Other subsequent choices may still lose.", common)
	return _reply(true, "committed_unknown", "The purchase was executed with the original buy() semantics. This bounded or unverified query gives no safety guarantee.", common)


func cancel(token: Variant) -> Dictionary:
	if not (token is String) or not _pending.has(token):
		return _reply(false, "invalid_token", "Only an unconsumed String token issued by this guard can be cancelled.")
	var ticket: Dictionary = _pending[token]
	_pending.erase(token)
	var values: Dictionary = _public_ticket(ticket)
	values["token_consumed"] = true
	return _reply(true, "cancelled", "The one-shot preview was consumed without changing the campaign.", values)


func _ready_game() -> bool:
	if _game == null:
		return false
	for method: String in ["campaign_snapshot", "current_state_sha256", "clone_for_search", "restore_snapshot", "buy", "is_active"]:
		if not _game.has_method(method):
			return false
	return bool(_game.is_active())


func _resolve_offer(value: Variant) -> Dictionary:
	if not (value is String) or str(value).is_empty():
		return {"ok": false, "status": "invalid_offer", "message": "Offer must be a choice String or a shop/choice String."}
	var parts: PackedStringArray = str(value).split("/", true)
	if parts.size() > 2 or parts[parts.size() - 1].is_empty():
		return {"ok": false, "status": "invalid_offer", "message": "Offer must identify exactly one shop and one choice."}
	var state_value: Dictionary = _game.state
	var data_value: Dictionary = _game.data
	var shop: Dictionary = {}
	# Match frozen BaseRules.buy(): first adjacent shop in declared object order.
	for item: Dictionary in data_value["floors"][int(state_value["floor"])]["objects"]:
		if item.get("kind", "") == "shop" and absi(int(item["pos"][0]) - int(state_value["pos"][0])) + absi(int(item["pos"][1]) - int(state_value["pos"][1])) <= 1:
			shop = item
			break
	if shop.is_empty():
		return {"ok": false, "status": "shop_unavailable", "message": "Stand next to the actual selected shop before previewing a purchase."}
	if parts.size() == 2 and parts[0] != str(shop["id"]):
		return {"ok": false, "status": "shop_not_selected", "message": "The qualified offer is not from the first shop selected by authoritative buy()."}
	var choice: String = parts[parts.size() - 1]
	for offer: Dictionary in data_value["shops"][shop["type"]]["offers"]:
		if str(offer["id"]) == choice:
			return {"ok": true, "offer": str(shop["id"]) + "/" + choice, "shop_id": str(shop["id"]), "choice": choice, "offer_definition": offer.duplicate(true)}
	return {"ok": false, "status": "invalid_offer", "message": "The selected shop has no such offer."}


func _binding(game: RefCounted, snapshot_value: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	for field: String in FIXED_BINDINGS:
		result[field] = snapshot_value.get(field)
	result["full_snapshot_sha256"] = Variants.content_hash(snapshot_value)
	result["state_sha256"] = game.current_state_sha256()
	result["active_data_sha256"] = Variants.content_hash(game.data)
	result["solver_active_data_sha256"] = JSON.stringify(game.data).sha256_text()
	result["rules_fingerprint"] = Campaign.rules_fingerprint()
	result["solver_source_sha256"] = FileAccess.get_sha256(SOLVER_PATH)
	result["navigation_source_sha256"] = FileAccess.get_sha256(NAVIGATION_PATH)
	result["guard_source_sha256"] = FileAccess.get_sha256(GUARD_PATH)
	return result


func _valid_binding(value: Dictionary) -> bool:
	for field: String in ["canonical_content_sha256", "transformed_content_sha256", "rules_sha256", "full_snapshot_sha256", "state_sha256", "active_data_sha256", "solver_active_data_sha256", "rules_fingerprint", "solver_source_sha256", "navigation_source_sha256", "guard_source_sha256"]:
		if not _is_hash(value.get(field)):
			return false
	return value["rules_sha256"] == value["rules_fingerprint"] and value["transformed_content_sha256"] == value["active_data_sha256"]


func _classify(report: Dictionary, after: Dictionary, binding: Dictionary) -> Dictionary:
	var unknown: Dictionary = {"classification": "unknown", "message": "The bounded query did not establish an exact complete answer. The purchase may continue, with no safety guarantee."}
	if not report.get("result", "") in ["witness", "unsatisfiable"]:
		return unknown
	var receipt: Variant = report.get("receipt")
	if not (receipt is Dictionary) or not (receipt.get("complete") is bool) or not bool(receipt["complete"]) or receipt.get("status", "") != report["result"] or receipt.get("solver", "") != Solver.SOLVER_VERSION or report.get("solver", "") != Solver.SOLVER_VERSION:
		return unknown
	for field: String in ["state_sha256", "canonical_content_sha256", "transformed_content_sha256", "rules_sha256"]:
		if receipt.get(field, "") != binding[field]:
			return unknown
	if report.get("solver_source_sha256", "") != binding["solver_source_sha256"] or report.get("navigation_source_sha256", "") != binding["navigation_source_sha256"] or report.get("active_data_sha256", "") != binding["solver_active_data_sha256"]:
		return unknown
	if not (report.get("initial_snapshot") is Dictionary) or not _same(report["initial_snapshot"], after) or not (report.get("errors") is Array) or not report["errors"].is_empty():
		return unknown
	if report["result"] == "unsatisfiable":
		if not report.has("unexplored_states") or int(report["unexplored_states"]) != 0 or bool(after.get("failed", true)) or bool(after.get("core_state", {}).get("won", true)):
			return unknown
		return {"classification": "known_losing", "message": "This exact post-purchase state has no winning ordinary continuation under a complete, state-bound solver result. Commit requires explicit confirmation; reset and respawn are outside that proof."}
	var verified: Variant = report.get("witness_verification")
	if not (verified is Dictionary) or not (verified.get("ok") is bool) or not bool(verified["ok"]) or not (verified.get("won") is bool) or not bool(verified["won"]) or not (verified.get("core_state_matches_search") is bool) or not bool(verified["core_state_matches_search"]):
		return unknown
	if not (report.get("witness") is Array) or report["witness"].is_empty() or not (verified.get("final_snapshot") is Dictionary):
		return unknown
	var final_snapshot: Dictionary = verified["final_snapshot"]
	if bool(final_snapshot.get("failed", true)) or not bool(final_snapshot.get("core_state", {}).get("won", false)):
		return unknown
	for field: String in FIXED_BINDINGS:
		if not _same(final_snapshot.get(field), after.get(field)):
			return unknown
	return {"classification": "known_winning", "message": "This exact post-purchase state has a continuously replayed winning suffix. It does not make every later purchase or combat order safe."}


func _new_token() -> String:
	for attempt: int in range(8):
		var bytes: PackedByteArray = _crypto.generate_random_bytes(32)
		if bytes.size() != 32:
			return ""
		var token: String = bytes.hex_encode()
		if not _pending.has(token):
			return token
	return ""


func _public_ticket(ticket: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	for field: String in ["token", "classification", "offer", "shop_id", "choice", "offer_definition", "before_snapshot", "after_snapshot", "before_binding", "after_binding", "solver_report", "solver_receipt", "requested_budgets", "effective_budgets", "query_accounting"]:
		result[field] = ticket[field]
	return result.duplicate(true)


func _preview_error(before: Dictionary, status: String, message: String) -> Dictionary:
	var actual: Dictionary = _game.campaign_snapshot()
	var extra: Dictionary = {"original_unchanged": _same(actual, before), "actual_after_snapshot": actual.duplicate(true)}
	if not bool(extra["original_unchanged"]):
		extra.merge(_restore_before(before), true)
	return _reply(false, status, message, extra)


func _restore_before(before: Dictionary) -> Dictionary:
	var restored: bool = _game.restore_snapshot(before.duplicate(true))
	var actual: Dictionary = _game.campaign_snapshot()
	var same: bool = _same(actual, before)
	return {"rollback_attempted": true, "rollback_ok": restored and same, "rollback_restore_returned": restored, "rollback_snapshot_matches": same, "rollback_snapshot": actual.duplicate(true)}


func _reply(ok: bool, status: String, message: String, values: Dictionary = {}) -> Dictionary:
	var result: Dictionary = {"ok": ok, "status": status, "action": status, "message": message, "classification": "unknown", "token_consumed": false, "query_accounting": query_stats()}
	result.merge(values, true)
	return result.duplicate(true)


func _valid_budgets(budgets: Dictionary) -> bool:
	for field: Variant in budgets:
		if not (field is String) or not QUERY_CAPS.has(field):
			return false
		var value: Variant = budgets[field]
		var minimum: int = 0 if field == "navigation_max_nodes" else 1
		if not _bounded_integer(value, minimum, int(QUERY_CAPS[field])):
			return false
	return true


func _configure_limits(requested: Dictionary) -> void:
	var normalized: Dictionary = INSTANCE_CAPS.duplicate(true)
	for field: Variant in requested:
		if not (field is String) or not INSTANCE_CAPS.has(field) or not _bounded_integer(requested[field], 1, int(INSTANCE_CAPS[field])):
			_limits_valid = false
			_limits_error = "Instance limits only allow downward bounds: max_queries 1..16 and max_total_msec 1..120000. Unknown fields and raised limits are rejected."
			return
		normalized[field] = int(requested[field])
	_limits = normalized


func _limit_refusal(requested: Dictionary) -> Dictionary:
	var values: Dictionary = {"requested_budgets": requested.duplicate(true), "effective_budgets": {}, "query_accounting": query_stats()}
	if _queries_used >= int(_limits["max_queries"]):
		return _reply(false, "query_limit_reached", "The instance solver-call allowance is exhausted. Cancelling tickets does not reset it; no purchase or new query was executed.", values)
	if _total_query_msec >= int(_limits["max_total_msec"]):
		return _reply(false, "total_time_limit_reached", "The cumulative cooperative solver time allowance is exhausted. No new query or known-result claim was made.", values)
	return {}


func _bounded_integer(value: Variant, minimum: int, maximum: int) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) == floorf(float(value)) and float(value) >= minimum and float(value) <= maximum


func _same(a: Variant, b: Variant) -> bool:
	var first: String = Variants.canonical_json(a)
	var second: String = Variants.canonical_json(b)
	return not first.is_empty() and first == second


func _is_hash(value: Variant) -> bool:
	if not (value is String) or value.length() != 64:
		return false
	for letter: String in value:
		if not "0123456789abcdef".contains(letter):
			return false
	return true
