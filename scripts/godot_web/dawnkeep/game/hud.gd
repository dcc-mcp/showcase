extends Control
## Native responsive UI: anchored regions, Container-owned content, one shared Theme.
signal command(action: String, value: Variant)
signal move_pressed(direction: Vector2)

const INK = Color("0d2027")
const GOLD = Color("c9ad6b")
const CREAM = Color("f4edda")
const TEAL = Color("64d8c2")
const MUTED = Color("9eb5b7")
const WORDS = {
 "title":["DAWNKEEP", "曙光守誓"],
 "subtitle":["OATH OF THE LAST LIGHT", "守住最后一道光"],
 "chapter":["I  /  THE EMERALD PASS", "第一章  /  翡翠隘口"],
 "core":["DAWNHEART", "曙光之心"], "gold":["GOLD", "金币"], "wave":["WAVE", "波次"],
 "hero":["ELYRA · DAWNWARDEN", "艾莉拉 · 曙光守护者"], "hero_name":["ELYRA", "艾莉拉"], "fallen":["FALLEN", "已陨落"], "level":["LV", "等级"],
 "start":["ENTER THE PASS", "进入隘口"],
 "goal":["Stand against the Hollow Court. Protect the Dawnheart through eight waves and defeat the Crownless King.", "抵御空壳王庭的侵袭。守住曙光之心，撑过八波敌潮，击败无冕之王。"],
 "short_goal":["Protect the Dawnheart through eight waves. Defeat the Crownless King.", "守住曙光之心，撑过八波敌潮，击败无冕之王。"],
 "intro_tip":["Move to intercept enemies. Your hero attacks nearby foes automatically. Spend gold on equipment, then place supporting towers.", "主动迎击敌人，英雄会自动攻击近处目标。用金币强化装备，再建造防御塔协助守护。"],
 "controls":["WASD / arrows: move   ·   Click ground: move   ·   Q E R: skills   ·   Space: next wave\nTab: navigate UI · Esc: return / pause", "WASD / 方向键移动 · 点击地面移动 · Q E R 技能 · 空格开始下一波\nTab 切换界面焦点 · Esc 返回战场 / 暂停"],
 "touch_controls":["Tap the ground to move. Use the direction pad and skill buttons. Tap a gold platform to build.", "点击地面移动，也可使用方向键与技能按钮。点击金色基座建造防御塔。"],
 "next_wave":["CALL NEXT WAVE", "迎战下一波"], "in_wave":["DEFEND THE DAWNHEART", "守住曙光之心"],
 "prepare":["Prepare your defense", "整备防线"], "equipment":["EQUIPMENT", "装备"], "towers":["DEFENSES", "防御"],
 "pause":["PAUSE", "暂停"], "resume":["RESUME", "继续"], "restart":["RESET", "重开"],
 "reset_question":["Start a new defense? Your current run will be lost.", "重新开始守护？本局进度将被重置。"],
 "confirm":["START AGAIN", "重新开始"], "cancel":["CANCEL", "取消"],
 "paused":["THE PASS WAITS", "隘口静候"], "paused_tip":["Take a breath. Your defense is paused.", "稍作休息。战斗已暂停。"],
 "victory":["THE LIGHT ENDURES", "曙光永存"], "defeat":["THE DAWNHEART FALLS", "曙光之心已陨落"],
 "victory_tip":["The Crownless King is broken. Dawn returns to the Emerald Pass.", "无冕之王败落，晨光再次照耀翡翠隘口。"],
 "defeat_tip":["A new oath begins with another attempt. Upgrade your hero and intercept threats before they reach the shrine.", "新的誓言，从再试一次开始。强化英雄，在敌人抵达圣坛前拦住他们。"],
 "q":["DAWNCLEAVE", "曙光斩"], "e":["RALLYING LIGHT", "振奋之光"], "r":["STARFALL", "星落"],
 "q_tip":["Q · Strike nearby enemies", "Q · 重创周围敌人"], "e_tip":["E · Heal and empower allies", "E · 治疗并强化友军"], "r_tip":["R · Devastating area strike", "R · 大范围毁灭打击"],
 "ready":["READY", "就绪"], "locked":["LV 3", "3级解锁"], "respawn":["RETURNING", "重返战场"],
 "shop_tip":["Equipment stays for the whole run. Specialize your warden.", "装备整局生效，打造你的守护者。"],
 "blade":["SUNSTEEL BLADE", "日钢之刃"], "plate":["WARDEN PLATE", "守护重甲"], "focus":["STARGLASS FOCUS", "星璃法器"], "boots":["WINDSTEP BOOTS", "风行战靴"], "potion":["DAWNBLOOM TONIC", "晨花药剂"],
 "blade_tip":["Stronger basic attacks", "强化普通攻击"], "plate_tip":["More health and resilience", "提升生命与生存"], "focus_tip":["Stronger active skills", "强化主动技能"], "boots_tip":["Faster movement", "提升移动速度"], "potion_tip":["Restore hero health", "恢复英雄生命"],
 "sunbow":["SUNBOW", "耀日弩塔"], "ember":["CINDER MORTAR", "余烬迫击炮"], "frost":["FROSTSPIRE", "霜晶塔"], "storm":["STORMBELL", "风暴钟塔"],
 "sunbow_tip":["Fast, focused physical fire", "快速精准的物理攻击"], "ember_tip":["Splash damage against crowds", "范围轰击密集敌群"], "frost_tip":["Slows enemies for your hero", "减速敌人，为英雄争取时间"], "storm_tip":["Lightning arcs through armor", "连锁闪电穿透护甲"],
 "build_tip":["Select a gold platform in the world to place a defense.", "先点击战场上的金色基座，再选择防御塔。"],
 "upgrade":["UPGRADE", "升级"], "sell":["SELL", "出售"], "close":["CLOSE", "关闭"],
 "insufficient":["Not enough gold", "金币不足"], "maxed":["MAXED", "已满级"],
 "branch_a":["PATH I", "分支一"], "branch_b":["PATH II", "分支二"],
 "speed":["SPEED", "速度"], "help":["HOW TO PLAY", "玩法说明"],
 "boss":["THE CROWNLESS KING", "无冕之王"], "enemies":["ENEMIES", "敌人"],
 "saved_tip":["EIGHT WAVES · NO ACCOUNT NEEDED", "八波敌潮 · 无需账号"],
 "music_on":["SOUND ON", "声音开"], "music_off":["SOUND OFF", "声音关"],
 "reward":["REWARD", "奖励"], "selected":["SELECTED DEFENSE", "已选防御塔"],
 "dawn":["Dawn is coming. Hold the line.", "晨光将至，坚守防线。"],
 "none":["No defense selected", "尚未选择防御塔"],
 "buy":["BUY", "购买"], "damage":["ATK", "攻击"], "health":["HEALTH", "生命"],
 "move":["MOVE", "移动"], "wave_cleared":["WAVE CLEARED", "敌潮已清除"],
 "hero_level_up":["LEVEL UP", "英雄升级"], "tower_built":["DEFENSE READY", "防御塔就绪"],
 "item_bought":["EQUIPPED", "已装备"], "skill_cast":["LIGHT ANSWERS", "光芒回应"],
 "hero_died":["Your warden will return. Protect the shrine!", "守护者即将重返战场，保护圣坛！"],
 "wave_started":["THE HOLLOW COURT ADVANCES", "空壳王庭来袭"],
 "invalid_action":["That action is not available yet", "当前尚不能执行此操作"],
 "hero_on_pad":["Move away from this platform before building", "先离开这座基座，再建造防御塔"],
 "not_enough_gold":["Not enough gold", "金币不足"],
 "pierce":["ARMORPIERCER", "穿甲弩"], "volley":["TRIPLE VOLLEY", "三重齐射"],
 "inferno":["BURNING GROUND", "灼热大地"], "siege":["SIEGE CANNON", "攻城重炮"],
 "deepfreeze":["DEEP FREEZE", "极寒禁锢"], "shatter":["SHATTER CRYSTAL", "碎晶爆裂"],
 "conduit":["CHAIN CONDUIT", "连锁导流"], "tempest":["TEMPEST HEART", "风暴之心"],
 "owned":["OWNED", "已购"], "chosen":["CHOSEN", "已选"], "other_path":["OTHER PATH", "另一分支"],
 "health_full":["Your hero is already at full health", "英雄生命已满"],
 "item_maxed":["This equipment is fully upgraded", "这件装备已满级"],
 "invalid_purchase":["Wait for your hero to return before buying", "请等待英雄重返战场后购买"],
 "wave_not_ready":["Defeat more enemies before calling a wave", "击败更多敌人后才能迎战下一波"],
 "cannot_start_wave":["A new wave cannot begin right now", "当前无法开始下一波"],
 "skill_unavailable":["Your hero cannot cast right now", "英雄当前无法施放技能"],
 "skill_cooling":["This skill is still recovering", "技能仍在冷却"],
 "skill_locked":["Starfall unlocks at level three", "星落在三级解锁"],
 "pierce_tip":["28 damage, longer range, pierces armor", "28点伤害，更远射程，穿透护甲"],
 "volley_tip":["Faster attacks hit up to three targets", "更快攻击，最多命中三个目标"],
 "inferno_tip":["Burns enemies and leaves damaging ground", "灼烧敌人，并留下持续伤害区域"],
 "siege_tip":["66 damage, wider blast, longer range", "66点伤害，更广爆炸，更远射程"],
 "deepfreeze_tip":["Stronger slow; every fourth hit stuns", "更强减速，每第四次攻击造成眩晕"],
 "shatter_tip":["Faster fire; targets take 25% more damage", "更快攻击，目标受到的伤害提高25%"],
 "conduit_tip":["Lightning chains through five enemies", "闪电在五个敌人之间弹射"],
 "tempest_tip":["Faster lightning briefly stuns chain targets", "更快闪电，短暂眩晕连锁目标"]
}
var language := "zh"
var state: Dictionary = {}
var controls: Dictionary = {}
var labels: Dictionary = {}
var panels: Dictionary = {}
var portrait := false
var intro := true
var shop := ""
var confirming := false
var help_open := false
var toast_text := ""
var toast_time := 0.0
var muted := false
var _layout_size := Vector2.ZERO
var minimap_rect := Rect2()
var _finger_directions: Dictionary = {}
var hero_health_bar: ProgressBar
var boss_health_bar: ProgressBar
var groups: Dictionary = {}
var _keyboard_navigation := false
var _focus_scope := ""
var _restore_focus: Control
var _stacked := false
var _compact := false
var _shop_content := ""


