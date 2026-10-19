extends SceneTree
## Synthetic UI/action regression; this does not prove real input or pixels.
var failures:Array=[]
var checks:=0
var settle_max_frames:=0
var settle_histogram:Dictionary={}
var focus_samples:Array=[]
func _initialize():call_deferred("run")
func check(ok:bool,message:String):
 checks+=1
 if not ok:failures.append(message);push_error(message)

func focus_key(hud:Control) -> String:
 var owner:Control=root.gui_get_focus_owner()
 for key:String in hud.controls:
  if owner==hud.controls[key]:return key
 return "" if owner==null else str(owner.get_path())

func settle_layout(hud:Control,context:String) -> bool:
 var previous:Dictionary={}
 var equal_samples:=0
 for frame in range(16):
  await process_frame
  var current:Dictionary={}
  for node:Node in hud.find_children("*","Control",true,false):
   var control:=node as Control
   current[str(control.get_path())]=[control.visible,control.is_visible_in_tree(),control.get_global_rect(),control.get_combined_minimum_size()]
  current["focus_owner"]=focus_key(hud)
  equal_samples=equal_samples+1 if current==previous else 0
  previous=current
  if equal_samples>=2:
   settle_max_frames=maxi(settle_max_frames,frame+1)
   settle_histogram[str(frame+1)]=int(settle_histogram.get(str(frame+1),0))+1
   return true
 check(false,"UI geometry/focus did not produce three equal samples within 16 frames: "+context)
 return false

func observed_visible_rect(control:Control) -> Rect2:
 if not control.is_visible_in_tree():return Rect2()
 var result:=control.get_global_rect()
 var ancestor:Node=control.get_parent()
 while ancestor is Control:
  if ancestor.clip_contents:result=result.intersection(ancestor.get_global_rect())
  ancestor=ancestor.get_parent()
 return result

func verify_native_geometry(hud:Control,ui:Dictionary,dims:Vector2,context:String) -> void:
 for key:String in hud.controls:
  var button:Button=hud.controls[key]
  check(button.get_parent() is Container,"Native Container owns button "+context+key)
  var expected:=observed_visible_rect(button)
  check(ui.controls.has(key)==expected.has_area(),"Snapshot respects tree visibility and clipped area "+context+key)
  if expected.has_area() and ui.controls.has(key):
   var c:Dictionary=ui.controls[key]
   var actual:=Rect2(c.x,c.y,c.w,c.h)
   check(actual.is_equal_approx(expected),"Snapshot uses common-space clipped button bounds "+context+key)
 for key:String in hud.labels:
  var label:Label=hud.labels[key]
  check(label.get_parent() is Container,"Native Container owns label "+context+key)
  var visible_rect:=observed_visible_rect(label)
  if not visible_rect.has_area():continue
  check(Rect2(Vector2.ZERO,dims).grow(1.0).encloses(visible_rect),"Visible label bounds outside viewport "+context+key+str(visible_rect))
  if label.autowrap_mode==TextServer.AUTOWRAP_OFF:
   var font:Font=label.get_theme_font("font")
   var font_size:int=label.get_theme_font_size("font_size")
   for line:String in label.text.split("\n"):
    check(font.get_string_size(line,HORIZONTAL_ALIGNMENT_LEFT,-1,font_size).x<=label.size.x+1.0,"Nonwrapped label text exceeds native allocation "+context+key+":"+line)
   check(label.get_line_count()*label.get_line_height()<=label.size.y+1.0,"Nonwrapped label height exceeds native allocation "+context+key)
 for bar:ProgressBar in [hud.hero_health_bar,hud.boss_health_bar]:
  if not bar.is_visible_in_tree():continue
  var panel:Control=hud.panels.hero_panel if bar==hud.hero_health_bar else hud.panels.boss_panel
  check(panel.get_global_rect().grow(1.0).encloses(bar.get_global_rect()),"Visible health bar stays within its native panel "+context)
 var owner:Control=root.gui_get_focus_owner()
 if is_instance_valid(owner):
  check(owner.is_visible_in_tree() and owner.focus_mode!=Control.FOCUS_NONE,"Focus owner remains a visible keyboard control "+context)
  if owner is BaseButton:check(not owner.disabled,"Focus owner is enabled "+context)
 if hud.is_modal_open():check(is_instance_valid(owner),"Open modal has a native keyboard focus owner "+context)
 if ui.has("focus_owner"):check(str(ui.focus_owner)==focus_key(hud),"Observer focus owner matches native viewport "+context)
 focus_samples.append({"state":context,"focus_owner":focus_key(hud),"keyboard_navigation":hud.keyboard_navigation_active()})

