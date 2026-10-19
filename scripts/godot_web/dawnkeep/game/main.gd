extends Node3D
## Native Godot scene/input/audio adapter. Diagnostics are strictly read-only.
signal shutdown_finished(success: bool)
const Gameplay = preload("res://gameplay.gd")
const Visuals = preload("res://visuals.gd")
const HUD = preload("res://hud.gd")
var game: Node
var art: Node3D
var hud: Control
var camera: Camera3D
var language := "zh"
var audio_unlocked := false
var muted := false
var music_bus := -1
var sfx_bus := -1
var calm: AudioStreamPlayer
var battle: AudioStreamPlayer
var sound_players: Array[AudioStreamPlayer] = []
var sound_bank: Dictionary = {}
var sound_index := 0
var touch_move := Vector2.ZERO
var report_timer := 0.0
var report_id := 0
var frame_ready := false
var camera_target := Vector3.ZERO
var _snapshot: Dictionary = {}
var _music_battle := false
var _last_phase := ""
var _modal_was_paused := false
var _modal_open := false
var _last_selected := -2
var _last_occupied := false
var _last_boss_present := false
var _marker: Node3D
var _quitting := false

func _ready() -> void:
 name="Dawnkeep"
 get_tree().auto_accept_quit=false
 _configure_inputs()
 _configure_lighting()
 game=Gameplay.new()
 game.name="DefenseSimulation"
 add_child(game)
 art=Visuals.new()
 art.name="EmeraldPassArt"
 add_child(art)
 var layer:=CanvasLayer.new()
 add_child(layer)
 hud=HUD.new()
 hud.name="DawnkeepInterface"
 layer.add_child(hud)
 hud.command.connect(_command)
 hud.move_pressed.connect(func(value:Vector2):touch_move=value)
 game.state_changed.connect(_on_state)
 game.game_event.connect(_on_game_event)
 game.finished.connect(func(_won:bool):hud._layout())
 art.setup(game)
 game.setup(self,art,hud)
 _configure_audio()
 hud.set_language(language)
 get_viewport().size_changed.connect(_resize)
 _resize()
 if DisplayServer.get_name() != "headless":
  RenderingServer.frame_post_draw.connect(_on_frame_post_draw,CONNECT_ONE_SHOT)
 else:
  print("DAWNKEEP_HEADLESS_READY {\"schema\":1,\"rendered\":false}")

func _notification(what:int) -> void:
 if what==NOTIFICATION_WM_CLOSE_REQUEST and is_inside_tree():_quit_cleanly()

func _quit_cleanly() -> void:
 if _quitting:return
 _quitting=true
 # Simulation intentionally runs in PROCESS_MODE_ALWAYS during normal play.
 if is_instance_valid(game):game.process_mode=Node.PROCESS_MODE_DISABLED
 process_mode=Node.PROCESS_MODE_DISABLED
 # AudioServer releases stopped playback references on its next mixer updates,
 # not synchronously in stop() or when the player leaves the scene tree.
 var pending:Array[WeakRef]=[]
 var players:Array[AudioStreamPlayer]=sound_players.duplicate()
 if is_instance_valid(calm):players.append(calm)
 if is_instance_valid(battle):players.append(battle)
 for player in players:
  if player.has_stream_playback():pending.append(weakref(player.get_stream_playback()))
  player.stop()
  player.stream=null
 sound_bank.clear()
 var started:=Time.get_ticks_msec()
 var remaining:=pending.size()
 while Time.get_ticks_msec()-started<2000:
  remaining=0
  for playback in pending:
   if playback.get_ref()!=null:remaining+=1
  if remaining==0:break
  await get_tree().process_frame
 var success:=remaining==0
 if not success:push_error("Dawnkeep audio shutdown timed out with %d retained playbacks"%remaining)
 print("DAWNKEEP_SHUTDOWN "+JSON.stringify({"passed":success,"playbacks":pending.size(),"remaining":remaining,"elapsed_ms":Time.get_ticks_msec()-started}))
 shutdown_finished.emit(success)
 get_tree().quit(0 if success else 1)