func text(key: String) -> String:
 var value: Variant = WORDS.get(key, [key.replace("_", " ").to_upper(), key])
 return str(value[1 if language == "zh" else 0])

func _ready() -> void:
 mouse_filter = Control.MOUSE_FILTER_IGNORE
 set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 var theme_new := Theme.new()
 if ResourceLoader.exists("res://ui/dawnkeep-sans.otf"):
  theme_new.default_font = load("res://ui/dawnkeep-sans.otf")
 theme_new.default_font_size = 17
 theme_new.set_constant("separation","BoxContainer",8)
 theme_new.set_constant("h_separation","GridContainer",2)
 theme_new.set_constant("v_separation","GridContainer",2)
 theme_new.set_stylebox("panel","PanelContainer",_style(Color(.035,.08,.10,.94)))
 theme_new.set_type_variation("DawnInline","PanelContainer")
 var inline_style:=StyleBoxEmpty.new()
 theme_new.set_stylebox("panel","DawnInline",inline_style)
 for variation in ["Button","DawnPrimary","DawnCleave","DawnRally","DawnStarfall"]:
  if variation!="Button":theme_new.set_type_variation(variation,"Button")
  var accent:Color={"Button":GOLD,"DawnPrimary":TEAL,"DawnCleave":Color("efd37a"),"DawnRally":Color("69d9a0"),"DawnStarfall":Color("8faaff")}[variation]
  theme_new.set_font_size("font_size",variation,15)
  theme_new.set_color("font_color",variation,CREAM)
  theme_new.set_color("font_hover_color",variation,Color.WHITE)
  theme_new.set_color("font_disabled_color",variation,MUTED.darkened(.3))
  var styles={"normal":_style(Color(.055,.12,.145,.97),accent,7),"hover":_style(Color(.11,.23,.25,.98),accent.lightened(.2),7),"pressed":_style(Color(.16,.28,.26,.98),accent,7),"disabled":_style(Color(.035,.065,.08,.85),MUTED.darkened(.6),7),"focus":_style(Color(0,0,0,0),Color.WHITE,7)}
  for item:String in styles:
   var style:StyleBoxFlat=styles[item]
   style.content_margin_left=5;style.content_margin_right=5
   style.content_margin_top=3;style.content_margin_bottom=3
   theme_new.set_stylebox(item,variation,style)
 theme = theme_new
 _build()
 get_viewport().size_changed.connect(_layout)
 _layout()

func _style(bg: Color, border: Color = GOLD, radius: int = 8) -> StyleBoxFlat:
 var s := StyleBoxFlat.new()
 s.bg_color = bg
 s.border_color = Color(border, .66)
 s.set_border_width_all(1)
 s.set_corner_radius_all(radius)
 s.content_margin_left = 12
 s.content_margin_right = 12
 s.content_margin_top = 8
 s.content_margin_bottom = 8
 return s

func _panel(key: String, _color: Color = Color(.035,.08,.10,.94)) -> PanelContainer:
 var p := PanelContainer.new()
 p.name=key
 p.mouse_filter = Control.MOUSE_FILTER_STOP
 add_child(p)
 panels[key] = p
 return p

