extends SceneTree
## Headless story/UI/state regression. Direct calls and fixture positions are
## integration tests, not trusted browser gestures, rendered UI, or audio proof.
var game: Node3D
var failures:Array[String]=[]
var checks:=0
var had_save:=false
var original_save:=""
const SAVE_PATH="user://tidal-sanctuary-v2.json"

func _initialize() -> void:run.call_deferred()
func check(value:bool,label:String) -> void:
 checks+=1
 if not value:failures.append(label);push_error(label)

func open_game() -> void:
 game=load("res://start.tscn").instantiate();root.add_child(game)
 game.set_physics_process(false);game.set_process(false)
 await process_frame

func place(index:int) -> void:
 var target:Vector3=game.beacon.position if index==3 else game.lantern_points[index]
 game.player.position=target+Vector3(1.35,0,0)
 game.player.velocity=Vector3.ZERO
 if index==2:game.player.position.y=game.swim.floating_height()
 game.game_time+=4.0
 await physics_frame
 game.update_prompt()

func all_text(value:Variant) -> String:
 if value is String:return value
 var result:=""
 if value is Dictionary:
  for child in value.values():result+=all_text(child)
 elif value is Array:
  for child in value:result+=all_text(child)
 return result

func check_layout_cache() -> void:
 var interface:CanvasLayer=game.interface
 root.size=Vector2i(1280,720)
 for i in range(4):
  await process_frame;interface.layout()
 var theme_changes:=[0]
 interface.message.theme_changed.connect(func():theme_changes[0]+=1)
 var original_action:Rect2=interface.action_button.get_global_rect()
 for i in range(8):
  interface.layout();await process_frame
 check(theme_changes[0]==0,"unchanged layout does not invalidate the message theme each frame")
 check(not interface._layout_dirty,"unchanged layout settles into the cached geometry path")
 check(interface.action_button.get_global_rect()==original_action,"cached layout preserves action geometry")
 interface.prompt.text="";interface.layout()
 check(not interface.prompt_panel.visible,"cached geometry still hides an empty proximity prompt")
 interface.prompt.text="Read the shore chart";interface.layout()
 check(interface.prompt_panel.visible,"cached geometry still reveals a new proximity prompt")
 interface.prompt.text="";interface.layout()
 check(not interface.prompt_panel.visible,"cached geometry hides the prompt again without resize")
 for size in [Vector2i(320,568),Vector2i(390,844),Vector2i(1280,720)]:
  root.size=size;await process_frame;interface.layout()
  var expected_font:=16 if size.x<600 else 14
  check(interface.message.get_theme_font_size("font_size")==expected_font,"resize updates the responsive message font")
  check(interface.action_button.position==Vector2(size.x-216,size.y-(150 if size.x<384 else 92)),"resize invalidates cached action geometry immediately")
  for lang in ["en","zh"]:
   game.language=lang;game.update_state()
   interface.show_card("journal",game.tr_text(game.story.title),game.tr_text(game.story.opening.body),game.tr_text(game.story.ui.continue),game.tr_text(game.story.ending.secondary))
   for i in range(4):
    await process_frame;interface.layout()
   check(interface.language_button.text==("EN" if lang=="en" else "ZH"),"same-viewport status change updates language")
   check(interface.card_secondary.visible,"same-viewport story change reveals secondary control")
   var expanded:Rect2=interface.card.get_global_rect()
   check(expanded.end.x<=size.x+.1 and expanded.end.y<=size.y+.1,"localized card reflow stays inside the unchanged viewport")
   interface.show_card("opening",game.tr_text(game.story.title),"Short body" if lang=="en" else "简短内容",game.tr_text(game.story.ui.continue))
   for i in range(4):
    await process_frame;interface.layout()
   check(not interface.card_secondary.visible,"same-viewport story change removes secondary control")
   check(interface.card_body.text==("Short body" if lang=="en" else "简短内容"),"same-viewport card content is refreshed")
   interface.hide_card();interface.layout()
   check(not interface.card.visible and not interface.shade.visible,"cached layout preserves card hide and shade removal")
 # A deferred minimum-size change must invalidate geometry even without a
 # status/card/viewport setter. Removing it must restore the authored size.
 interface.title.custom_minimum_size=Vector2(380,24)
 await process_frame;await process_frame
 check(interface._layout_dirty,"deferred text minimum-size change marks layout dirty")
 interface.layout()
 check(interface.title.size.x>=380,"dirty layout respects a new minimum size")
 interface.title.custom_minimum_size=Vector2.ZERO
 for i in range(4):
  await process_frame;interface.layout()
 check(interface.title.size.x==362,"minimum-size shrink restores authored title width without resize")
 var stable_changes:int=theme_changes[0]
 for i in range(8):
  interface.layout();await process_frame
 check(theme_changes[0]==stable_changes,"settled content reflow returns to a theme-stable cached layout")
 check(not interface._layout_dirty,"content minimum-size reflow settles back into the cached geometry path")