func _configure_inputs() -> void:
 var bindings := {"move_left":[KEY_A,KEY_LEFT],"move_right":[KEY_D,KEY_RIGHT],"move_up":[KEY_W,KEY_UP],"move_down":[KEY_S,KEY_DOWN]}
 for action:String in bindings:
  if not InputMap.has_action(action):InputMap.add_action(action)
  for key:int in bindings[action]:
   var event:=InputEventKey.new()
   event.physical_keycode=key
   InputMap.action_add_event(action,event)

func _configure_lighting() -> void:
 var sun:=DirectionalLight3D.new()
 sun.name="WarmDawnSun"
 sun.rotation_degrees=Vector3(-55,-38,0)
 sun.light_color=Color("ffe2a8")
 sun.light_energy=1.25
 sun.shadow_enabled=true
 sun.directional_shadow_max_distance=80
 sun.shadow_bias=.04
 sun.shadow_normal_bias=1.1
 add_child(sun)
 var fill:=DirectionalLight3D.new()
 fill.rotation_degrees=Vector3(-25,145,0)
 fill.light_color=Color("72bcd0")
 fill.light_energy=.28
 add_child(fill)
 var env:=WorldEnvironment.new()
 var settings:=Environment.new()
 settings.background_mode=Environment.BG_COLOR
 settings.background_color=Color("122b31")
 settings.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
 settings.ambient_light_color=Color("b3cfcb")
 settings.ambient_light_energy=.62
 settings.tonemap_mode=Environment.TONE_MAPPER_FILMIC
 settings.fog_enabled=true
 settings.fog_light_color=Color("17414a")
 settings.fog_light_energy=.55
 settings.fog_density=.0015
 env.environment=settings
 add_child(env)
 camera=Camera3D.new()
 camera.name="TacticalCamera"
 camera.projection=Camera3D.PROJECTION_ORTHOGONAL
 camera.keep_aspect=Camera3D.KEEP_HEIGHT
 camera.size=34
 camera.near=.1
 camera.far=160
 add_child(camera)
 camera.current=true
 camera.position=Vector3(22,31,34)
 camera.look_at(Vector3(0,0,1))

func _resize() -> void:
 if not is_instance_valid(hud):return
 hud.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 hud._layout()
 if hud.portrait:
  camera.size=24
 else:
  var ratio:=get_viewport().get_visible_rect().size.x/maxf(1,get_viewport().get_visible_rect().size.y)
  camera.size=33 if ratio>=1.5 else 39

func _physics_process(_delta:float) -> void:
 if not is_instance_valid(game) or not is_instance_valid(hud):return
 # Input polling ignores GUI event consumption. Keyboard focus must explicitly
 # suspend movement so arrows navigate native controls without moving Elyra.
 var input:=touch_move
 if not hud.keyboard_navigation_active():
  input+=Input.get_vector("move_left","move_right","move_up","move_down")
 if hud.is_modal_open():input=Vector2.ZERO
 # Screen-relative input follows the fixed camera basis; physics remains world-space.
 var right:=camera.global_basis.x
 var forward:=camera.global_basis.z
 right.y=0;forward.y=0
 right=right.normalized();forward=forward.normalized()
 var direction:Vector3=(right*input.x+forward*input.y).limit_length()
 game.set_move_input(Vector2(direction.x,direction.z))

func _process(delta:float) -> void:
 if not is_instance_valid(game):return
 if hud.portrait and is_instance_valid(game.hero):
  var wanted:Vector3=game.hero.position
  wanted.x=clampf(wanted.x,-9,8)
  wanted.z=clampf(wanted.z,-5,5)
  camera_target=camera_target.lerp(wanted,1-exp(-delta*5))
 else:camera_target=camera_target.lerp(Vector3(0,0,1),1-exp(-delta*5))
 camera.position=camera_target+Vector3(22,31,34)
 camera.look_at(camera_target)
 if is_instance_valid(calm):
  var calm_target:float=-48 if _music_battle else -17
  var battle_target:float=-16 if _music_battle else -48
  calm.volume_db=move_toward(calm.volume_db,calm_target,delta*15)
  battle.volume_db=move_toward(battle.volume_db,battle_target,delta*15)
 report_timer+=delta
 if report_timer>=.25:
  report_timer=0
  _report_state()