func _label(key: String, size_px: int = 18, color: Color = CREAM) -> Label:
 var l := Label.new()
 l.name=key
 l.add_theme_font_size_override("font_size", size_px)
 l.add_theme_color_override("font_color", color)
 l.mouse_filter = Control.MOUSE_FILTER_IGNORE
 l.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 l.text = text(key)
 add_child(l)
 labels[key] = l
 return l

func _button(key: String, action: String, value: Variant = null, color: Color = GOLD) -> Button:
 var b := Button.new()
 b.name=key
 b.text = text(key)
 b.theme_type_variation="DawnPrimary" if color==TEAL else "Button"
 if key.begins_with("skill_"):b.theme_type_variation=["DawnCleave","DawnRally","DawnStarfall"][int(key.right(1))-1]
 b.clip_text=true
 b.custom_minimum_size.y=44
 b.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 b.size_flags_vertical=Control.SIZE_EXPAND_FILL
 b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
 b.pressed.connect(func(): _activate(action, value))
 add_child(b)
 controls[key] = b
 return b

func _box(key:String,parent:Node,vertical:bool=true,separation:int=8) -> BoxContainer:
 var box:BoxContainer=VBoxContainer.new() if vertical else HBoxContainer.new()
 box.name=key
 box.mouse_filter=Control.MOUSE_FILTER_IGNORE
 box.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 box.size_flags_vertical=Control.SIZE_EXPAND_FILL
 box.add_theme_constant_override("separation",separation)
 parent.add_child(box)
 groups[key]=box
 return box

func _pack(node:Control,parent:Node) -> void:
 if node.get_parent()!=parent:
  node.reparent(parent,false)
  node.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)

func _scroll(key:String,parent:Node) -> VBoxContainer:
 var scroll:=ScrollContainer.new()
 scroll.name=key
 scroll.horizontal_scroll_mode=ScrollContainer.SCROLL_MODE_DISABLED
 scroll.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 scroll.size_flags_vertical=Control.SIZE_EXPAND_FILL
 scroll.follow_focus=true
 parent.add_child(scroll)
 groups[key]=scroll
 return _box(key+"_content",scroll,true,10)

func _native_groups() -> void:
 # The only manually bounded Controls are screen regions. Containers own all
 # labels, progress bars, and buttons, including after responsive reparenting.
 var header:=_box("header_row",panels.header,false,12)
 var brand:=_box("brand",header,true,0)
 brand.size_flags_horizontal=Control.SIZE_FILL
 brand.custom_minimum_size.x=224
 _pack(labels.title,brand);_pack(labels.chapter,brand)
 _pack(labels.stats,header)
 labels.stats.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
 var toolbar:=_box("toolbar",header,false,6)
 toolbar.size_flags_horizontal=Control.SIZE_FILL
 for key in ["language","mute","pause","restart","help"]:
  _pack(controls[key],toolbar)
  controls[key].size_flags_horizontal=Control.SIZE_FILL
  controls[key].custom_minimum_size=Vector2(64 if key in ["pause","restart"] else 44,44)
 var bottom:=Control.new()
 bottom.name="BottomRegion";bottom.mouse_filter=Control.MOUSE_FILTER_IGNORE
 add_child(bottom);groups.bottom=bottom
 var wide:=_box("bottom_wide",bottom,false,10)
 var stacked:=_box("bottom_stacked",bottom,true,6)
 wide.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 stacked.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 var hero:=_box("hero_content",panels.hero_panel,true,5)
 for key in ["hero","hero_stats","hero_health"]:_pack(labels[key],hero)
 labels.hero.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 labels.hero_stats.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 _pack(hero_health_bar,hero);hero_health_bar.custom_minimum_size.y=4
 var skills:=_box("skills_row",panels.skills_panel,false,8)
 var pad:=GridContainer.new()
 pad.name="DirectionPad";pad.columns=3;pad.mouse_filter=Control.MOUSE_FILTER_IGNORE
 pad.size_flags_horizontal=Control.SIZE_FILL
 pad.size_flags_vertical=Control.SIZE_SHRINK_CENTER
 skills.add_child(pad);groups.dpad=pad
 for key in ["","move_up","","move_left","move_down","move_right"]:
  if key=="":
   var spacer:=Control.new();spacer.mouse_filter=Control.MOUSE_FILTER_IGNORE
   spacer.custom_minimum_size=Vector2(40,40);pad.add_child(spacer)
  else:
   _pack(controls[key],pad);controls[key].custom_minimum_size=Vector2(40,40)
 var skill_buttons:=_box("skill_buttons",skills,false,6)
 for key in ["skill_1","skill_2","skill_3"]:_pack(controls[key],skill_buttons)
 var actions_wide:=_box("actions_wide",bottom,true,6)
 var actions_stacked:=_box("actions_stacked",bottom,false,6)
 actions_wide.custom_minimum_size.x=120
 for key in ["equipment","build"]:_pack(controls[key],actions_wide)
 var wave_vertical:=_box("wave_vertical",panels.wave_panel,true,4)
 var wave_horizontal:=_box("wave_horizontal",panels.wave_panel,false,8)
 var wave_text:=_box("wave_text",wave_vertical,true,2)
 _pack(labels.wave_status,wave_text);_pack(labels.wave_preview,wave_text)
 labels.wave_status.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 labels.wave_preview.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 var wave_actions:=_box("wave_actions",wave_vertical,false,8)
 _pack(controls.start_wave,wave_actions);_pack(controls.speed,wave_actions)
 controls.speed.size_flags_horizontal=Control.SIZE_FILL
 controls.speed.custom_minimum_size.x=44
 var shop_box:=_box("shop_content",panels.shop_panel,true,8)
 var shop_header:=_box("shop_header",shop_box,false,8)
 shop_header.size_flags_vertical=Control.SIZE_FILL
 _pack(labels.shop_title,shop_header);_pack(controls.close,shop_header)
 controls.close.size_flags_horizontal=Control.SIZE_FILL
 controls.close.custom_minimum_size.x=64
 _pack(labels.shop_tip,shop_box)
 var shop_items:=_scroll("shop_scroll",shop_box)
 for key in ["item_blade","item_plate","item_focus","item_boots","item_potion","tower_sunbow","tower_ember","tower_frost","tower_storm"]:
  _pack(controls[key],shop_items);controls[key].custom_minimum_size.y=54
  controls[key].size_flags_vertical=Control.SIZE_FILL
 _pack(labels.selected_info,shop_items)
 for key in ["upgrade","upgrade_b","sell"]:
  _pack(controls[key],shop_items);controls[key].custom_minimum_size.y=54
  controls[key].size_flags_vertical=Control.SIZE_FILL
 var boss:=_box("boss_content",panels.boss_panel,true,4)
 _pack(labels.boss_status,boss);_pack(boss_health_bar,boss)
 labels.boss_status.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
 labels.boss_status.add_theme_font_size_override("font_size",13)
 boss_health_bar.custom_minimum_size.y=4
 _pack(labels.toast_label,panels.toast)
 labels.toast_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
 labels.toast_label.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 var overlay:=Control.new()
 overlay.name="ModalInputLayer"
 overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 overlay.mouse_filter=Control.MOUSE_FILTER_STOP
 add_child(overlay);groups.modal_layer=overlay
 var shade:=ColorRect.new()
 shade.color=Color(0.01,.025,.035,.56);shade.mouse_filter=Control.MOUSE_FILTER_IGNORE
 overlay.add_child(shade);shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 var margin:=MarginContainer.new()
 overlay.add_child(margin);margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
 margin.mouse_filter=Control.MOUSE_FILTER_IGNORE
 for side in ["left","right","bottom"]:margin.add_theme_constant_override("margin_"+side,12)
 margin.add_theme_constant_override("margin_top",84)
 var center:=CenterContainer.new()
 center.mouse_filter=Control.MOUSE_FILTER_IGNORE;margin.add_child(center)
 _pack(panels.modal,center)
 var modal:=_box("modal_content",panels.modal,true,10)
 for key in ["modal_title","modal_subtitle"]:_pack(labels[key],modal)
 labels.modal_title.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 var prose:=_scroll("modal_scroll",modal)
 for key in ["modal_body","modal_tip"]:_pack(labels[key],prose)
 var modal_actions:=_box("modal_actions",modal,false,12)
 modal_actions.size_flags_vertical=Control.SIZE_FILL
 for key in ["start","resume","confirm_restart","cancel"]:
  _pack(controls[key],modal_actions);controls[key].custom_minimum_size.y=48
 _pack(labels.modal_footer,modal)
 labels.modal_footer.autowrap_mode=TextServer.AUTOWRAP_WORD_SMART
 panels.header.move_to_front()

