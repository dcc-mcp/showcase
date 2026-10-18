extends SceneTree
func _initialize():call_deferred("run")
func run():
 var hud=load("res://hud.gd").new()
 root.add_child(hud)
 await process_frame
 for dims in [Vector2(1280,720),Vector2(390,844),Vector2(320,568),Vector2(1024,768)]:
  hud.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
  hud.size=dims
  hud._layout()
  for intro in [true,false]:
   hud.intro=intro;hud._layout()
   var ui=hud.ui_snapshot()
   for key in ui.controls:
    var c=ui.controls[key]
    assert(c.x>=0 and c.y>=0 and c.x+c.w<=dims.x+1 and c.y+c.h<=dims.y+1,"Control outside viewport "+str(dims)+key+str(c))
 print("DAWNKEEP_UI_BOUNDS pass 4 viewports x intro/gameplay; synthetic layout, not input")
 quit()