func _input(event:InputEvent) -> void:
 # Only global controls precede GUI dispatch. In particular, Space belongs to
 # a focused native Button before it can become the next-wave world shortcut.
 if event is InputEventKey and event.pressed and not event.echo:
  var code:int=event.physical_keycode if event.physical_keycode!=0 else event.keycode
  if code not in [KEY_L,KEY_M,KEY_ESCAPE]:return
  if hud.intro and code not in [KEY_L,KEY_M]:return
  if code==KEY_L:_command("language",null)
  elif code==KEY_M:_command("mute",null)
  elif code==KEY_ESCAPE:
   if hud.confirming or hud.help_open: hud._activate("cancel",null)
   elif hud.shop!="":hud.shop="";hud._layout()
   elif not hud.is_modal_open() and hud.keyboard_navigation_active():hud.leave_keyboard_navigation()
   elif not hud.intro:_command("pause",null)
  get_viewport().set_input_as_handled()

func _unhandled_key_input(event:InputEvent) -> void:
 if not event is InputEventKey or not event.pressed or event.echo:return
 if event.ctrl_pressed or event.alt_pressed or event.meta_pressed:return
 if hud.is_modal_open() or hud.keyboard_navigation_active():return
 var code:int=event.physical_keycode if event.physical_keycode!=0 else event.keycode
 match code:
  KEY_BACKSPACE:hud._activate("restart",null)
  KEY_Q:_command("skill","q")
  KEY_E:_command("skill","e")
  KEY_R:_command("skill","r")
  KEY_SPACE:_command("start_wave",null)
  _:return
 get_viewport().set_input_as_handled()

func _unhandled_input(event:InputEvent) -> void:
 if event is InputEventMouseButton and event.pressed and event.button_index in [MOUSE_BUTTON_LEFT,MOUSE_BUTTON_RIGHT]:
  if hud.blocks_world(event.position):return
  _unlock_audio()
  if hud.minimap_rect.has_point(event.position):
   game.set_move_target(hud.minimap_world(event.position))
   return
  var point:=_world_point(event.position)
  if point==Vector3.INF:return
  if event.button_index==MOUSE_BUTTON_LEFT:
   var best:=-1
   var best_dist:=1.45
   for i in range(Gameplay.PADS.size()):
    var d:float=Vector2(point.x,point.z).distance_to(Vector2(Gameplay.PADS[i].x,Gameplay.PADS[i].z))
    if d<best_dist:best_dist=d;best=i
   if best>=0:
    game.select_pad(best)
    hud.open_build()
    return
  game.set_move_target(point)

func _world_point(screen:Vector2) -> Vector3:
 var origin:=camera.project_ray_origin(screen)
 var normal:=camera.project_ray_normal(screen)
 var t:float=-origin.y/normal.y
 if t<=0:return Vector3.INF
 var point:=origin+normal*t
 point.y=0
 point.x=clampf(point.x,-16,15)
 point.z=clampf(point.z,-10,10)
 return point

func _command(action:String,value:Variant) -> void:
 _unlock_audio()
 match action:
  "unlock":pass
  "modal_open":
   if _modal_open:return
   _modal_open=true
   _modal_was_paused=bool(game.paused)
   if not _modal_was_paused:game.toggle_pause();_pause_music(true)
  "modal_close":
   if not _modal_open:return
   _modal_open=false
   if not _modal_was_paused and game.paused:game.toggle_pause();_pause_music(false)
  "language":
   language="en" if language=="zh" else "zh"
   hud.set_language(language)
  "mute":
   muted=not muted
   AudioServer.set_bus_mute(0,muted)
   hud.muted=muted
   hud._refresh()
  "pause":
   if hud.intro or hud.confirming or hud.help_open:return
   game.toggle_pause()
   _pause_music(bool(game.paused))
   hud._layout()
  "speed":game.set_speed(2 if game.speed==1 else 1)
  "restart":
   _modal_open=false
   hud.clear_announcement()
   game.restart()
   _pause_music(false)
   touch_move=Vector2.ZERO
   hud._layout()
  "start_wave":game.start_wave()
  "skill":game.cast_skill(str(value))
  "item":game.buy_item(str(value))
  "tower":game.build_tower(str(value));hud._layout()
  "upgrade":
   var selected:Dictionary=game.snapshot().get("selected",{})
   var upgrades:Array=selected.get("upgrades",[])
   var index:=0 if value=="a" else 1
   if upgrades.size()>index:game.upgrade_tower(str(upgrades[index].key))
   hud._layout()
  "sell":game.sell_tower();hud._layout()
 _play_sound("click")