func _build() -> void:
 for k in ["header", "hero_panel", "skills_panel", "wave_panel", "shop_panel", "modal", "toast", "boss_panel"]: _panel(k)
 _label("title", 24, GOLD)
 _label("chapter", 11, MUTED)
 _label("stats", 18)
 _label("hero", 14, GOLD)
 _label("hero_stats", 15)
 _label("hero_health", 14, TEAL)
 _label("wave_status", 14, GOLD)
 _label("boss_status", 15, CREAM)
 _label("wave_preview", 12, MUTED)
 _label("shop_title", 22, GOLD)
 _label("shop_tip", 13, MUTED)
 _label("selected_info", 14, CREAM)
 _label("toast_label", 18, GOLD)
 _label("modal_title", 38, GOLD)
 _label("modal_subtitle", 12, TEAL)
 _label("modal_body", 18, CREAM)
 _label("modal_tip", 14, MUTED)
 _label("modal_footer", 12, MUTED)
 for k in ["modal_body", "modal_tip", "shop_tip", "selected_info"]:
  labels[k].autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
 _button("language", "language")
 _button("mute", "mute")
 _button("pause", "pause")
 _button("restart", "restart")
 _button("speed", "speed")
 _button("equipment", "shop", "equipment")
 _button("build", "shop", "build")
 _button("start_wave", "start_wave", null, TEAL)
 _button("skill_1", "skill", "q", Color("efd37a"))
 _button("skill_2", "skill", "e", Color("69d9a0"))
 _button("skill_3", "skill", "r", Color("8faaff"))
 _button("close", "close_shop")
 _button("upgrade", "upgrade", "a", TEAL)
 _button("upgrade_b", "upgrade", "b", Color("8faaff"))
 _button("sell", "sell")
 _button("start", "start", null, TEAL)
 _button("resume", "resume", null, TEAL)
 _button("confirm_restart", "confirm_restart", null, TEAL)
 _button("cancel", "cancel")
 _button("help", "help")
 for item in ["blade","plate","focus","boots","potion"]: _button("item_"+item,"item",item)
 for kind in ["sunbow","ember","frost","storm"]: _button("tower_"+kind,"tower",kind)
 for item in [["up",Vector2(0,-1)],["down",Vector2(0,1)],["left",Vector2(-1,0)],["right",Vector2(1,0)]]:
  var b := _button("move_"+item[0], "none")
  b.button_down.connect(func(): _set_direction(str(item[0]),item[1],true))
  b.button_up.connect(func(): _set_direction(str(item[0]),item[1],false))
 labels.modal_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
 labels.modal_subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
 labels.modal_footer.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
 hero_health_bar=_health_bar(panels.hero_panel,TEAL)
 boss_health_bar=_health_bar(panels.boss_panel,Color("e5748c"))
 _native_groups()
 for panel:Control in panels.values():panel.minimum_size_changed.connect(_fit_regions.call_deferred)

func _health_bar(parent:Control,color:Color) -> ProgressBar:
 var bar:=ProgressBar.new()
 bar.show_percentage=false
 bar.mouse_filter=Control.MOUSE_FILTER_IGNORE
 var background:=StyleBoxFlat.new()
 background.bg_color=Color(.1,.2,.2)
 var fill:=StyleBoxFlat.new()
 fill.bg_color=color
 bar.add_theme_stylebox_override("background",background)
 bar.add_theme_stylebox_override("fill",fill)
 parent.add_child(bar)
 return bar

func _set_direction(key: String, direction: Vector2, pressed: bool) -> void:
 if not action_allowed("none") or (portrait and shop!=""):
  clear_touch_movement()
  return
 if pressed: _finger_directions[key] = direction
 else: _finger_directions.erase(key)
 var total := Vector2.ZERO
 for value: Vector2 in _finger_directions.values(): total += value
 move_pressed.emit(total.limit_length())

func clear_touch_movement() -> void:
 _finger_directions.clear()
 move_pressed.emit(Vector2.ZERO)

func action_allowed(action: String) -> bool:
 if action in ["language","mute"]:return true
 if confirming:return action in ["confirm_restart","cancel"]
 if help_open:return action=="cancel"
 if intro:return action=="start"
 if str(state.get("mode","")) in ["victory","defeat","won","lost"]:return action=="confirm_restart"
 if bool(state.get("paused",false)):return action in ["resume","restart"]
 return true

func _activate(action: String, value: Variant) -> void:
 if not action_allowed(action):return
 # Preserve the caller before scope changes hide it or remove its focus mode.
 if _focus_scope=="" and _keyboard_navigation:
  var focused:=get_viewport().gui_get_focus_owner()
  if focused!=null:_restore_focus=focused
 if action == "shop":
  shop = "" if shop == str(value) else str(value)
 elif action == "close_shop": shop = ""
 elif action == "restart": confirming = true; command.emit("modal_open",null)
 elif action == "cancel": confirming = false; help_open = false; command.emit("modal_close",null)
 elif action == "help": help_open = true; command.emit("modal_open",null)
 elif action == "start": intro = false; command.emit("unlock",null)
 elif action == "confirm_restart": confirming = false; shop = ""; command.emit("restart",null)
 elif action == "resume": command.emit("pause",null)
 elif action != "none": command.emit(action,value)
 _layout()
 if not _keyboard_navigation:_release_pointer_focus.call_deferred()

