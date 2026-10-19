extends SceneTree
## Isolated integration fixtures, never a real-input acceptance claim.
var failures:Array=[]
var checks:=0
func _initialize():call_deferred("run")
func check(ok:bool,message:String):
 checks+=1
 if not ok:failures.append(message);push_error(message)
func run():
 var main=load("res://main.gd").new()
 root.add_child(main)
 await process_frame
 main.game.set_physics_process(false)
 main.set_process(false)
 main.art.set_process(false)
 main.hud._activate("start",null)
 main.hud._activate("restart",null)
 check(main.game.paused and main.hud.confirming,"Restart dialog pauses active game")
 main.hud._activate("pause",null)
 main.hud._activate("restart",null)
 main.hud._activate("help",null)
 main._command("modal_open",null)
 check(main.game.paused and not main.hud.help_open and not main._modal_was_paused,"Repeated modal controls cannot unpause or replace origin")
 main.hud._activate("cancel",null)
 check(not main.game.paused and not main._modal_open,"Cancel returns to originally active game")
 main._command("pause",null)
 main.hud._activate("restart",null)
 main.hud._activate("cancel",null)
 check(main.game.paused and not main.hud.confirming,"Cancel preserves originally paused game")
 main.hud._activate("resume",null)
 main.hud.shop="equipment"
 main.hud._activate("restart",null)
 var escape:=InputEventKey.new();escape.pressed=true;escape.physical_keycode=KEY_ESCAPE
 main._input(escape)
 check(not main.hud.confirming and not main.game.paused and main.hud.shop=="equipment","Escape closes top modal before shop")
 main.hud.shop="";main.hud._layout()
 var boss_id:int=main.game._spawn_enemy("boss",0,8)
 check(main.hud.panels.boss_panel.visible,"Boss arrival immediately shows health panel")
 main.game._damage_enemy(boss_id,100000.0,"holy")
 check(not main.hud.panels.boss_panel.visible,"Boss death immediately hides health panel")
 main.art.effect("boss_warning",Vector3.ZERO,4.5)
 var effect_count:int=main.art.effects.size()
 var warning:Dictionary=main.art.effects[-1]
 main._command("pause",null)
 main.art._process(.4)
 check(main.art.effects.size()==effect_count and is_equal_approx(warning.remaining,1.0),"Paused boss warning keeps its full duration")
 main._command("pause",null);main.game.set_speed(2.0)
 main.art._process(.1)
 check(is_equal_approx(warning.remaining,.8),"Warning follows double simulation speed")
 main.hud._activate("restart",null);main.hud._activate("confirm_restart",null)
 check(not main._modal_open and not main.game.paused and main.game.wave==0,"Confirmed restart clears modal lifecycle")
 print("DAWNKEEP_RUNTIME_CHECKS "+JSON.stringify({"passed":failures.is_empty(),"checks":checks,"failures":failures,"scope":"Headless main/HUD/VFX integration fixtures; not real-input acceptance"}))
 main.queue_free()
 main=null
 warning.clear()
 escape=null
 await process_frame
 await process_frame
 # Audio cleanup runs on a real-time mixer thread even with --fixed-fps.
 var audio_cleanup_deadline:=Time.get_ticks_msec()+250
 while Time.get_ticks_msec()<audio_cleanup_deadline:await process_frame
 quit(0 if failures.is_empty() else 1)