func _on_state(value:Dictionary) -> void:
 _snapshot=value.duplicate(true)
 _snapshot["core_hp"]=value.get("core_hp",value.get("nexus_hp",20))
 var selected:Dictionary=value.get("selected",{})
 _snapshot["selected_tower"]=selected if selected.get("occupied",false) else {}
 hud.set_state(_snapshot)
 _music_battle=str(value.get("phase","build"))=="wave"
 var occupied:=bool(selected.get("occupied",false))
 var selection:=int(value.get("selected_pad",-1))
 var boss_present:bool=not value.get("boss",{}).is_empty()
 if _last_selected!=selection or _last_occupied!=occupied or _last_phase!=str(value.get("phase","")) or _last_boss_present!=boss_present:
  _last_selected=selection;_last_occupied=occupied;_last_phase=str(value.get("phase",""))
  _last_boss_present=boss_present
  hud._layout()

func _on_game_event(key:String,data:Dictionary) -> void:
 if key=="level_up":key="hero_level_up"
 if key=="hero_fallen":key="hero_died"
 hud.announce(key,data)
 if key in ["skill_cast","level_up","hero_level_up","wave_started","wave_cleared","victory","defeat","hero_died","tower_built","item_bought"]:_play_sound(key)

func _configure_audio() -> void:
 AudioServer.add_bus()
 music_bus=AudioServer.bus_count-1
 AudioServer.set_bus_name(music_bus,"DawnkeepMusic")
 AudioServer.set_bus_send(music_bus,"Master")
 AudioServer.add_bus()
 sfx_bus=AudioServer.bus_count-1
 AudioServer.set_bus_name(sfx_bus,"DawnkeepEffects")
 AudioServer.set_bus_send(sfx_bus,"Master")
 AudioServer.set_bus_volume_db(0,-4)
 calm=_music_player("res://audio/field-of-dreams.ogg")
 battle=_music_player("res://audio/determined-pursuit.ogg")
 calm.volume_db=-17;battle.volume_db=-48
 for i in range(8):
  var player:=AudioStreamPlayer.new()
  player.bus="DawnkeepEffects"
  player.playback_type=AudioServer.PLAYBACK_TYPE_STREAM
  player.volume_db=-17
  add_child(player)
  sound_players.append(player)
 for key in ["click","skill_cast","level_up","hero_level_up","wave_started","wave_cleared","victory","defeat","hero_died","tower_built","item_bought"]:
  sound_bank[key]=_synth_sound(key)

func _music_player(path:String) -> AudioStreamPlayer:
 var player:=AudioStreamPlayer.new()
 player.bus="DawnkeepMusic"
 player.playback_type=AudioServer.PLAYBACK_TYPE_STREAM
 var stream:AudioStream=load(path)
 if stream is AudioStreamOggVorbis:
  stream=stream.duplicate()
  stream.loop=true
 player.stream=stream
 add_child(player)
 return player

func _unlock_audio() -> void:
 if audio_unlocked:return
 audio_unlocked=true
 if is_instance_valid(calm):calm.play();battle.play()

func _pause_music(paused:bool) -> void:
 if not is_instance_valid(calm):return
 calm.stream_paused=paused
 battle.stream_paused=paused