func set_language(value: String) -> void:
 language = value
 _refresh()
 _layout()

func set_state(value: Dictionary) -> void:
 state = value
 _refresh()
 if not groups.is_empty():_sync_focus()

func open_build() -> void:
 shop = "build"
 _layout()

func announce(key: String, _data: Dictionary = {}) -> void:
 if WORDS.has(key):
  toast_text = text(key)
  toast_time = 2.6
  labels.toast_label.text = toast_text
  _layout()

func _process(delta: float) -> void:
 if toast_time > 0:
  toast_time = maxf(0,toast_time-delta)
  panels.toast.visible = toast_time > 0 and not intro
  labels.toast_label.visible = panels.toast.visible
 if size != _layout_size: _layout()
 queue_redraw()

func _place(node: Control, r: Rect2, visible_now: bool = true) -> void:
 # For top-level regions only. Never use this on a Container-managed child.
 node.position = r.position
 node.size = r.size
 node.visible = visible_now

func is_modal_open() -> bool:
 return intro or confirming or help_open or bool(state.get("paused",false)) or str(state.get("mode","")) in ["victory","defeat","won","lost"]

func keyboard_navigation_active() -> bool:
 return _keyboard_navigation

func leave_keyboard_navigation() -> void:
 _keyboard_navigation=false
 _restore_focus=null
 _release_pointer_focus()

func _input(event:InputEvent) -> void:
 if event is InputEventKey and event.pressed and event.keycode==KEY_TAB:
  _keyboard_navigation=true
  if get_viewport().gui_get_focus_owner()==null:
   _focus_first.call_deferred(event.shift_pressed)
   get_viewport().set_input_as_handled()
 elif event is InputEventMouseButton and event.pressed:
  _keyboard_navigation=false
  if not is_modal_open():_release_pointer_focus.call_deferred()

func _release_pointer_focus() -> void:
 if _keyboard_navigation or is_modal_open():return
 var focused:=get_viewport().gui_get_focus_owner()
 if focused!=null:focused.release_focus()

func _focus_first(reverse:bool=false) -> void:
 var eligible:=_focus_candidates()
 if not eligible.is_empty():eligible[-1 if reverse else 0].grab_focus()

func _focus_candidates() -> Array[Control]:
 var result:Array[Control]=[]
 # Stable semantic order, independent of reparenting or dictionary insertion.
 var order:Array=["start","resume","restart","confirm_restart","cancel"] if is_modal_open() else (["close","item_blade","item_plate","item_focus","item_boots","item_potion","tower_sunbow","tower_ember","tower_frost","tower_storm","upgrade","upgrade_b","sell"] if shop!="" else ["equipment","build","skill_1","skill_2","skill_3","start_wave","speed","pause","restart","help"])
 order.append_array(["language","mute"])
 for key:String in order:
  var button:Button=controls[key]
  if button.is_visible_in_tree() and not button.disabled:result.append(button)
 return result

func _sync_focus() -> void:
 var eligible:=_focus_candidates()
 for button:Button in controls.values():
  button.focus_mode=Control.FOCUS_ALL if button in eligible else Control.FOCUS_NONE
 for i in range(eligible.size()):
  var button:Control=eligible[i]
  var previous:=button.get_path_to(eligible[posmod(i-1,eligible.size())])
  var next:=button.get_path_to(eligible[(i+1)%eligible.size()])
  button.focus_previous=previous;button.focus_next=next
  button.focus_neighbor_left=previous;button.focus_neighbor_top=previous
  button.focus_neighbor_right=next;button.focus_neighbor_bottom=next
 var scope:String=("confirm" if confirming else "help" if help_open else "intro" if intro else str(state.get("mode",""))+"_modal") if is_modal_open() else shop
 if scope!=_focus_scope:
  groups.modal_scroll.scroll_vertical=0
  if _focus_scope=="" and _keyboard_navigation:
   var current_focus:=get_viewport().gui_get_focus_owner()
   if current_focus!=null:_restore_focus=current_focus
  var was_modal:bool=_focus_scope!=""
  _focus_scope=scope
  if is_modal_open():
   _keyboard_navigation=true
   _focus_first.call_deferred()
  elif _keyboard_navigation and shop!="":_focus_first.call_deferred()
  elif _keyboard_navigation and was_modal and is_instance_valid(_restore_focus) and _restore_focus.is_visible_in_tree() and _restore_focus.focus_mode!=Control.FOCUS_NONE:_restore_focus.grab_focus.call_deferred()
  elif scope=="":
   _keyboard_navigation=false
   _release_pointer_focus.call_deferred()
  elif not _keyboard_navigation:_release_pointer_focus.call_deferred()
  if scope=="":_restore_focus=null
 elif _keyboard_navigation:
  var focused:=get_viewport().gui_get_focus_owner()
  if focused==null or focused not in eligible:_focus_first.call_deferred()

