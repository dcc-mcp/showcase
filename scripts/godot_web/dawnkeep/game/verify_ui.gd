extends SceneTree
## Synthetic UI/action regression; this does not prove real input or pixels.
var failures:Array=[]
var checks:=0
func _initialize():call_deferred("run")
func check(ok:bool,message:String):
 checks+=1
 if not ok:failures.append(message);push_error(message)
func run():
 var hud=load("res://hud.gd").new()
 root.add_child(hud)
 await process_frame
 for dims in [Vector2(1280,720),Vector2(1440,900),Vector2(390,844),Vector2(320,568),Vector2(1024,768),Vector2(844,390)]:
  hud.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
  hud.size=dims
  for lang in ["en","zh"]:
   hud.set_language(lang)
   for mode in ["intro","playing","equipment","build","upgrade","paused","confirm","help","victory","defeat"]:
    hud.intro=mode=="intro";hud.confirming=mode=="confirm";hud.help_open=mode=="help"
    hud.shop="equipment" if mode=="equipment" else ("build" if mode in ["build","upgrade"] else "")
    hud.state={"paused":mode in ["paused","confirm","help"],"mode":mode if mode in ["victory","defeat"] else "build","selected_pad":2,"hero":{"hp":120,"max_hp":240},"boss":{"hp":500,"max_hp":1000}}
    if mode=="upgrade":hud.state.selected_tower={"kind":"sunbow","level":2,"branch":"pierce","refund":133,"upgrades":[{"key":"pierce","cost":110,"available":false},{"key":"volley","cost":110,"available":false}]}
    hud._layout()
    var ui:Dictionary=hud.ui_snapshot()
    for key in ui.controls:
     var c:Dictionary=ui.controls[key]
     check(c.x>=0 and c.y>=0 and c.x+c.w<=dims.x+1 and c.y+c.h<=dims.y+1,"Control outside viewport "+str(dims)+lang+mode+key+str(c))
     var button:Button=hud.controls[key]
     var font:Font=button.get_theme_font("font")
     var font_size:int=button.get_theme_font_size("font_size")
     for line:String in button.text.split("\n"):
      check(font.get_string_size(line,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x<=c.w-10,"Clipped button text "+str(dims)+lang+mode+key+":"+line)
    var keys:Array=ui.controls.keys()
    for i in range(keys.size()):
     for j in range(i+1,keys.size()):
      var a:Rect2=hud.controls[keys[i]].get_rect()
      var b:Rect2=hud.controls[keys[j]].get_rect()
      check(not a.intersects(b),"Overlapping visible inputs "+str(dims)+lang+mode+keys[i]+"/"+keys[j])
    if mode in ["confirm","help"]:
     check(not hud.action_allowed("pause") and not hud.action_allowed("restart") and not hud.action_allowed("help"),"Nested modal and pause are blocked")
     check(hud.action_allowed("cancel"),"Modal cancel stays available")
    if mode in ["victory","defeat"]:check(hud.blocks_world(Vector2(2,2)),"Terminal screen blocks world input")
    check(hud.hero_health_bar.get_parent()==hud.panels.hero_panel and hud.hero_health_bar.value==50.0,"Hero health bar is visible child layer and has actual ratio")
    check(hud.boss_health_bar.get_parent()==hud.panels.boss_panel and hud.boss_health_bar.value==50.0,"Boss health bar is visible child layer and has actual ratio")
 hud.state={"mode":"build","paused":false};hud.intro=false;hud.confirming=false;hud.help_open=false;hud.shop="";hud._layout()
 hud._set_direction("right",Vector2.RIGHT,true)
 check(not hud._finger_directions.is_empty(),"Touch hold registers")
 hud.confirming=true;hud._layout()
 check(hud._finger_directions.is_empty(),"Opening modal cancels held touch movement")
 print("DAWNKEEP_UI_CHECKS "+JSON.stringify({"passed":failures.is_empty(),"checks":checks,"failures":failures,"scope":"Synthetic layouts/actions; six viewports, EN/ZH, ten screen modes; not real-input or visual acceptance"}))
 quit(0 if failures.is_empty() else 1)
