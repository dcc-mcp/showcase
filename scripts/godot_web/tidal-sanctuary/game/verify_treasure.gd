extends SceneTree
## Integration regression of the real main scene. Fixture positioning and direct
## interact calls test game logic, not physical keyboard/touch or rendered quality.
## Run with an isolated XDG_DATA_HOME to keep the test save separate from play.

const SAVE_PATH := "user://tidal-sanctuary-v2.json"
var game: Node3D
var failures: Array[String] = []
var checks: Array[Dictionary] = []
var had_save := false
var original_save := ""

func _initialize() -> void:
 run.call_deferred()

func check(condition: bool, description: String) -> void:
 if not condition:
  failures.append(description)
  push_error(description)

func write_raw_save(text: String) -> void:
 var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
 check(file != null, "fixture can open save file")
 if file:
  file.store_string(text)
  file.flush()
  file.close()

func clear_save() -> void:
 if FileAccess.file_exists(SAVE_PATH):
  check(DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH)) == OK, "fixture can clear its save")

func reopen() -> void:
 if is_instance_valid(game):
  game.queue_free()
  await process_frame
 game = load("res://start.tscn").instantiate()
 root.add_child(game)
 game.set_physics_process(false)
 game.set_process(false)
 await process_frame

func place_at(point: Vector3, offset := Vector3.ZERO) -> void:
 game.player.position = point + offset
 game.player.velocity = Vector3.ZERO

func read_save() -> Dictionary:
 var result = JSON.parse_string(FileAccess.get_file_as_string(SAVE_PATH))
 check(result is Dictionary, "save is readable JSON")
 return result if result is Dictionary else {}