func _layout() -> void:
 _layout_size = size
 if size.x <= 0 or groups.is_empty(): return
 portrait = size.x < 1080 or size.x / maxf(size.y,1) < 1.18
 _compact=portrait and size.x>=720 and size.y<520
 _stacked=portrait and not _compact
 var w:=size.x;var h:=size.y
 var pad:=10.0 if portrait else 20.0
 var bottom_height:=222.0 if _stacked else (108.0 if _compact else 136.0)
 var bottom:Control=groups.bottom
 bottom.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
 bottom.offset_left=pad;bottom.offset_right=-pad
 bottom.offset_top=-bottom_height-pad;bottom.offset_bottom=-pad
 groups.bottom_wide.visible=not _stacked
 groups.bottom_stacked.visible=_stacked
 var flow:Container=groups.bottom_stacked if _stacked else groups.bottom_wide
 _pack(panels.hero_panel,flow);_pack(panels.skills_panel,flow)
 var actions:Container=groups.actions_stacked if _stacked else groups.actions_wide
 _pack(actions,flow)
 groups.actions_stacked.visible=_stacked;groups.actions_wide.visible=not _stacked
 flow.move_child(panels.hero_panel,0);flow.move_child(panels.skills_panel,1);flow.move_child(actions,2)
 for key in ["equipment","build"]:_pack(controls[key],actions)
 _pack(controls.pause,actions if _stacked else groups.toolbar)
 _pack(controls.restart,groups.toolbar)
 controls.restart.size_flags_horizontal=Control.SIZE_FILL
 controls.restart.custom_minimum_size=Vector2(64,44)
 var toolbar_index:=0
 for key in ["language","mute","pause","restart","help"]:
  if controls[key].get_parent()==groups.toolbar:
   groups.toolbar.move_child(controls[key],toolbar_index);toolbar_index+=1
 for key:String in controls:controls[key].visible=true
 panels.hero_panel.visible=true;panels.skills_panel.visible=true
 panels.hero_panel.custom_minimum_size=Vector2(0 if _stacked else (220 if portrait else 250),0)
 panels.skills_panel.custom_minimum_size=Vector2(0 if _stacked else (320 if portrait else 314),96 if _stacked else 0)
 panels.hero_panel.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 panels.skills_panel.size_flags_horizontal=Control.SIZE_EXPAND_FILL
 panels.skills_panel.size_flags_stretch_ratio=1.5 if portrait else 1.0
 panels.hero_panel.size_flags_vertical=Control.SIZE_FILL if _stacked else Control.SIZE_EXPAND_FILL
 panels.skills_panel.size_flags_vertical=Control.SIZE_EXPAND_FILL
 actions.custom_minimum_size.y=44 if _stacked else 0
 actions.size_flags_vertical=Control.SIZE_FILL if _stacked else Control.SIZE_EXPAND_FILL
 labels.hero_health.visible=not _stacked
 groups.hero_content.add_theme_constant_override("separation",2 if _stacked else 5)
 groups.dpad.visible=portrait
 for key in ["move_up","move_down","move_left","move_right"]:controls[key].visible=portrait
 _place(panels.header,Rect2(pad,pad,w-pad*2,76 if _compact else (60 if portrait else 68)))
 groups.brand.visible=not portrait
 controls.restart.visible=not portrait;controls.help.visible=not portrait
 controls.pause.size_flags_horizontal=Control.SIZE_EXPAND_FILL if portrait else Control.SIZE_FILL
 controls.pause.custom_minimum_size.x=0 if _stacked else 64
 labels.stats.size_flags_horizontal=Control.SIZE_FILL if _compact else Control.SIZE_EXPAND_FILL
 groups.wave_vertical.visible=not portrait;groups.wave_horizontal.visible=portrait
 _pack(groups.wave_text,groups.wave_horizontal if portrait else groups.wave_vertical)
 _pack(groups.wave_actions,groups.wave_horizontal if portrait else groups.wave_vertical)
 panels.wave_panel.theme_type_variation="DawnInline" if _compact else ""
 if _compact:
  _pack(panels.wave_panel,groups.header_row)
  groups.header_row.move_child(panels.wave_panel,2)
  panels.wave_panel.custom_minimum_size=Vector2(310,0)
  panels.wave_panel.size_flags_horizontal=Control.SIZE_EXPAND_FILL
  groups.wave_actions.size_flags_horizontal=Control.SIZE_FILL
  controls.start_wave.custom_minimum_size.x=128
 elif portrait:
  _pack(panels.wave_panel,self)
  panels.wave_panel.custom_minimum_size=Vector2.ZERO
  _place(panels.wave_panel,Rect2(pad,78,w-pad*2,56))
  groups.wave_actions.size_flags_horizontal=Control.SIZE_FILL
  controls.start_wave.custom_minimum_size.x=128
 else:
  _pack(panels.wave_panel,flow)
  panels.wave_panel.custom_minimum_size=Vector2(270,0)
  panels.wave_panel.size_flags_horizontal=Control.SIZE_EXPAND_FILL
  groups.wave_actions.size_flags_horizontal=Control.SIZE_EXPAND_FILL
  controls.start_wave.custom_minimum_size.x=0
 panels.wave_panel.visible=true
 controls.speed.visible=not portrait
 labels.wave_preview.visible=not portrait
 labels.wave_status.add_theme_font_size_override("font_size",12 if portrait else 14)
 var sw:=minf(410,w-20)
 var sh:=minf(430,h-96)
 var sy:=maxf(80,minf(h-bottom_height-pad-sh-12,h-sh-12))
 _place(panels.shop_panel,Rect2((w-sw)*.5 if portrait else w-sw-pad,sy,sw,sh),shop!="")
 var selected:Dictionary=state.get("selected_tower",{}) if state.get("selected_tower") is Dictionary else {}
 var has_tower:=not selected.is_empty()
 var content_key:String=shop+":"+str(selected.get("kind",""))+":"+str(selected.get("level",0))+":"+str(selected.get("branch",""))
 if content_key!=_shop_content:groups.shop_scroll.scroll_vertical=0;_shop_content=content_key
 for key in ["blade","plate","focus","boots","potion"]:controls["item_"+key].visible=shop=="equipment"
 for key in ["sunbow","ember","frost","storm"]:controls["tower_"+key].visible=shop=="build" and not has_tower
 labels.selected_info.visible=shop=="build" and has_tower
 for key in ["upgrade","upgrade_b","sell"]:controls[key].visible=shop=="build" and has_tower
 var has_boss:bool=not state.get("boss",{}).is_empty()
 minimap_rect=Rect2(12,(146 if has_boss else 98) if _compact else (190 if has_boss else 142),112,82) if portrait else Rect2(20,102,148,104)
 var bw:=minf(440,w-28)
 _place(panels.boss_panel,Rect2((w-bw)/2,140 if _stacked else 98,bw,44),has_boss)
 var tw:=minf(500,w-40)
 _place(panels.toast,Rect2((w-tw)/2,190 if has_boss and portrait else 140,tw,44),toast_time>0 and not intro)
 var mode:String=str(state.get("mode","build"))
 var ended:=mode in ["victory","defeat","won","lost"]
 var paused:bool=bool(state.get("paused",false))
 var modal:=is_modal_open()
 groups.modal_layer.visible=modal
 panels.modal.visible=modal
 panels.modal.custom_minimum_size=Vector2(minf(700,w-24),minf(424 if portrait else 464,h-96))
 panels.modal.size=panels.modal.custom_minimum_size
 labels.modal_title.add_theme_font_size_override("font_size",22 if w<400 else (30 if portrait else 38))
 for key in ["start","resume","confirm_restart","cancel"]:controls[key].visible=false
 if intro:
  bottom.visible=false;panels.wave_panel.visible=false;panels.boss_panel.visible=false;panels.toast.visible=false
 elif shop=="" or not portrait:bottom.visible=true
 if modal:
  var allowed:Array=["language","mute"]
  if confirming:allowed.append_array(["confirm_restart","cancel"])
  elif help_open:allowed.append("cancel")
  elif intro:allowed.append("start")
  elif ended:allowed.append("confirm_restart")
  else:
   allowed.append_array(["resume","restart"])
   _pack(controls.restart,groups.modal_actions)
   controls.restart.size_flags_horizontal=Control.SIZE_EXPAND_FILL
   controls.restart.custom_minimum_size.y=48
  for key:String in controls:controls[key].visible=key in allowed
  clear_touch_movement()
  groups.modal_layer.move_to_front();panels.header.move_to_front()
 elif portrait and shop!="":
  bottom.visible=false
  panels.wave_panel.visible=false
  panels.shop_panel.move_to_front()
  clear_touch_movement()
 else:bottom.visible=true
 _refresh()
 _sync_focus()
 _fit_regions.call_deferred()
 queue_redraw()

