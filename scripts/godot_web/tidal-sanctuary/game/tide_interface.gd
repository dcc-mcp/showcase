extends CanvasLayer
## Original responsive story interface. World input remains owned by the game.
signal action_requested
signal language_requested
signal audio_requested
signal journal_requested
signal card_primary_requested
signal card_secondary_requested
signal card_changed

var root: Control
var title_panel: Panel
var prompt_panel: Panel
var footer_panel: Panel
var title: Label
var objective: Label
var progress: Label
var subtitle: Label
var compass: Label
var prompt: Label
var message: Label
var action_button: Button
var language_button: Button
var audio_button: Button
var journal_button: Button
var milestone_icons: Array[TextureRect] = []
var milestone_checks: Array[Label] = []
var shade: ColorRect
var card: PanelContainer
var card_title: Label
var card_body: RichTextLabel
var card_primary: Button
var card_secondary: Button
var card_mode := ""
var font: Font
var ui_language := "en"
var current_stage := 0
var muted := false
var _layout_viewport := Vector2(-1,-1)
var _layout_dirty := true

func panel_style(color: Color, border := false) -> StyleBoxFlat:
 var style := StyleBoxFlat.new()
 style.bg_color = color
 style.set_corner_radius_all(12)
 if border:
  style.border_color = Color("d9bd7b")
  style.set_border_width_all(1)
 return style

func label(size: int, color := Color("fff1ce")) -> Label:
 var value := Label.new()
 value.add_theme_font_override("font",font)
 value.add_theme_font_size_override("font_size",size)
 value.add_theme_color_override("font_color",color)
 value.mouse_filter = Control.MOUSE_FILTER_IGNORE
 return value

func button(text_value: String, size := 16) -> Button:
 var value := Button.new()
 value.text = text_value
 value.add_theme_font_override("font",font)
 value.add_theme_font_size_override("font_size",size)
 value.add_theme_color_override("font_color",Color("fff1ce"))
 value.add_theme_color_override("font_disabled_color",Color("aac8bf"))
 value.add_theme_stylebox_override("normal",panel_style(Color("173c43"),true))
 value.add_theme_stylebox_override("hover",panel_style(Color("23525a"),true))
 value.add_theme_stylebox_override("pressed",panel_style(Color("0e252b"),true))
 value.add_theme_stylebox_override("disabled",panel_style(Color(.06,.14,.16,.82)))
 var focus := StyleBoxFlat.new()
 focus.bg_color = Color(0,0,0,0)
 focus.border_color = Color("fff1ce")
 focus.set_border_width_all(2)
 focus.set_corner_radius_all(12)
 value.add_theme_stylebox_override("focus",focus)
 value.custom_minimum_size = Vector2(44,44)
 return value

