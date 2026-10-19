extends SceneTree
## Isolated integration fixtures, never a real-input acceptance claim.
var failures:Array=[]
var checks:=0
var layout_settle_max_frames:=0
var synthetic_input_events:=0
var pointer_hold_max_frames:=0
func _initialize():call_deferred("run")
func check(ok:bool,message:String):
 checks+=1
 if not ok:failures.append(message);push_error(message)

func settle_ui() -> void:
 # Nested Container sorting and focus restoration can require several frames.
 # Require three equal snapshots, with a bounded timeout rather than assuming
 # one deferred callback or a fixed frame count establishes settled geometry.
 var previous:Dictionary={}
 var stable_frames:=0
 for frame in range(16):
  await process_frame
  var current:Dictionary={}
  for node:Node in root.find_children("*","Control",true,false):
   var control:=node as Control
   current[str(control.get_path())]=[control.is_visible_in_tree(),control.get_global_rect()]
  var focused:Control=root.gui_get_focus_owner()
  current["focus_owner"]=str(focused.get_path()) if is_instance_valid(focused) else ""
  stable_frames=stable_frames+1 if current==previous else 0
  previous=current
  if stable_frames>=2:
   layout_settle_max_frames=maxi(layout_settle_max_frames,frame+1)
   return
 check(false,"Native UI geometry/focus did not settle within 16 frames")

func key_event(code:int,pressed:bool,shift:bool=false,control:bool=false) -> void:
 var event:=InputEventKey.new()
 event.keycode=code
 event.physical_keycode=code
 event.pressed=pressed
 event.shift_pressed=shift
 event.ctrl_pressed=control
 root.push_input(event,true)
 synthetic_input_events+=1

func tap_key(code:int,shift:bool=false,control:bool=false) -> void:
 key_event(code,true,shift,control)
 await process_frame
 key_event(code,false,shift,control)
 await settle_ui()

func click_control(button:Control,hold_frames:int=3) -> void:
 var point:=button.get_global_rect().get_center()
 var visible_rect:=root.get_visible_rect().intersection(button.get_global_rect())
 var ancestor:Node=button.get_parent()
 while ancestor!=null:
  if ancestor is Control and ancestor.clip_contents:visible_rect=visible_rect.intersection(ancestor.get_global_rect())
  ancestor=ancestor.get_parent()
 check(button.is_visible_in_tree() and visible_rect.has_point(point),"Pointer target center is visible inside viewport and clip ancestors: "+str(button.name))
 var activations:Array[int]=[0]
 var record_activation:=func():activations[0]+=1
 if button is BaseButton:button.pressed.connect(record_activation)
 var motion:=InputEventMouseMotion.new()
 motion.position=point;motion.global_position=point
 root.push_input(motion,true)
 synthetic_input_events+=1
 if button is BaseButton:check(button.is_hovered(),"Synthetic pointer motion reaches native button: "+str(button.name))
 for pressed:bool in [true,false]:
  var event:=InputEventMouseButton.new()
  event.position=point;event.global_position=point
  event.button_index=MOUSE_BUTTON_LEFT;event.pressed=pressed
  root.push_input(event,true)
  synthetic_input_events+=1
  if pressed:
   # One process_frame can resume before deferred focus cleanup. Cross several
   # idle frames so a real held click cannot be masked by an immediate pair.
   for frame in range(hold_frames):await process_frame
   pointer_hold_max_frames=maxi(pointer_hold_max_frames,hold_frames)
   if button is BaseButton and not button.disabled:
    check(button.is_pressed(),"Native button retains held pointer press across idle frames: "+str(button.name))
    if button.action_mode==BaseButton.ACTION_MODE_BUTTON_RELEASE:
     check(activations[0]==0,"Native release-mode button does not activate before pointer release: "+str(button.name))
  else:await process_frame
 await settle_ui()
 if button is BaseButton:
  check(activations[0]==1,"Native pointer click emits exactly one activation: "+str(button.name))
  button.pressed.disconnect(record_activation)

func verify_pointer_holds(main:Node) -> void:
 var original_size:Vector2i=root.size
 main._command("restart",null)
 main.hud.shop="";main.hud.intro=false;main.hud.confirming=false;main.hud.help_open=false
 main.hud.leave_keyboard_navigation()
 root.size=Vector2i(842,388)
 main._resize()
 await settle_ui()
 check(main.hud.portrait and main.hud.controls.equipment.is_visible_in_tree(),"Held-pointer fixture uses observed compact native viewport")
 await click_control(main.hud.controls.equipment,18)
 check(main.hud.shop=="equipment" and main.game.gold==420,"Held Equipment pointer click opens shop exactly once without a purchase")
 if main.hud.shop=="equipment":
  var boots:Button=main.hud.controls.item_boots
  main.hud.groups.shop_scroll.ensure_control_visible(boots)
  await settle_ui()
  for purchase in range(2):
   var before:Dictionary=main.game.snapshot()
   var cost:int=0
   for item:Dictionary in before.shop:
    if item.key=="boots":cost=int(item.cost)
   await click_control(boots,18)
   var after:Dictionary=main.game.snapshot()
   check(after.hero.equipment.boots==before.hero.equipment.boots+1 and after.gold==before.gold-cost,"Held Boots pointer click purchases exactly once: "+str(purchase))
   check(main.hud.shop=="equipment" and main.game.wave==0,"Held shop purchase preserves panel and does not trigger world action")
  check(not main.hud.keyboard_navigation_active() and root.gui_get_focus_owner()==null,"Completed pointer purchase releases incidental keyboard focus")
  await click_control(main.hud.controls.close,18)
  check(main.hud.shop=="","Held Close pointer click closes shop")
 var was_muted:bool=main.muted
 await click_control(main.hud.controls.mute,18)
 check(main.muted!=was_muted,"Held ordinary pointer button activates on release")
 check(not main.hud.keyboard_navigation_active() and root.gui_get_focus_owner()==null,"Held ordinary pointer button does not trap gameplay keyboard focus")
 root.size=original_size
 main._resize()
 await settle_ui()