func verify_scroll_snapshot(hud:Control) -> void:
 hud.size=Vector2(320,568)
 hud.intro=false;hud.confirming=false;hud.help_open=false;hud.shop="equipment"
 hud.state={"mode":"build","paused":false,"hero":{"hp":120,"max_hp":240}}
 var blade:Button=hud.controls.item_blade
 var original_minimum:Vector2=blade.custom_minimum_size
 # Deliberately oversized fixture guarantees clipping without depending on a
 # particular language's text height or on an assumed scrollbar range.
 blade.custom_minimum_size.y=400
 hud._layout()
 await settle_layout(hud,"forced shop scroll")
 var scroll:ScrollContainer=hud.groups.shop_scroll
 check(scroll is ScrollContainer and scroll.clip_contents,"Shop uses native clipping ScrollContainer")
 scroll.scroll_vertical=0
 await settle_layout(hud,"shop scroll top")
 var top:Dictionary=hud.ui_snapshot()
 check(blade.visible and blade.is_visible_in_tree(),"Partially clipped row retains native tree visibility")
 check(top.controls.has("item_blade") and float(top.controls.item_blade.h)<blade.size.y,"Snapshot trims partially clipped input to ScrollContainer viewport")
 check(hud.controls.item_potion.is_visible_in_tree() and not top.controls.has("item_potion"),"Snapshot omits fully clipped tree-visible input")
 check(hud.controls.item_potion.text not in top.labels,"Snapshot text omits fully clipped shop row")
 check(not hud.blocks_world(Vector2(160,540)),"Offscreen clipped shop rows do not block the battlefield outside the panel")
 scroll.visible=false
 await settle_layout(hud,"hidden scroll ancestor")
 var hidden:Dictionary=hud.ui_snapshot()
 check(blade.visible and not blade.is_visible_in_tree() and not hidden.controls.has("item_blade"),"Locally visible child of hidden ancestor is absent from snapshot")
 scroll.visible=true
 await settle_layout(hud,"restored scroll ancestor")
 scroll.scroll_vertical=int(scroll.get_v_scroll_bar().max_value)
 await settle_layout(hud,"shop scroll bottom")
 var bottom:Dictionary=hud.ui_snapshot()
 check(bottom.controls.has("item_potion") and hud.controls.item_potion.text in bottom.labels,"Scrolled-into-view row returns to input and text snapshots")
 if bottom.controls.has("item_potion"):
  var c:Dictionary=bottom.controls.item_potion
  check(Rect2(c.x,c.y,c.w,c.h).is_equal_approx(observed_visible_rect(hud.controls.item_potion)),"Scrolled row snapshot remains in correct global coordinates")
 blade.custom_minimum_size=original_minimum
 scroll.scroll_vertical=0
 hud.shop="";hud._layout()
 await settle_layout(hud,"scroll fixture cleanup")

func verify_focus_restoration(hud:Control) -> void:
 hud.intro=false;hud.confirming=false;hud.help_open=false;hud.shop=""
 hud.state={"mode":"build","paused":false,"hero":{"hp":120,"max_hp":240}}
 hud._layout()
 var pointer:=InputEventMouseButton.new()
 pointer.button_index=MOUSE_BUTTON_LEFT;pointer.pressed=true
 hud._input(pointer)
 pointer.pressed=false
 hud._input(pointer)
 await settle_layout(hud,"focus fixture reset")
 var tab:=InputEventKey.new()
 tab.keycode=KEY_TAB;tab.physical_keycode=KEY_TAB;tab.pressed=true
 hud._input(tab)
 await settle_layout(hud,"keyboard focus entry")
 hud.controls.equipment.grab_focus()
 hud._activate("shop","equipment")
 await settle_layout(hud,"keyboard shop entry")
 check(hud.keyboard_navigation_active() and root.gui_get_focus_owner()!=null,"Keyboard-opened shop has native focus")
 hud._activate("close_shop",null)
 await settle_layout(hud,"keyboard shop return")
 check(root.gui_get_focus_owner()==hud.controls.equipment and hud.keyboard_navigation_active(),"Closing keyboard shop restores its valid initiating control")
 hud._activate("shop","equipment")
 await settle_layout(hud,"disabled focus fixture entry")
 hud.controls.item_blade.grab_focus()
 var state:Dictionary=hud.state.duplicate(true)
 state.shop=[{"key":"blade","available":false,"cost":110,"count":3,"max_count":3}]
 hud.set_state(state)
 await settle_layout(hud,"disabled focus repair")
 var owner:Control=root.gui_get_focus_owner()
 check(is_instance_valid(owner) and owner!=hud.controls.item_blade and owner.is_visible_in_tree(),"Disabling focused purchase repairs focus without changing UI scope")
 hud._activate("close_shop",null)
 await settle_layout(hud,"focus fixture cleanup")

func verify_bundled_glyphs() -> void:
 # System fallback can hide an incomplete subset on desktop but not in Web.
 var font:FontFile=load("res://ui/dawnkeep-sans.otf").duplicate()
 font.allow_system_fallback=false
 var supported:String=font.get_supported_chars()
 var required:Dictionary={}
 var hud_script=load("res://hud.gd")
 for translations:Array in hud_script.WORDS.values():
  for value:String in translations:
   for character:String in value:
    if not character.strip_edges().is_empty():required[character]=true
 for character:String in "▲▼◀▶♪×0123456789":required[character]=true
 for character:String in required:
  check(supported.contains(character),"Bundled font missing UI glyph U+%04X: %s"%[character.unicode_at(0),character])