func setup(game_font: Font) -> void:
 font = game_font
 root = Control.new()
 root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 root.mouse_filter = Control.MOUSE_FILTER_IGNORE
 add_child(root)
 title_panel = Panel.new();title_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
 title_panel.add_theme_stylebox_override("panel",panel_style(Color(.04,.13,.15,.94)))
 root.add_child(title_panel)
 title=label(13,Color("aac8bf"));root.add_child(title)
 objective=label(20);objective.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;root.add_child(objective)
 subtitle=label(16,Color("c5d9d1"));subtitle.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;root.add_child(subtitle)
 progress=label(14,Color("d9bd7b"));root.add_child(progress)
 for name in ["chart","key","pearl","beacon"]:
  var icon:=TextureRect.new();icon.texture=load("res://assets/story/%s.svg"%name)
  icon.expand_mode=TextureRect.EXPAND_IGNORE_SIZE;icon.stretch_mode=TextureRect.STRETCH_KEEP_ASPECT_CENTERED
  icon.mouse_filter=Control.MOUSE_FILTER_IGNORE;root.add_child(icon);milestone_icons.append(icon)
  var check:=label(14,Color("fff1ce"));root.add_child(check);milestone_checks.append(check)
 compass=label(16,Color("fff1ce"));compass.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;root.add_child(compass)
 prompt_panel=Panel.new();prompt_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
 prompt_panel.add_theme_stylebox_override("panel",panel_style(Color(.04,.13,.15,.94)))
 root.add_child(prompt_panel)
 prompt=label(16);prompt.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER;prompt.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
 prompt.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;root.add_child(prompt)
 footer_panel=Panel.new();footer_panel.mouse_filter=Control.MOUSE_FILTER_IGNORE
 footer_panel.add_theme_stylebox_override("panel",panel_style(Color(.04,.13,.15,.82)));root.add_child(footer_panel)
 message=label(14,Color("c5d9d1"));root.add_child(message)
 action_button=button("");action_button.pressed.connect(func():action_requested.emit());root.add_child(action_button)
 language_button=button("EN",14);language_button.pressed.connect(func():language_requested.emit());root.add_child(language_button)
 audio_button=button("");audio_button.expand_icon=true;audio_button.icon_alignment=HORIZONTAL_ALIGNMENT_CENTER
 audio_button.pressed.connect(func():audio_requested.emit());root.add_child(audio_button)
 journal_button=button("");journal_button.icon=load("res://assets/story/chart.svg");journal_button.expand_icon=true
 journal_button.icon_alignment=HORIZONTAL_ALIGNMENT_CENTER;journal_button.pressed.connect(func():journal_requested.emit());root.add_child(journal_button)
 shade=ColorRect.new();shade.color=Color(.015,.045,.055,.72)
 shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT);shade.mouse_filter=Control.MOUSE_FILTER_STOP;root.add_child(shade)
 card=PanelContainer.new();card.add_theme_stylebox_override("panel",panel_style(Color("102b31"),true));root.add_child(card)
 var margin:=MarginContainer.new()
 for side in ["left","right","top","bottom"]:margin.add_theme_constant_override("margin_"+side,24)
 card.add_child(margin)
 var column:=VBoxContainer.new();column.add_theme_constant_override("separation",16);margin.add_child(column)
 card_title=label(24);card_title.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART;column.add_child(card_title)
 card_body=RichTextLabel.new();card_body.bbcode_enabled=false;card_body.scroll_active=true
 card_body.add_theme_font_override("normal_font",font);card_body.add_theme_font_size_override("normal_font_size",18)
 card_body.add_theme_color_override("default_color",Color("d2e2d9"));card_body.size_flags_vertical=Control.SIZE_EXPAND_FILL
 column.add_child(card_body)
 card_primary=button("");card_primary.pressed.connect(func():card_primary_requested.emit());column.add_child(card_primary)
 card_secondary=button("");card_secondary.pressed.connect(func():card_secondary_requested.emit());column.add_child(card_secondary)
 # Text and Container minimum sizes can settle after their setters return.
 # Reapply the fixed geometry then, including at an unchanged viewport size.
 for control in root.get_children():
  if control is Control:control.minimum_size_changed.connect(_mark_layout_dirty)
 hide_card()
 layout()

func _mark_layout_dirty() -> void:
 _layout_dirty=true

func show_card(mode: String, heading: String, body: String, primary: String, secondary := "") -> void:
 card_changed.emit()
 _mark_layout_dirty()
 # Opening may temporarily disable Begin while Web audio is preparing.
 # Every later journal/restart card owns a fresh enabled action state.
 card_primary.disabled=false;card_secondary.disabled=false
 card_mode=mode;card_title.text=heading;card_body.text=body;card_body.scroll_to_line(0)
 card_primary.text=primary;card_secondary.text=secondary;card_secondary.visible=not secondary.is_empty()
 shade.show();card.show();card_primary.grab_focus();layout()

func hide_card() -> void:
 card_changed.emit()
 _mark_layout_dirty()
 card_mode="";shade.hide();card.hide()
 if get_viewport():get_viewport().gui_release_focus()

