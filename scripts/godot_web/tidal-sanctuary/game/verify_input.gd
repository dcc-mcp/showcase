extends SceneTree
## Engine Input.parse_input_event regression, not physical keyboard proof.
## Preserve the exact pre-existing save bytes, including damaged/non-UTF8 files.
const SAVE_PATH := "user://tidal-sanctuary-v2.json"
var game: Node3D
var failures: Array[String] = []
var checks: Array[Dictionary] = []
var had_save := false
var original_save := PackedByteArray()

func _initialize() -> void:
 run_checks.call_deferred()

func check(condition: bool, description: String) -> void:
 if not condition:
  failures.append(description)
  push_error(description)

func key(k: int, down: bool) -> void:
 var ev := InputEventKey.new()
 ev.keycode=k;ev.physical_keycode=k;ev.pressed=down
 Input.parse_input_event(ev)

func restore_save() -> void:
 if had_save:
  var file := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
  check(file != null, "original save can be restored")
  if file:
   file.store_buffer(original_save);file.flush();file.close()
  check(FileAccess.get_file_as_bytes(SAVE_PATH) == original_save, "original save bytes are unchanged")
 elif FileAccess.file_exists(SAVE_PATH):
  check(DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH)) == OK, "test-only save is removed")

func run_checks() -> void:
 had_save=FileAccess.file_exists(SAVE_PATH)
 if had_save:
  var reader := FileAccess.open(SAVE_PATH, FileAccess.READ)
  if reader == null:
   push_error("Cannot read existing save; input check did not start")
   quit(1)
   return
  var byte_count := reader.get_length()
  original_save=reader.get_buffer(byte_count)
  var read_ok := reader.get_error() == OK and original_save.size() == byte_count
  reader.close()
  if not read_ok:
   push_error("Cannot capture all original save bytes; input check did not start")
   quit(1)
   return
  if DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH)) != OK:
   push_error("Cannot isolate existing save; input check did not start")
   quit(1)
   return
 game=load("res://start.tscn").instantiate()
 root.add_child(game)
 await process_frame
 game.reset_game()
 await physics_frame
 var start: Vector3=game.player.position
 # Stop on the actual chart approach. A fixed 78-frame press overshot the
 # chart on the current camera-relative controller and was never run by CI.
 key(KEY_W,true)
 for i in range(78):
  await physics_frame
  var distance: Vector2=Vector2(game.player.position.x-game.lantern_points[0].x,game.player.position.z-game.lantern_points[0].z)
  if distance.length() < 1.0:break
 key(KEY_W,false)
 for i in range(12):await physics_frame
 key(KEY_E,true)
 await process_frame
 key(KEY_E,false)
 await process_frame
 var finish: Vector3=game.player.position
 check(finish.distance_to(start) > .5,"Input moves player")
 check(game.activated == [true,false,false],"E reads the shore chart")
 game.save_game()
 check(FileAccess.file_exists(SAVE_PATH),"input route writes its test save")
 checks.append({"check":"keyboard_movement_and_chart","start":str(start),"end":str(finish),"activated":game.activated.duplicate()})
 game.queue_free()
 await process_frame
 restore_save()
 checks.append({"check":"save_restoration","had_save":had_save,"save_exists":FileAccess.file_exists(SAVE_PATH),"byte_count":original_save.size()})
 print("TIDAL_INPUT_CHECK ",JSON.stringify({"schema":1,"engine":Engine.get_version_info().string,"route":"Godot Input.parse_input_event in headless engine; not physical keyboard proof","passed":failures.is_empty(),"failures":failures,"checks":checks}))
 quit(0 if failures.is_empty() else 1)