func run():
 verify_bundled_glyphs()
 var hud=load("res://hud.gd").new()
 root.add_child(hud)
 await process_frame
 for key:String in hud.panels:check(hud.panels[key] is PanelContainer,"Native PanelContainer owns panel "+key)
 for dims in [Vector2(1280,720),Vector2(1280,800),Vector2(1440,900),Vector2(390,844),Vector2(320,568),Vector2(1024,768),Vector2(844,390),Vector2(2560,1080)]:
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
    var context:String=str(dims)+lang+mode
    await settle_layout(hud,context)
    var ui:Dictionary=hud.ui_snapshot()
    verify_native_geometry(hud,ui,dims,context)
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
      var a:Rect2=hud._visible_rect(hud.controls[keys[i]])
      var b:Rect2=hud._visible_rect(hud.controls[keys[j]])
      check(not a.intersects(b),"Overlapping visible inputs "+str(dims)+lang+mode+keys[i]+"/"+keys[j])
    if mode in ["confirm","help"]:
     check(not hud.action_allowed("pause") and not hud.action_allowed("restart") and not hud.action_allowed("help"),"Nested modal and pause are blocked")
     check(hud.action_allowed("cancel"),"Modal cancel stays available")
    if mode in ["victory","defeat"]:check(hud.blocks_world(Vector2(2,2)),"Terminal screen blocks world input")
    check(hud.panels.hero_panel.is_ancestor_of(hud.hero_health_bar) and hud.hero_health_bar.value==50.0,"Hero health bar is visible child layer and has actual ratio")
    check(hud.panels.boss_panel.is_ancestor_of(hud.boss_health_bar) and hud.boss_health_bar.value==50.0,"Boss health bar is visible child layer and has actual ratio")
   # Measure the displayed dynamic text, not Label.size: a Label can grow to its
   # minimum text width and silently spill beyond the panel into adjacent skills.
   for hero_mode in ["build","wave","paused","victory","defeat"]:
    for hero_case in [{"dead":false,"respawn":0.0},{"dead":true,"respawn":14.0},{"dead":true,"respawn":2.3},{"dead":true,"respawn":0.1}]:
     hud.intro=false;hud.confirming=false;hud.help_open=false;hud.shop=""
     hud.state={"mode":"wave" if hero_mode=="paused" else hero_mode,"paused":hero_mode=="paused","hero":hero_case}
     hud._layout()
     await settle_layout(hud,str(dims)+lang+hero_mode+str(hero_case))
     var hero_title:Label=hud.labels.hero
     var hero_panel:PanelContainer=hud.panels.hero_panel
     var available_width:float=hero_panel.get_global_rect().end.x-hero_title.get_global_rect().position.x-12.0
     var context:String=str(dims)+lang+hero_mode+str(hero_case)
     check(hero_title.is_visible_in_tree() and hero_panel.is_visible_in_tree(),"Dynamic hero title is visible "+context)
     check(hero_title.size.x<=available_width+1 and hero_title.get_line_count()*hero_title.get_line_height()<=hero_title.size.y+1,"Dynamic hero title spills outside its panel "+context+":"+hero_title.text)
     var expected_title:String=hud.text("hero")
     if hero_case.dead:
      expected_title="%s · %s"%[hud.text("hero_name"),hud.text("fallen")] if hero_mode in ["victory","defeat"] else "%s · %s %.1fs"%[hud.text("hero_name"),hud.text("respawn"),hero_case.respawn]
     check(hero_title.text==expected_title,"Hero title preserves healthy name, live countdown, and terminal fallen state "+context)
 await verify_scroll_snapshot(hud)
 await verify_focus_restoration(hud)
 hud.state={"mode":"build","paused":false};hud.intro=false;hud.confirming=false;hud.help_open=false;hud.shop="";hud._layout()
 hud._set_direction("right",Vector2.RIGHT,true)
 check(not hud._finger_directions.is_empty(),"Touch hold registers")
 hud.confirming=true;hud._layout()
 check(hud._finger_directions.is_empty(),"Opening modal cancels held touch movement")
 print("DAWNKEEP_UI_CHECKS "+JSON.stringify({"passed":failures.is_empty(),"checks":checks,"failures":failures,"layout_settle_max_frames":settle_max_frames,"layout_settle_histogram":settle_histogram,"focus_samples":focus_samples,"scope":"Synthetic settled native hierarchy/layout, clipping, font widths and focus snapshots; eight viewports, EN/ZH, ten screen modes plus dynamic hero titles; not real-input or visual acceptance"}))
 quit(0 if failures.is_empty() else 1)