func run() -> void:
 had_save=FileAccess.file_exists(SAVE_PATH)
 if had_save:original_save=FileAccess.get_file_as_string(SAVE_PATH)
 await open_game()
 game.reset_game()
 game.audio_muted=false;game.tide_audio.set_muted(false,"fixture_initial")
 check(not game.journey_started,"fresh scene waits for Begin")
 check(not game.tide_audio.get_state().started,"fresh scene never starts music")
 await place(0)
 game.interact();check(game.quest_stage()==0,"opening blocks world interaction")
 game.show_opening()
 check(game.interface.card_body.text.ends_with(game.control_help(DisplayServer.is_touchscreen_available())),"opening instructions match the actual input capability")
 for lang in ["en","zh"]:
  game.language=lang
  check(game.control_help(true)==str(game.story.ui.controls_touch[lang]),"touch controls are localized")
  check(game.control_help(false)==str(game.story.ui.controls_keyboard[lang]),"keyboard controls are localized")
  check(game.control_help(true)!=game.control_help(false),"touch help never substitutes keyboard-only instructions")
 game.language="en"
 # The shared CJK font renders curly English apostrophes at full width.
 # Keep the shipped English title compact without changing Chinese punctuation.
 check(str(game.story.title.en)=="The Tidekeeper's Promise","English title uses compact Latin punctuation")
 game.interface.set_status(0,"en",false)
 check(game.interface.journal_button.tooltip_text=="Tidekeeper's journal","English journal tooltip uses compact Latin punctuation")
 game.begin_journey("fixture")
 check(game.journey_started and game.interface.card_mode.is_empty(),"explicit Begin opens player control")
 check(game.tide_audio.get_state().start_count==1,"one logical music start")
 game.interface.card_primary.disabled=true # Model a delayed Web Begin's shared button state.
 game.show_journal()
 check(not game.interface.card_primary.disabled,"journal re-enables the shared action after delayed Begin")
 game.request_restart()
 check(not game.interface.card_primary.disabled,"restart confirmation has its own enabled action")
 game.card_secondary()
 game.begin_journey("fixture_repeat")
 check(game.tide_audio.get_state().start_count==1,"repeated Begin does not restart music")
 await place(2)
 check(game.interaction_status().reason=="missing_key","reef cache explains the brass lock")
 await place(3)
 check(game.interaction_status().reason=="missing_pearl","beacon explains its missing pearl")
 await place(0)
 game.interact();check(game.quest_stage()==1,"chart advances once")
 game.game_time+=4.0;game.update_prompt()
 check(game.interaction_status().reason=="already_read","visited chart has its own state")
 check(game.prompt.text==game.tr_text(game.story.ui.already_read),"visited chart does not claim next target is nearby")
 var before:Dictionary=game.tide_audio.get_state()
 game.interact();check(game.quest_stage()==1,"visited chart cannot advance next objective")
 check(game.tide_audio.get_state().cue_counts==before.cue_counts,"visited interaction has no duplicate cue")
 await place(1)
 game.interact();check(game.quest_stage()==2,"grove grants key once")
 game.game_time+=4.0;game.update_prompt()
 check(game.interaction_status().reason=="already_open","opened grove chest is explicitly empty")
 check(game.prompt.text==game.tr_text(game.story.ui.already_open),"empty chest uses its own message")
 check(not game.lanterns[1].get_node("Gem").visible,"collected key marker disappears")
 check(game.chest_lids[0].rotation.x<-.5,"opened lid stays visibly open")
 check(game.action_button.disabled,"visited chest cannot show an active pickup action")
 game.hint_text="Previous-language feedback";game.tip_until=game.game_time+3.0
 game.change_language("fixture");await process_frame
 check(game.prompt.text==game.tr_text(game.story.ui.already_open),"language toggle clears stale prior-language toast")
 game.show_journal()
 check(game.interface.card_mode=="journal" and game.interface.card_body.text.contains(game.tr_text(game.story.stages[0].story_body)),"journal retains readable chart story")
 check(game.interface.card_body.text.contains(game.tr_text(game.story.stages[1].story_body)),"journal retains key clue without timed reading")
 game.card_secondary()
 check(game.restart_pending and game.interface.card_mode=="restart","journal secondary exposes touch-accessible restart confirmation")
 check(game.quest_stage()==2,"journal restart request preserves progress")
 game.card_secondary()
 game.toggle_audio("fixture")
 check(game.audio_muted and game.tide_audio.get_state().muted,"sound toggle shares runtime mute state")
 game.save_game()
 game.queue_free();await process_frame
 await open_game()
 check(game.loaded_found and game.audio_muted,"fresh scene restores the saved sound preference")
 check(not game.journey_started and not game.tide_audio.get_state().started,"restore remains silent until its own Begin")
 check(game.quest_stage()==2,"story reload retains exact quest stage")
 game.begin_journey("fixture")
 game.request_restart();check(game.restart_pending and game.quest_stage()==2,"restart request is non-destructive")
 game.card_secondary();check(not game.restart_pending and game.quest_stage()==2,"restart cancellation preserves progress")
 game.request_restart();game.card_primary();check(game.quest_stage()==0,"explicit confirmation resets progress")
 await check_layout_cache()
 var font_text:=all_text(game.story)
 var missing:Array[int]=[]
 for index in range(font_text.length()):
  var cp:=font_text.unicode_at(index)
  if cp>32 and not game.game_font.has_char(cp) and cp not in missing:missing.append(cp)
 check(missing.is_empty(),"all localized story text has glyph coverage")
 for size in [Vector2i(1280,720),Vector2i(390,844),Vector2i(320,568),Vector2i(360,800),Vector2i(375,667)]:
  root.size=size;await process_frame;game.interface.layout()
  var web_save_rect:=Rect2(16,size.y-82,148,50)
  check(not game.action_button.get_global_rect().intersects(web_save_rect),"game action avoids external Web save control")
  for control in [game.action_button,game.language_button,game.interface.audio_button,game.interface.journal_button]:
   var rect:Rect2=control.get_global_rect()
   check(rect.position.x>=0 and rect.position.y>=0 and rect.end.x<=size.x+.1 and rect.end.y<=size.y+.1,"touch control fits viewport %s"%size)
   check(rect.size.x>=44 and rect.size.y>=44,"touch target is at least 44px")
  for marker in game.interface.milestone_icons+game.interface.milestone_checks:
   var marker_rect:Rect2=marker.get_global_rect()
   check(marker_rect.position.x>=0 and marker_rect.end.x<=size.x+.1,"milestone row fits viewport %s"%size)
  game.show_journal();await process_frame;game.interface.layout()
  var card_rect:Rect2=game.interface.card.get_global_rect()
  check(card_rect.position.x>=0 and card_rect.position.y>=0 and card_rect.end.x<=size.x+.1 and card_rect.end.y<=size.y+.1,"story card fits viewport %s"%size)
  check(not game.interface.card_primary.get_global_rect().intersects(web_save_rect),"story primary avoids external Web save control")
  check(not game.interface.card_secondary.get_global_rect().intersects(web_save_rect),"story secondary avoids external Web save control")
  game.card_primary()
 game.queue_free();await process_frame
 # Fixed-fps fixtures advance simulated timers faster than the audio mixing thread.
 OS.delay_msec(200)
 await process_frame
 if had_save:
  var file:=FileAccess.open(SAVE_PATH,FileAccess.WRITE);file.store_string(original_save);file.close()
 elif FileAccess.file_exists(SAVE_PATH):DirAccess.remove_absolute(ProjectSettings.globalize_path(SAVE_PATH))
 print("TIDAL_STORY_CHECK ",JSON.stringify({"schema":1,"passed":failures.is_empty(),"checks":checks,"failures":failures,"route":"headless direct-call, fixture-position and layout integration; no rendered, trusted-input or audio-output claim"}))
 quit(0 if failures.is_empty() else 1)