func _fit_regions() -> void:
 # Child minimum sizes propagate after sorting. Refit only free screen regions;
 # Container children retain exclusive native layout ownership.
 if groups.is_empty() or size.x<=0:return
 var w:=size.x;var h:=size.y;var pad:=10.0 if portrait else 20.0
 _place(panels.header,Rect2(pad,pad,w-pad*2,76 if _compact else (60 if portrait else 68)))
 if _stacked:_place(panels.wave_panel,Rect2(pad,78,w-pad*2,60),panels.wave_panel.visible)
 var sw:=minf(410,w-20);var sh:=minf(430,h-96)
 var bottom_height:=222.0 if _stacked else (108.0 if _compact else 136.0)
 var sy:=maxf(80,minf(h-bottom_height-pad-sh-12,h-sh-12))
 _place(panels.shop_panel,Rect2((w-sw)*.5 if portrait else w-sw-pad,sy,sw,sh),shop!="")
 var bw:=minf(440,w-28)
 _place(panels.boss_panel,Rect2((w-bw)/2,140 if _stacked else 98,bw,44),panels.boss_panel.visible)
 var tw:=minf(500,w-40)
 _place(panels.toast,Rect2((w-tw)/2,190 if not state.get("boss",{}).is_empty() and portrait else 140,tw,44),panels.toast.visible)

func _refresh() -> void:
 if labels.is_empty(): return
 labels.title.text = text("title")
 labels.chapter.text = text("chapter")
 var wave: int = int(state.get("wave",0))
 var gold: int = int(state.get("gold",420))
 var core: int = int(state.get("core_hp",20))
 labels.stats.text = ("%s %d   ·   %s %d   ·   %s %d/8" % [text("core"),core,text("gold"),gold,text("wave"),wave]) if not portrait else ("%s %d\n%d G  ·  %s %d/8" % [text("core"),core,gold,text("wave"),wave])
 labels.stats.add_theme_font_size_override("font_size",13 if portrait else 17)
 var hero: Dictionary = state.get("hero",{})
 var mode: String = str(state.get("mode","build"))
 if is_instance_valid(hero_health_bar):hero_health_bar.value=100.0*float(hero.get("hp",240))/maxf(1,float(hero.get("max_hp",240)))
 labels.hero.text = text("hero")
 if hero.get("dead",false):
  labels.hero.text = "%s · %s" % [text("hero_name"),text("fallen")] if mode in ["victory","defeat","won","lost"] else "%s · %s %.1fs" % [text("hero_name"),text("respawn"),float(hero.get("respawn",0))]
 labels.hero_stats.text = "%s %d    %s %d    XP %d / %d" % [text("level"),hero.get("level",1),text("damage"),hero.get("damage",32),hero.get("xp",0),hero.get("xp_next",70)]
 labels.hero_stats.add_theme_font_size_override("font_size",12 if portrait else 14)
 labels.hero_health.text = "%s  %d / %d" % [text("health"),hero.get("hp",240),hero.get("max_hp",240)]
 var active := mode in ["wave","combat","playing"]
 labels.wave_status.text = text("in_wave") if active else text("prepare")
 var boss:Dictionary=state.get("boss",{})
 if is_instance_valid(boss_health_bar):boss_health_bar.value=100.0*float(boss.get("hp",0))/maxf(1,float(boss.get("max_hp",1)))
 labels.boss_status.text=text("boss")+"  %d / %d"%[boss.get("hp",0),boss.get("max_hp",1)]
 labels.wave_preview.text = "%s: %d" % [text("enemies"),state.get("enemies",[]).size()] if active else text("dawn")
 controls.start_wave.text = text("next_wave")+" +30" if state.get("early_call",false) else (text("in_wave") if active else text("next_wave"))
 controls.start_wave.disabled = not bool(state.get("can_start_wave",true)) or intro
 controls.start_wave.add_theme_font_size_override("font_size",12 if portrait else 14)
 controls.language.text = "EN" if language=="zh" else "中文"
 controls.mute.text = ("♪" if not muted else "×♪")
 controls.mute.tooltip_text = text("music_off" if muted else "music_on")
 controls.pause.text = text("pause")
 controls.restart.text = text("restart")
 controls.help.text = "?"
 controls.equipment.text = text("equipment")
 controls.build.text = text("towers")
 controls.close.text = text("close")
 controls.speed.text = "%dx" % int(state.get("speed",1))
 for i in range(3):
  var key: String = ["q","e","r"][i]
  var cd: float = 0
  var skills: Dictionary = state.get("skills",state.get("cooldowns",{}))
  var data: Variant = skills.get(key,0)
  if data is Dictionary: cd=float(data.get("cooldown",data.get("remaining",0)))
  elif data is float or data is int: cd=float(data)
  var unlocked := i<2 or int(hero.get("level",1))>=3
  var suffix := text("ready") if cd<=0 else "%.1fs"%cd
  if not unlocked: suffix=text("locked")
  var skill_name:String=text(key)
  if portrait:skill_name=(["斩击","振奋","星落"][i] if language=="zh" else ["CUT" if size.x<360 else "CLEAVE","RALLY","NOVA"][i])
  elif language=="en":skill_name=["DAWN\nCLEAVE","RALLYING\nLIGHT","STARFALL"][i]
  if portrait and not unlocked:suffix="Lv3"
  controls["skill_"+str(i+1)].text = key.to_upper()+"\n"+skill_name+"\n"+suffix
  controls["skill_"+str(i+1)].add_theme_font_size_override("font_size",(11 if size.x<360 else 12) if portrait else 14)
  controls["skill_"+str(i+1)].disabled = not unlocked or cd>0 or bool(hero.get("dead",false)) or intro
  controls["skill_"+str(i+1)].tooltip_text = text(key+"_tip")
 labels.shop_title.text = text("equipment" if shop=="equipment" else "towers")
 labels.shop_tip.text = text("shop_tip" if shop=="equipment" else "build_tip")
 var inventory: Array = state.get("shop",[])
 var fallback_costs := {"blade":90,"plate":90,"focus":110,"boots":75,"potion":45}
 for key: String in fallback_costs:
  var item: Dictionary = {}
  for entry: Dictionary in inventory:
   if str(entry.get("key",entry.get("id",""))) == key: item=entry
  var cost: int = int(item.get("cost",fallback_costs[key]))
  var owned:int=int(item.get("count",0))
  var maximum:int=int(item.get("max_count",99 if key=="potion" else 3))
  var rank:String="%s %d"%[text("owned"),owned] if key=="potion" else "%d/%d"%[owned,maximum]
  controls["item_"+key].text = "%s · %d G · %s\n%s" % [text(key),cost,rank,text(key+"_tip")]
  controls["item_"+key].add_theme_font_size_override("font_size",13)
  controls["item_"+key].disabled = gold<cost or (item.has("available") and not item.available)
 var costs := {"sunbow":80,"ember":115,"frost":100,"storm":145}
 for key: String in costs:
  controls["tower_"+key].text = "%s   ·   %d G\n%s" % [text(key),costs[key],text(key+"_tip")]
  controls["tower_"+key].add_theme_font_size_override("font_size",13)
  controls["tower_"+key].disabled = gold<int(costs[key]) or int(state.get("selected_pad",-1))<0
 var selected: Dictionary = state.get("selected_tower",{}) if state.get("selected_tower") is Dictionary else {}
 if not selected.is_empty():
  labels.selected_info.text = "%s  ·  %s %d\n%s" % [text(str(selected.get("kind","sunbow"))),text("level"),selected.get("level",1),text(str(selected.get("kind","sunbow"))+"_tip")]
  var branch:String=str(selected.get("branch",""))
  if branch!="":labels.selected_info.text+="\n"+text(branch)+" · "+text(branch+"_tip")
 var upgrades:Array=selected.get("upgrades",[])
 for i in range(2):
  var b:Button=controls.upgrade if i==0 else controls.upgrade_b
  if upgrades.size()>i:
   var option:Dictionary=upgrades[i]
   var branch_key:String=str(option.get("key","branch_a"))
   var chosen:String=str(selected.get("branch",""))
   var suffix:String=(text("chosen") if chosen==branch_key else text("other_path")) if chosen!="" else "%d G"%int(option.get("cost",0))
   b.text=text(branch_key)+" · "+suffix+"\n"+text(branch_key+"_tip")
   b.add_theme_font_size_override("font_size",12)
   b.tooltip_text=text(branch_key+"_tip")
   b.disabled=not bool(option.get("available",false))
  else:
   b.text=text("maxed")
   b.disabled=true
 controls.sell.text=text("sell")+" · %d G"%int(selected.get("refund",0))
 controls.move_up.text="▲"
 controls.move_down.text="▼"
 controls.move_left.text="◀"
 controls.move_right.text="▶"
 for key in ["start","resume","cancel"]: controls[key].text=text(key)
 controls.confirm_restart.text=text("confirm")
 var ended := mode in ["victory","defeat","won","lost"]
 var won := mode in ["victory","won"]
 labels.modal_title.text=text("title" if intro or help_open else ("reset_question" if confirming else ("victory" if won else "defeat") if ended else "paused"))
 if confirming: labels.modal_title.text=text("restart")
 labels.modal_subtitle.text=text("subtitle")
 labels.modal_body.text=text("goal" if intro or help_open else ("reset_question" if confirming else ("victory_tip" if won else "defeat_tip") if ended else "paused_tip"))
 if size.y<450 and (intro or help_open):labels.modal_body.text=text("short_goal")
 labels.modal_tip.text=(text("touch_controls") if portrait else text("controls")+"\n\n"+text("intro_tip")) if intro or help_open else text("intro_tip")
 labels.modal_footer.text=text("saved_tip")