func run() -> void:
 had_save = FileAccess.file_exists(SAVE_PATH)
 if had_save:
  original_save = FileAccess.get_file_as_string(SAVE_PATH)
 clear_save()
 await reopen()
 check(not game.demo and not game.capture, "save tests run in normal game mode")
 check(game.quest_stage() == 0 and not game.loaded_found, "fresh game starts at chart")
 var safe_spawn: Vector3 = game.swim.safe_spawn_position

 for point: Vector3 in [game.lantern_points[1], game.lantern_points[2], game.beacon.position]:
  place_at(point)
  game.interact()
  check(game.quest_stage() == 0, "wrong-order treasure/ring cannot skip chart")
 place_at(game.lantern_points[0], Vector3(1.56, 0, 0))
 game.interact()
 check(game.quest_stage() == 0, "chart outside 1.55m interaction radius is rejected")
 place_at(game.lantern_points[0], Vector3(1.50, 0, 0))
 game.interact()
 check(game.quest_stage() == 1, "chart inside 1.55m interaction radius advances exactly once")
 for i in range(5):game.interact()
 check(game.quest_stage() == 1, "repeated chart interaction cannot collect distant grove key")
 var saved := read_save()
 check(saved.get("schema") == 2 and saved.get("quest_stage") == 1, "chart creates schema2 save")
 var chart_position: Vector3 = game.player.position
 await reopen()
 check(game.loaded_found and game.quest_stage() == 1, "fresh scene reload restores chart progress")
 check(game.player.position.distance_to(chart_position) < 0.15, "fresh scene reload retains valid land position")
 checks.append({"check": "chart_order_range_repeat_reload", "stage": game.quest_stage(), "interaction_radius": 1.55})

 place_at(game.lantern_points[2])
 game.interact()
 check(game.quest_stage() == 1, "pearl remains locked without grove key")
 place_at(game.lantern_points[1], Vector3(1.56, 0, 0))
 game.interact()
 check(game.quest_stage() == 1, "grove outside interaction radius is rejected")
 place_at(game.lantern_points[1], Vector3(1.50, 0, 0))
 game.interact()
 check(game.quest_stage() == 2, "grove key advances to pearl")
 for i in range(5):game.interact()
 check(game.quest_stage() == 2, "repeated grove interaction cannot collect pearl")
 place_at(game.lantern_points[2], Vector3(1.56, 0, 0))
 game.interact()
 check(game.quest_stage() == 2, "pearl outside interaction radius is rejected")
 place_at(game.lantern_points[2])
 game.player.position.y = game.swim.floating_height()
 game.language = "zh"
 game.save_game()
 await reopen()
 check(game.quest_stage() == 2 and game.language == "zh", "mid-quest save restores stage and language")
 check(absf(game.player.position.y - game.swim.floating_height()) < 0.025, "water save restores surface height")
 game.set_physics_process(true)
 for i in range(90):await physics_frame
 game.set_physics_process(false)
 check(game.swim.is_swimming() and absf(game.player.position.y - game.swim.floating_height()) < 0.04, "restored water save resumes stable actual swimming physics")
 game.interact()
 check(game.quest_stage() == 3, "pearl can be collected from actual swim surface")
 for i in range(5):game.interact()
 check(game.quest_stage() == 3 and not game.beacon_awakened, "repeated pearl interaction cannot finish distant ring")
 await reopen()
 check(game.quest_stage() == 3 and not game.beacon_awakened, "reload keeps final return to ring outstanding")
 checks.append({"check": "key_pearl_order_repeat_water_reload", "stage": game.quest_stage(), "language": game.language, "position_finite": game.player.position.is_finite()})

 place_at(game.beacon.position, Vector3(1.56, 0, 0))
 game.interact()
 check(game.quest_stage() == 3, "ring outside interaction radius is rejected")
 place_at(game.beacon.position, Vector3(1.50, 0, 0))
 game.interact()
 check(game.quest_stage() == 4 and game.beacon_awakened, "ring completes quest in range")
 for i in range(5):game.interact()
 check(game.quest_stage() == 4, "repeated completed interaction is idempotent")
 for i in range(5):game.on_action_pressed()
 check(game.quest_stage() == 4, "rapid completion button taps preserve the reward feedback")
 game.game_time += 3.1
 check(game.game_time >= game.restart_available_time, "completion restart cooldown expires")
 saved = read_save()
 check(saved.get("completed") == true and saved.get("beacon_awakened") == true, "completed state persists")
 game.on_action_pressed()
 check(game.quest_stage() == 0, "same-session completion button restarts after feedback cooldown")
 write_raw_save(JSON.stringify(saved))
 await reopen()
 check(game.quest_stage() == 4 and game.beam.visible, "fresh scene reload restores completion and lit ring")
 game.on_action_pressed()
 check(game.quest_stage() == 0 and game.activated == [false, false, false], "completion action button resets quest")
 check(game.player.position.distance_to(safe_spawn) < 0.001 and game.player.velocity == Vector3.ZERO, "reset returns to safe spawn with zero velocity")
 check(game.swim.state == &"walk" and not game.beam.visible, "reset clears swim state and ring glow")
 await reopen()
 check(game.quest_stage() == 0 and not game.beacon_awakened, "reset persists after fresh scene reload")
 checks.append({"check": "completion_repeat_reset_reload", "stage_after_reset": game.quest_stage(), "spawn": [game.player.position.x, game.player.position.y, game.player.position.z]})

 var corrupt_cases := [
  {"name": "legacy_schema", "raw": '{"schema":1,"activated":[true,true,true],"player":[0,0,0],"beacon_awakened":true}'},
  {"name": "truncated_json", "raw": '{"schema":2,"player":['},
  {"name": "nan_json", "raw": '{"schema":2,"activated":[false,false,false],"player":[NaN,0,0]}'},
  {"name": "overflow_number", "raw": '{"schema":2,"activated":[false,false,false],"player":[1e999,0,0]}'},
  {"name": "out_of_world", "raw": '{"schema":2,"activated":[false,false,false],"player":[500,-99,500]}'},
  {"name": "invalid_order", "raw": '{"schema":2,"activated":[false,true,true],"player":[1.3,0.8,10],"beacon_awakened":true}'}
 ]
 var corrupt_results: Array[Dictionary] = []
 for test: Dictionary in corrupt_cases:
  write_raw_save(test.raw)
  await reopen()
  check(game.player.position.is_finite() and game.player.velocity.is_finite(), "%s save never produces NaN/Inf transform" % test.name)
  check(Vector2(game.player.position.x, game.player.position.z).length() <= game.swim.ocean_radius, "%s save remains in safe world" % test.name)
  check(game.quest_stage() == 0 and not game.beacon_awakened, "%s save cannot bypass quest order" % test.name)
  corrupt_results.append({"case": test.name, "stage": game.quest_stage(), "finite": game.player.position.is_finite(), "loaded": game.loaded_found})
 checks.append({"check": "corrupt_save_recovery", "cases": corrupt_results})

 # JSON values are untrusted. Reject malformed flag types while retaining the
 # valid prefix of quest progress and the original numeric/bool save behavior.
 var flag_cases := [
  {"name": "string_chart", "flags": ["x", true, true], "beacon": true, "stage": 0},
  {"name": "null_chart", "flags": [null, true, true], "beacon": true, "stage": 0},
  {"name": "object_key", "flags": [true, {}, true], "beacon": true, "stage": 1},
  {"name": "null_key", "flags": [true, null, true], "beacon": true, "stage": 1},
  {"name": "array_pearl", "flags": [true, true, []], "beacon": true, "stage": 2},
  {"name": "string_pearl", "flags": [true, true, "true"], "beacon": true, "stage": 2},
  {"name": "string_beacon", "flags": [true, true, true], "beacon": "true", "stage": 3},
  {"name": "null_beacon", "flags": [true, true, true], "beacon": null, "stage": 3},
  {"name": "object_beacon", "flags": [true, true, true], "beacon": {}, "stage": 3},
  {"name": "numeric_flags", "flags": [1, -1, 0.5], "beacon": 1, "stage": 4},
  {"name": "numeric_zero_order", "flags": [1, 0, 1], "beacon": 1, "stage": 1}
 ]
 var flag_results: Array[Dictionary] = []
 for test: Dictionary in flag_cases:
  write_raw_save(JSON.stringify({"schema": 2, "activated": test.flags, "beacon_awakened": test.beacon, "language": "zh"}))
  await reopen()
  check(game.loaded_found and game.language == "zh", "%s loads without interrupting language restoration" % test.name)
  check(game.quest_stage() == test.stage, "%s preserves only valid ordered quest flags" % test.name)
  flag_results.append({"case": test.name, "stage": game.quest_stage(), "loaded": game.loaded_found, "language": game.language})
 checks.append({"check": "malformed_save_flags", "cases": flag_results})

 game.queue_free()
 await process_frame
 if had_save:write_raw_save(original_save)
 else:clear_save()
 print("TIDAL_TREASURE_CHECK ", JSON.stringify({"schema": 1, "engine": Engine.get_version_info().string, "route": "actual main scene save/reopen integration; direct interact calls and fixture positions, not rendered/physical input proof", "passed": failures.is_empty(), "failures": failures, "checks": checks}))
 quit(0 if failures.is_empty() else 1)