func set_status(stage: int, language: String, audio_muted: bool) -> void:
 _mark_layout_dirty()
 current_stage=stage;ui_language=language;muted=audio_muted
 language_button.text="EN" if language=="en" else "ZH"
 audio_button.icon=load("res://assets/story/audio-%s.svg"%["off" if muted else "on"])
 audio_button.tooltip_text=("Sound off" if muted else "Sound on") if language=="en" else ("声音已关闭" if muted else "声音已开启")
 journal_button.tooltip_text="Tidekeeper's journal" if language=="en" else "守潮手记"
 for i in range(4):
  milestone_icons[i].modulate=Color.WHITE if stage>i else Color(.55,.68,.65,.8)
  milestone_checks[i].text="●" if stage>i else "○"
 layout()

func layout() -> void:
 if root==null:return
 # Prompt text changes with real proximity even when geometry is cached.
 prompt_panel.visible=not prompt.text.is_empty()
 var viewport:=get_viewport().get_visible_rect().size
 if not _layout_dirty and viewport==_layout_viewport:return
 _layout_dirty=false;_layout_viewport=viewport
 var narrow:=viewport.x<600
 var panel_width:=minf(390,viewport.x-32)
 title_panel.position=Vector2(16,16);title_panel.size=Vector2(panel_width,190 if narrow else 174)
 title.position=Vector2(30,28)
 title.size=Vector2(panel_width-160,24) if narrow else Vector2(panel_width-28,24)
 objective.position=Vector2(30,70 if narrow else 58);objective.size=Vector2(panel_width-28,50)
 subtitle.position=Vector2(30,121 if narrow else 107);subtitle.size=Vector2(panel_width-28,48)
 progress.position=Vector2(30,174 if narrow else 143);progress.size=Vector2(42,24)
 var milestone_spacing:=minf(62,(panel_width-80)/4)
 for i in range(4):
  milestone_icons[i].position=Vector2(92+i*milestone_spacing,170 if narrow else 140);milestone_icons[i].size=Vector2(26,26)
  milestone_checks[i].position=Vector2(122+i*milestone_spacing,175 if narrow else 145)
 language_button.position=Vector2(viewport.x-60,20);language_button.size=Vector2(44,44)
 audio_button.position=Vector2(viewport.x-110,20);audio_button.size=Vector2(44,44)
 journal_button.position=Vector2(viewport.x-160,20);journal_button.size=Vector2(44,44)
 compass.position=Vector2(viewport.x*.5-140,214 if narrow else 22);compass.size=Vector2(280,32)
 var compact:=viewport.x<384
 action_button.position=Vector2(viewport.x-216,viewport.y-(150 if compact else 92));action_button.size=Vector2(200,54)
 var prompt_width:=minf(530,viewport.x-32)
 prompt_panel.position=Vector2((viewport.x-prompt_width)*.5,viewport.y-(228 if compact else 170))
 prompt_panel.size=Vector2(prompt_width,64)
 prompt.position=prompt_panel.position+Vector2(14,8);prompt.size=prompt_panel.size-Vector2(28,16)
 footer_panel.position=Vector2(16,viewport.y-30);footer_panel.size=Vector2(minf(570,viewport.x-32),26)
 message.position=Vector2(26,viewport.y-27);message.size=footer_panel.size-Vector2(20,0)
 var message_font_size:=16 if narrow else 14
 # Godot emits theme-change notifications even for an identical override.
 if message.get_theme_font_size("font_size")!=message_font_size:
  message.add_theme_font_size_override("font_size",message_font_size)
 var card_width:=minf(550,viewport.x-32)
 var card_height:=minf(470,viewport.y-140)
 card.position=Vector2((viewport.x-card_width)*.5,(viewport.y-92-card_height)*.5)
 card.size=Vector2(card_width,card_height)
 card_body.custom_minimum_size=Vector2(card_width-48,120 if viewport.y<600 else 160)