func _synth_sound(key:String) -> AudioStreamWAV:
 # Original deterministic feedback: short shaped chords, not borrowed game audio.
 var length:=.17 if key=="click" else .65
 var rate:=22050
 var count:=int(length*rate)
 var data:=PackedByteArray()
 data.resize(count*2)
 var notes: Array[float]=[523.25,659.25,783.99]
 if key in ["defeat","hero_died"]:notes=[196.0,233.08,293.66]
 elif key=="wave_started":notes=[146.83,220.0,293.66]
 elif key=="skill_cast":notes=[392.0,587.33,783.99]
 elif key=="click":notes=[740.0]
 for i in range(count):
  var time:float=float(i)/rate
  var env:float=minf(1,time/.012)*pow(maxf(0,1-time/length),2)
  var sample:=0.0
  for j in range(notes.size()):
   var delayed:float=maxf(0,time-j*.045)
   if time>=j*.045:sample+=sin(TAU*notes[j]*delayed)*.27/notes.size()
  var value:int=int(clampf(sample*env,-1,1)*32767)
  data.encode_s16(i*2,value)
 var stream:=AudioStreamWAV.new()
 stream.format=AudioStreamWAV.FORMAT_16_BITS
 stream.mix_rate=rate
 stream.stereo=false
 stream.data=data
 return stream

func _play_sound(key:String) -> void:
 if not audio_unlocked or muted or sound_players.is_empty() or not sound_bank.has(key):return
 var player:AudioStreamPlayer=sound_players[sound_index%sound_players.size()]
 sound_index+=1
 player.stream=sound_bank[key]
 player.play()

func _on_frame_post_draw() -> void:
 frame_ready=true
 print("DAWNKEEP_FRAME_READY {\"schema\":1}")

func _report_state() -> void:
 var report:Dictionary=game.snapshot()
 report_id+=1
 report["schema"]=1
 report["sample_id"]=report_id
 report["physics_frame"]=Engine.get_physics_frames()
 report["language"]=language
 report["core_hp"]=report.get("core_hp",report.get("nexus_hp",20))
 report["rendered"]=frame_ready
 for entity:Dictionary in report.get("enemies",[]):entity.position=_position_array(entity.position)
 for entity:Dictionary in report.get("towers",[]):entity.position=_position_array(entity.position)
 var hero_state:Dictionary=report.get("hero",{})
 var hero_pos:=_as_vector(hero_state.get("position",{}))
 hero_state["position"]=[hero_pos.x,hero_pos.y,hero_pos.z]
 var projection:=camera.unproject_position(hero_pos+Vector3.UP)
 hero_state["screen"]={"x":projection.x,"y":projection.y}
 var ui:Dictionary=hud.ui_snapshot()
 var pads:Array=[]
 for i in range(Gameplay.PADS.size()):
  var p:Vector2=camera.unproject_position(Gameplay.PADS[i])
  pads.append({"id":i,"x":p.x,"y":p.y})
 ui["pads"]=pads
 report["ui"]=ui
 var peak:float=-100
 if music_bus>=0:
  peak=maxf(AudioServer.get_bus_peak_volume_left_db(music_bus,0),AudioServer.get_bus_peak_volume_right_db(music_bus,0))
  if not is_finite(peak):peak=-100
 report["music"]={"unlocked":audio_unlocked,"muted":muted,"playing":audio_unlocked and not muted and is_instance_valid(calm) and calm.playing and not calm.stream_paused,"peak_db":peak,"track":"determined-pursuit" if _music_battle else "field-of-dreams"}
 print("DAWNKEEP_STATE "+JSON.stringify(report))

func _position_array(value:Variant) -> Array:
 var v:=_as_vector(value)
 return [v.x,v.y,v.z]

func _as_vector(value:Variant) -> Vector3:
 if value is Vector3:return value
 if value is Dictionary:return Vector3(float(value.get("x",0)),float(value.get("y",0)),float(value.get("z",0)))
 if value is Array and value.size()>=3:return Vector3(float(value[0]),float(value[1]),float(value[2]))
 return Vector3.ZERO
