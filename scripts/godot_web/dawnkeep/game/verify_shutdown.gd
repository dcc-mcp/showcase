extends SceneTree
## Real process shutdown through the production desktop/Web close notification.
var main:Node
var checks:=0
var failures:Array[String]=[]
var playback_refs:Array[WeakRef]=[]
var finished_count:=0
var mode:="active"
var close_started_msec:=0

func _initialize() -> void:call_deferred("run")

func check(value:bool,message:String) -> void:
 checks+=1
 if not value:failures.append(message);push_error(message)

func run() -> void:
 for argument in OS.get_cmdline_user_args():
  if argument in ["--shutdown-active","--shutdown-locked","--shutdown-paused"]:mode=argument.trim_prefix("--shutdown-")
 root.size=Vector2i(1280,800)
 main=load("res://main.gd").new()
 root.add_child(main)
 await process_frame
 check(not auto_accept_quit,"Production owns the desktop/Web close request")
 if mode!="locked":
  main._command("unlock",null)
  main._play_sound("wave_started")
  if mode=="paused":main._pause_music(true)
 var players:Array[AudioStreamPlayer]=main.sound_players.duplicate()
 players.append(main.calm);players.append(main.battle)
 for player in players:
  if player.has_stream_playback():playback_refs.append(weakref(player.get_stream_playback()))
 check(playback_refs.is_empty() if mode=="locked" else playback_refs.size()>=3,"Fixture covers the requested audio playback state")
 main.shutdown_finished.connect(_finished)
 # Rapid repeated close requests must share one cleanup and one final exit.
 close_started_msec=Time.get_ticks_msec()
 main.notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)
 main.notification(Node.NOTIFICATION_WM_CLOSE_REQUEST)

func _finished(success:bool) -> void:
 finished_count+=1
 check(success,"Production waits for the audio mixer to release playback references")
 check(finished_count==1,"Repeated close request completes exactly once")
 check(main._quitting and main.process_mode==Node.PROCESS_MODE_DISABLED,"Shutdown prevents new game input or playback")
 check(not main.game.can_process(),"Always-processing simulation stops before physics bodies are disabled")
 check(main.calm.stream==null and main.battle.stream==null,"Both music stream references are released")
 check(main.sound_bank.is_empty(),"Synthesized sound resources are released")
 for player in main.sound_players:
  check(player.stream==null and not player.playing,"Effect player stops and releases its stream")
 for playback in playback_refs:
  check(playback.get_ref()==null,"AudioServer no longer retains a playback")
 print("DAWNKEEP_SHUTDOWN_CHECKS "+JSON.stringify({"passed":failures.is_empty(),"checks":checks,"failures":failures,"mode":mode,"drain_elapsed_ms":Time.get_ticks_msec()-close_started_msec,"playbacks":playback_refs.size(),"scope":"Actual headless process exit through production close notification; not OS-input or Web acceptance"}))
