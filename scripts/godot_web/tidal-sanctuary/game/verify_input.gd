extends SceneTree
var game:Node3D
func _initialize():
 game=load("res://start.tscn").instantiate()
 root.add_child.call_deferred(game)
 run_checks.call_deferred()
func key(k:int,down:bool)->void:
 var ev:=InputEventKey.new();ev.keycode=k;ev.physical_keycode=k;ev.pressed=down
 Input.parse_input_event(ev)
func run_checks():
 await process_frame
 game.reset_game()
 await physics_frame
 var start:Vector3=game.player.position
 key(KEY_W,true)
 for i in range(78):await physics_frame
 key(KEY_W,false)
 key(KEY_E,true)
 await process_frame
 key(KEY_E,false)
 await process_frame
 assert(game.player.position.distance_to(start)>.5,"Input did not move player")
 assert(game.activated==[true,false,false],"E did not activate first lantern")
 game.save_game()
 print("TIDAL_INPUT_CHECK ",JSON.stringify({"route":"Godot Input.parse_input_event in headless engine; not physical keyboard proof","start":str(start),"end":str(game.player.position),"activated":game.activated,"save_exists":FileAccess.file_exists(game.SAVE_PATH)}))
 quit()