func focus_is_one_of(hud:Control,keys:Array) -> bool:
 var focused:Control=root.gui_get_focus_owner()
 if not is_instance_valid(focused) or not focused.is_visible_in_tree():return false
 if focused is BaseButton and focused.disabled:return false
 for key:String in keys:
  if focused==hud.controls[key]:return true
 return false

func verify_keyboard_navigation(main:Node) -> void:
 # These synthetic events exercise the native GUI dispatch order, not OS input.
 main.set_physics_process(false)
 main.hud.intro=true
 main.hud._layout()
 await settle_ui()
 check(main.hud.is_modal_open() and main.hud.keyboard_navigation_active(),"Intro owns keyboard focus")
 main.hud.controls.start.grab_focus()
 await tap_key(KEY_SPACE)
 check(not main.hud.intro and main.game.wave==0,"Focused Start receives Space before the world wave shortcut")
 check(not main.hud.keyboard_navigation_active() and root.gui_get_focus_owner()==null,"Starting from an unfocused intro returns keyboard ownership to gameplay")
 await tap_key(KEY_SPACE)
 check(main.game.wave==1,"Keyboard-only Start then Space reaches world wave action without a pointer click")
 main.game.restart()
 main.hud._layout()
 await settle_ui()
 await tap_key(KEY_ESCAPE)
 check(main.game.paused,"Escape from unfocused gameplay opens pause")
 main.hud.controls.resume.grab_focus()
 await tap_key(KEY_SPACE)
 await tap_key(KEY_Q)
 check(not main.game.paused and not main.hud.keyboard_navigation_active() and main.game.skill_cooldowns.q>0.0,"Keyboard-only Resume returns to world Q without a prior focused control or pointer click")
 main.game.restart()
 main.hud._layout()
 await settle_ui()

 await click_control(main.hud.controls.mute)
 check(not main.hud.keyboard_navigation_active() and root.gui_get_focus_owner()==null,"Ordinary pointer button releases residual keyboard focus")
 Input.action_press("move_right")
 main._physics_process(0.0)
 check(main.game._move_input.length()>0.9,"Arrow polling moves hero after an ordinary pointer button")
 Input.action_release("move_right")
 main._physics_process(0.0)
 await tap_key(KEY_SPACE)
 check(main.game.wave==1,"Unfocused world Space still starts a wave")
 main.game.hero_level=3
 for key:int in [KEY_Q,KEY_E,KEY_R]:await tap_key(key)
 check(main.game.skill_cooldowns.q>0.0 and main.game.skill_cooldowns.e>0.0 and main.game.skill_cooldowns.r>0.0,"Unfocused Q/E/R shortcuts retain their gameplay actions")

 await tap_key(KEY_TAB)
 var first:Control=root.gui_get_focus_owner()
 check(main.hud.keyboard_navigation_active() and is_instance_valid(first),"Tab enters native keyboard navigation")
 await tap_key(KEY_TAB)
 var second:Control=root.gui_get_focus_owner()
 check(is_instance_valid(second) and second!=first,"Tab advances focus to another enabled native control")
 await tap_key(KEY_TAB,true)
 check(root.gui_get_focus_owner()==first,"Shift+Tab reverses the native focus traversal")
 await tap_key(KEY_RIGHT)
 Input.action_press("move_right")
 check(Input.get_vector("move_left","move_right","move_up","move_down").x>0.9,"Arrow polling fixture remains pressed despite GUI event handling")
 main._physics_process(0.0)
 check(main.game._move_input==Vector2.ZERO,"GUI arrow navigation cannot leak through global movement polling")
 Input.action_release("move_right")
 main.game.skill_cooldowns.q=0.0
 await tap_key(KEY_Q)
 check(main.game.skill_cooldowns.q==0.0,"Keyboard UI navigation does not cast world skills")

 # Open the shop using a focused native Button, then buy twice using Space.
 main.hud.controls.equipment.grab_focus()
 await tap_key(KEY_SPACE)
 check(main.hud.shop=="equipment" and main.hud.keyboard_navigation_active(),"Keyboard-opened shop retains UI keyboard navigation")
 var shop_keys:Array=["language","mute","close","item_blade","item_plate","item_focus","item_boots","item_potion"]
 for i in range(shop_keys.size()*2):
  await tap_key(KEY_TAB,i>=shop_keys.size())
  check(focus_is_one_of(main.hud,shop_keys),"Shop Tab/Shift+Tab stays on its active native controls")
 for purchase in range(2):
  var before:Dictionary=main.game.snapshot()
  var cost:int=0
  for item:Dictionary in before.shop:
   if item.key=="blade":cost=int(item.cost)
  main.hud.controls.item_blade.grab_focus()
  await tap_key(KEY_SPACE)
  var after:Dictionary=main.game.snapshot()
  check(after.gold==before.gold-cost and after.hero.equipment.blade==before.hero.equipment.blade+1,"Focused native equipment Space purchases exactly once: "+str(purchase))
  check(main.hud.shop=="equipment" and main.game.wave==1,"Equipment activation neither closes shop nor calls a world wave")
 await tap_key(KEY_ESCAPE)
 check(main.hud.shop=="" and not main.game.paused,"Global Escape closes the shop before pausing")
 check(root.gui_get_focus_owner()==main.hud.controls.equipment and main.hud.keyboard_navigation_active(),"Closing keyboard shop restores equipment focus")
 await tap_key(KEY_ESCAPE)
 check(not main.hud.keyboard_navigation_active() and root.gui_get_focus_owner()==null and not main.game.paused,"Escape leaves nonmodal UI keyboard navigation without pausing")
 await tap_key(KEY_Q)
 check(main.game.skill_cooldowns.q>0.0,"Leaving UI navigation restores gameplay shortcuts without pointer input")

 await tap_key(KEY_ESCAPE)
 check(main.game.paused and main.hud.is_modal_open(),"Next Escape from gameplay opens native pause modal")
 var pause_keys:Array=["language","mute","resume","restart"]
 for i in range(8):
  await tap_key(KEY_TAB,i>=4)
  check(focus_is_one_of(main.hud,pause_keys),"Pause Tab/Shift+Tab stays on active modal controls")
 var old_language:String=main.language
 await tap_key(KEY_L)
 check(main.language!=old_language and main.game.paused,"Global L still changes language inside a focused modal")
 await tap_key(KEY_L)
 var old_muted:bool=main.muted
 await tap_key(KEY_M)
 check(main.muted!=old_muted and main.game.paused,"Global M still changes sound inside a focused modal")
 await tap_key(KEY_M)
 main.hud.controls.resume.grab_focus()
 await tap_key(KEY_SPACE)
 check(not main.game.paused and main.game.wave==1,"Focused Resume receives Space without advancing the wave")

 await click_control(main.hud.controls.mute)
 await tap_key(KEY_BACKSPACE)
 check(main.hud.confirming and main.game.paused,"Unhandled world Backspace opens restart confirmation")
 for i in range(8):
  await tap_key(KEY_TAB,i>=4)
  check(focus_is_one_of(main.hud,["language","mute","confirm_restart","cancel"]),"Restart Tab/Shift+Tab cannot reach background controls")
 main.hud.controls.cancel.grab_focus()
 await tap_key(KEY_SPACE)
 check(not main.hud.confirming and not main.game.paused and main.game.wave==1,"Focused Cancel receives Space without starting a wave")
 await click_control(main.hud.controls.mute)
 await tap_key(KEY_BACKSPACE)
 main.hud.controls.confirm_restart.grab_focus()
 await tap_key(KEY_ENTER)
 check(not main.hud.confirming and not main.game.paused and main.game.wave==0 and main.game.gold==420,"Native Enter confirms restart and clears gameplay state")

 await click_control(main.hud.controls.mute)
 await tap_key(KEY_Q,false,true)
 check(main.game.skill_cooldowns.q==0.0,"Modified application shortcuts do not cast world skills")
 await tap_key(KEY_Q)
 check(main.game.skill_cooldowns.q>0.0,"Pointer return from modal restores world skill shortcuts")
 main.hud._activate("help",null)
 main.touch_move=Vector2.RIGHT
 main._physics_process(0.0)
 check(main.game._move_input==Vector2.ZERO,"Open modal gates touch movement as well as keyboard polling")
 main.touch_move=Vector2.ZERO
 await tap_key(KEY_ESCAPE)
 check(not main.hud.help_open and not main.game.paused,"Global Escape cancels help and restores the active game")
 first=null;second=null

func run():
 # SceneTree --script starts headless with a 64x64 root, independently of the
 # project window defaults. Pointer hit testing must use the intended viewport.
 root.size=Vector2i(1280,800)
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
 await verify_keyboard_navigation(main)
 await verify_pointer_holds(main)
 print("DAWNKEEP_RUNTIME_CHECKS "+JSON.stringify({"passed":failures.is_empty(),"checks":checks,"failures":failures,"layout_settle_max_frames":layout_settle_max_frames,"synthetic_input_events":synthetic_input_events,"pointer_hold_max_frames":pointer_hold_max_frames,"scope":"Headless main/HUD/VFX integration and synthetic native GUI dispatch/focus fixtures including held pointer clicks; not OS real-input acceptance"}))
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