func _visible_rect(control:Control) -> Rect2:
 var rect:=control.get_global_rect()
 var ancestor:=control.get_parent()
 while ancestor is Control:
  if ancestor.clip_contents:rect=rect.intersection(ancestor.get_global_rect())
  ancestor=ancestor.get_parent()
 return rect

func ui_snapshot() -> Dictionary:
 var result: Dictionary = {}
 var modal := intro or confirming or help_open or bool(state.get("paused",false)) or str(state.get("mode","")) in ["victory","defeat","won","lost"]
 for key: String in controls:
  var button: Button = controls[key]
  if not button.is_visible_in_tree(): continue
  var r := _visible_rect(button)
  if not r.has_area():continue
  result[key]={"x":r.position.x,"y":r.position.y,"w":r.size.x,"h":r.size.y,"enabled":not button.disabled}
 var rendered: Array[String]=[]
 for l: Label in labels.values():
  if l.is_visible_in_tree() and _visible_rect(l).has_area(): rendered.append(l.text)
 for b: Button in controls.values():
  if b.is_visible_in_tree() and _visible_rect(b).has_area(): rendered.append(b.text)
 var focused:=get_viewport().gui_get_focus_owner()
 return {"focus_owner":str(focused.name) if focused!=null else "","keyboard_navigation":_keyboard_navigation,"controls":result,"labels":rendered,"portrait":portrait,"intro":intro,"shop":shop,"minimap":{"x":minimap_rect.position.x,"y":minimap_rect.position.y,"w":minimap_rect.size.x,"h":minimap_rect.size.y}}

func blocks_world(point: Vector2) -> bool:
 if intro or confirming or help_open or bool(state.get("paused",false)) or str(state.get("mode","")) in ["victory","defeat","won","lost"]: return true
 for p: Control in panels.values():
  if p.is_visible_in_tree() and p.get_global_rect().has_point(point): return true
 for b: Button in controls.values():
  if b.is_visible_in_tree() and _visible_rect(b).has_point(point): return true
 return false

func minimap_world(point:Vector2) -> Vector3:
 var uv:Vector2=(point-minimap_rect.position)/minimap_rect.size
 return Vector3(uv.x*34-17,0,uv.y*22-11)

func _map_point(point:Variant) -> Vector2:
 var x:float=float(point.get("x",0)) if point is Dictionary else float(point[0])
 var z:float=float(point.get("z",0)) if point is Dictionary else float(point[2])
 return minimap_rect.position+Vector2((x+17)/34,(z+11)/22)*minimap_rect.size

func _draw() -> void:
 if state.is_empty(): return
 if not intro:
  draw_style_box(_style(Color(.03,.08,.09,.76),Color(.4,.6,.56),5),minimap_rect)
  var routes=[[[ -15,-7],[-8,-7],[-8,2],[-2,2],[-2,-5],[7,-5],[7,5],[13,5]],[[-15,8],[-11,8],[-11,2],[-2,2]]]
  for route:Array in routes:
   var points:=PackedVector2Array()
   for point:Array in route:points.append(_map_point([point[0],0,point[1]]))
   draw_polyline(points,Color(.57,.57,.4,.8),1.4,true)
  for tower:Dictionary in state.get("towers",[]):draw_circle(_map_point(tower.position),2.5,GOLD)
  for enemy:Dictionary in state.get("enemies",[]):draw_circle(_map_point(enemy.position),2,Color("e98880"))
  draw_circle(_map_point([13,0,5]),3.5,TEAL)
  draw_circle(_map_point(state.get("hero",{}).get("position",{"x":-6,"z":0})),3.6,Color("ffd98d"))
 # Original compass emblem anchors the HUD without a third-party image.
 if not portrait:
  var center := Vector2(40,44)
  draw_arc(center,10,0,TAU,30,GOLD,1.4,true)
