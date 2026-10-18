extends Control
## Original responsive interface. Every displayed gameplay label is localized.
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
 "hero":["ELYRA · DAWNWARDEN", "艾莉拉 · 曙光守护者"], "level":["LV", "等级"],
 "start":["ENTER THE PASS", "进入隘口"],
 "goal":["Stand against the Hollow Court. Protect the Dawnheart through eight waves and defeat the Crownless King.", "抵御空壳王庭的侵袭。守住曙光之心，撑过八波敌潮，击败无冕之王。"],
 "intro_tip":["Move to intercept enemies. Your hero attacks nearby foes automatically. Spend gold on equipment, then place supporting towers.", "主动迎击敌人，英雄会自动攻击近处目标。用金币强化装备，再建造防御塔协助守护。"],
 "controls":["WASD / arrows: move   ·   Click ground: move   ·   Q E R: skills   ·   Space: next wave", "WASD / 方向键移动 · 点击地面移动 · Q E R 技能 · 空格开始下一波"],
 "touch_controls":["Tap the ground to move. Use the direction pad and skill buttons. Tap a gold platform to build.", "点击地面移动，也可使用方向键与技能按钮。点击金色基座建造防御塔。"],
 "next_wave":["CALL NEXT WAVE", "迎战下一波"], "in_wave":["DEFEND THE DAWNHEART", "守住曙光之心"],
 "prepare":["Prepare your defense", "整备防线"], "equipment":["EQUIPMENT", "装备"], "towers":["DEFENSES", "防御"],
 "pause":["PAUSE", "暂停"], "resume":["RESUME", "继续"], "restart":["RESTART", "重开"],
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
 "saved_tip":["This is one complete, replayable defense. No account is required.", "一场完整可重玩的守护战，无需账号。"],
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
 "conduit":["CHAIN CONDUIT", "连锁导流"], "tempest":["TEMPEST HEART", "风暴之心"]
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

func _panel(key: String, color: Color = Color(.035,.08,.10,.94)) -> Panel:
 var p := Panel.new()
 p.add_theme_stylebox_override("panel", _style(color))
 p.mouse_filter = Control.MOUSE_FILTER_STOP
 add_child(p)
 panels[key] = p
 return p

func _label(key: String, size_px: int = 18, color: Color = CREAM) -> Label:
 var l := Label.new()
 l.add_theme_font_size_override("font_size", size_px)
 l.add_theme_color_override("font_color", color)
 l.mouse_filter = Control.MOUSE_FILTER_IGNORE
 l.text = text(key)
 add_child(l)
 labels[key] = l
 return l

func _button(key: String, action: String, value: Variant = null, color: Color = GOLD) -> Button:
 var b := Button.new()
 b.text = text(key)
 b.add_theme_font_size_override("font_size", 15)
 b.add_theme_color_override("font_color", CREAM)
 b.add_theme_color_override("font_hover_color", Color.WHITE)
 b.add_theme_color_override("font_disabled_color", MUTED.darkened(.3))
 b.add_theme_stylebox_override("normal", _style(Color(.055,.12,.145,.97), color, 7))
 b.add_theme_stylebox_override("hover", _style(Color(.11,.23,.25,.98), color.lightened(.2), 7))
 b.add_theme_stylebox_override("pressed", _style(Color(.16,.28,.26,.98), color, 7))
 b.add_theme_stylebox_override("disabled", _style(Color(.035,.065,.08,.85), MUTED.darkened(.6), 7))
 b.add_theme_stylebox_override("focus", _style(Color(0,0,0,0), Color.WHITE, 7))
 b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
 b.pressed.connect(func(): _activate(action, value))
 add_child(b)
 controls[key] = b
 return b

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

func _set_direction(key: String, direction: Vector2, pressed: bool) -> void:
 if pressed: _finger_directions[key] = direction
 else: _finger_directions.erase(key)
 var total := Vector2.ZERO
 for value: Vector2 in _finger_directions.values(): total += value
 move_pressed.emit(total.limit_length())

func _activate(action: String, value: Variant) -> void:
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

func set_language(value: String) -> void:
 language = value
 _refresh()
 _layout()

func set_state(value: Dictionary) -> void:
 state = value
 _refresh()

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
 node.position = r.position
 node.size = r.size
 node.visible = visible_now

func _layout() -> void:
 _layout_size = size
 if size.x <= 0: return
 portrait = size.x < 1080 or size.x / maxf(size.y,1) < 1.18
 var w := size.x
 var h := size.y
 var pad := 10.0 if portrait else 20.0
 _place(panels.header, Rect2(pad,pad,w-pad*2,60 if portrait else 68))
 _place(labels.title,Rect2(pad+14,pad+5,210,31),not portrait)
 _place(labels.chapter,Rect2(pad+15,pad+39,230,18),not portrait)
 _place(labels.stats,Rect2(pad+12 if portrait else 292,pad+12,w-168 if portrait else w-625,35))
 var tools_x := w-pad-(104 if portrait else 310)
 for i in range(2 if portrait else 5):
  var key: String = ["language","mute","pause","restart","help"][i]
  _place(controls[key],Rect2(tools_x+i*(48 if portrait else 60),pad+10,44 if portrait else 56,40))
 for key in ["pause","restart","help"]: controls[key].visible = not portrait
 var bottom := h-(222 if portrait else 156)
 if portrait:
  _place(panels.hero_panel,Rect2(pad,bottom,w-pad*2,52))
  _place(labels.hero,Rect2(pad+12,bottom+5,w-20,20))
  _place(labels.hero_stats,Rect2(pad+12,bottom+26,w-20,20))
  labels.hero_health.visible = false
  _place(panels.skills_panel,Rect2(pad,bottom+58,w-pad*2,104))
  for i in range(3): _place(controls["skill_"+str(i+1)],Rect2(pad+150+i*((w-pad*2-160)/3),bottom+66,maxf(44,(w-pad*2-172)/3),88))
  for item in [["up",44,0],["left",0,44],["down",44,44],["right",88,44]]:
   _place(controls["move_"+str(item[0])],Rect2(pad+8+item[1],bottom+66+item[2],44,44))
  _place(controls.equipment,Rect2(pad,bottom+168,(w-pad*2-12)/3,44))
  _place(controls.build,Rect2(pad+(w-pad*2)/3,bottom+168,(w-pad*2-12)/3,44))
  _place(controls.pause,Rect2(pad+(w-pad*2)*2/3,bottom+168,(w-pad*2-12)/3,44))
  _place(panels.wave_panel,Rect2(pad,78,w-pad*2,50))
  _place(labels.wave_status,Rect2(pad+10,83,w-170,22))
  _place(labels.wave_preview,Rect2(pad+10,105,w-170,18))
  _place(controls.start_wave,Rect2(w-pad-138,83,128,40))
  controls.speed.visible = false
 else:
  _place(panels.hero_panel,Rect2(pad,bottom,276,136))
  _place(labels.hero,Rect2(pad+16,bottom+11,254,25))
  _place(labels.hero_stats,Rect2(pad+16,bottom+42,254,24))
  _place(labels.hero_health,Rect2(pad+16,bottom+74,254,22))
  _place(panels.skills_panel,Rect2(310,bottom,338,136))
  for i in range(3): _place(controls["skill_"+str(i+1)],Rect2(320+i*108,bottom+11,98,114))
  _place(panels.wave_panel,Rect2(w-322,bottom,302,136))
  _place(labels.wave_status,Rect2(w-307,bottom+9,240,24))
  _place(labels.wave_preview,Rect2(w-307,bottom+35,260,22))
  _place(controls.start_wave,Rect2(w-307,bottom+68,216,52))
  _place(controls.speed,Rect2(w-81,bottom+68,46,52))
  _place(controls.equipment,Rect2(662,bottom+11,w-998,54))
  _place(controls.build,Rect2(662,bottom+73,w-998,52))
  for key in ["move_up","move_down","move_left","move_right"]: controls[key].visible = false
 var sw := minf(390,w-20)
 var sx := (w-sw)*.5 if portrait else w-sw-20
 var sy := maxf(136,bottom-(374 if portrait else 370)-12)
 _place(panels.shop_panel,Rect2(sx,sy,sw,366),shop != "")
 _place(labels.shop_title,Rect2(sx+16,sy+12,sw-90,30),shop != "")
 _place(controls.close,Rect2(sx+sw-70,sy+10,58,36),shop != "")
 _place(labels.shop_tip,Rect2(sx+16,sy+49,sw-32,40),shop != "")
 for i in range(5):
  var key: String = ["blade","plate","focus","boots","potion"][i]
  _place(controls["item_"+key],Rect2(sx+14,sy+96+i*50,sw-28,44),shop == "equipment")
 var selected: Dictionary = state.get("selected_tower",{}) if state.get("selected_tower") is Dictionary else {}
 var has_tower := not selected.is_empty()
 for i in range(4):
  var key: String = ["sunbow","ember","frost","storm"][i]
  _place(controls["tower_"+key],Rect2(sx+14,sy+96+i*62,sw-28,54),shop == "build" and not has_tower)
 _place(labels.selected_info,Rect2(sx+16,sy+96,sw-32,90),shop == "build" and has_tower)
 _place(controls.upgrade,Rect2(sx+14,sy+190,sw-28,50),shop == "build" and has_tower)
 _place(controls.upgrade_b,Rect2(sx+14,sy+246,sw-28,50),shop == "build" and has_tower)
 _place(controls.sell,Rect2(sx+14,sy+304,sw-28,46),shop == "build" and has_tower)
 var has_boss:bool=not state.get("boss",{}).is_empty()
 minimap_rect=Rect2(12,184 if has_boss else 136,112,82) if portrait else Rect2(20,102,148,104)
 var bw:=minf(440,w-28)
 _place(panels.boss_panel,Rect2((w-bw)/2,136 if portrait else 98,bw,42),has_boss)
 _place(labels.boss_status,Rect2((w-bw)/2+12,140 if portrait else 102,bw-24,24),has_boss)
 var tw := minf(500,w-40)
 _place(panels.toast,Rect2((w-tw)/2,140,tw,44),toast_time>0 and not intro)
 _place(labels.toast_label,Rect2((w-tw)/2+10,147,tw-20,30),panels.toast.visible)
 labels.toast_label.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
 var mode: String = str(state.get("mode","build"))
 var ended := mode in ["victory","defeat","won","lost"]
 var paused: bool = bool(state.get("paused",false))
 var modal := intro or paused or confirming or ended or help_open
 var mw := minf(700,w-24)
 var mh := minf(464,h-32)
 var mx := (w-mw)*.5
 var my := (h-mh)*.5
 _place(panels.modal,Rect2(mx,my,mw,mh),modal)
 _place(labels.modal_title,Rect2(mx+20,my+25,mw-40,62),modal)
 labels.modal_title.add_theme_font_size_override("font_size",30 if portrait else 38)
 _place(labels.modal_subtitle,Rect2(mx+20,my+87,mw-40,24),modal)
 _place(labels.modal_body,Rect2(mx+30,my+125,mw-60,112 if portrait else 92),modal)
 _place(labels.modal_tip,Rect2(mx+30,my+238,mw-60,100),modal)
 _place(labels.modal_footer,Rect2(mx+20,my+mh-36,mw-40,20),modal)
 var button_y := my+mh-96
 _place(controls.start,Rect2(mx+30,button_y,mw-60,48),intro)
 _place(controls.resume,Rect2(mx+30,button_y,(mw-72)/2,48),paused and not intro and not confirming and not help_open and not ended)
 if paused and not intro and not confirming and not help_open and not ended:
  _place(controls.restart,Rect2(mx+42+(mw-72)/2,button_y,(mw-72)/2,48))
 _place(controls.confirm_restart,Rect2(mx+30,button_y,(mw-72)/2,48),confirming or ended)
 _place(controls.cancel,Rect2(mx+42+(mw-72)/2,button_y,(mw-72)/2,48),confirming or help_open)
 if ended: _place(controls.confirm_restart,Rect2(mx+30,button_y,mw-60,48))
 if help_open: _place(controls.cancel,Rect2(mx+30,button_y,mw-60,48))
 # Modal children are always the final visual/input layer, independent of creation order.
 if modal:
  panels.modal.move_to_front()
  for key in ["modal_title","modal_subtitle","modal_body","modal_tip","modal_footer"]: labels[key].move_to_front()
  for key in ["start","resume","restart","confirm_restart","cancel"]: controls[key].move_to_front()
 _refresh()
 queue_redraw()

func _refresh() -> void:
 if labels.is_empty(): return
 labels.title.text = text("title")
 labels.chapter.text = text("chapter")
 var wave: int = int(state.get("wave",0))
 var gold: int = int(state.get("gold",420))
 var core: int = int(state.get("core_hp",20))
 labels.stats.text = ("%s %d   ·   %s %d   ·   %s %d/8" % [text("core"),core,text("gold"),gold,text("wave"),wave]) if not portrait else ("%s %d  |  %d G  |  %d/8" % [text("core"),core,gold,wave])
 labels.stats.add_theme_font_size_override("font_size",13 if portrait else 17)
 var hero: Dictionary = state.get("hero",{})
 labels.hero.text = text("hero")+((" · "+text("respawn")+" %.1fs"%float(hero.get("respawn",0))) if hero.get("dead",false) else "")
 labels.hero_stats.text = "%s %d    %s %d    XP %d / %d" % [text("level"),hero.get("level",1),text("damage"),hero.get("damage",32),hero.get("xp",0),hero.get("xp_next",70)]
 labels.hero_stats.add_theme_font_size_override("font_size",12 if portrait else 14)
 labels.hero_health.text = "%s  %d / %d" % [text("health"),hero.get("hp",240),hero.get("max_hp",240)]
 var mode: String = str(state.get("mode","build"))
 var active := mode in ["wave","combat","playing"]
 labels.wave_status.text = text("in_wave") if active else text("prepare")
 var boss:Dictionary=state.get("boss",{})
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
  if portrait:skill_name=(["斩击","振奋","星落"][i] if language=="zh" else ["CLEAVE","RALLY","NOVA"][i])
  if portrait and not unlocked:suffix="Lv3"
  controls["skill_"+str(i+1)].text = key.to_upper()+"\n"+skill_name+"\n"+suffix
  controls["skill_"+str(i+1)].add_theme_font_size_override("font_size",12 if portrait else 14)
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
  controls["item_"+key].text = "%s   ·   %d G\n%s" % [text(key),cost,text(key+"_tip")]
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
 var upgrades:Array=selected.get("upgrades",[])
 for i in range(2):
  var b:Button=controls.upgrade if i==0 else controls.upgrade_b
  if upgrades.size()>i:
   var option:Dictionary=upgrades[i]
   b.text=text(str(option.get("key","branch_a")))+" · %d G"%int(option.get("cost",0))
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
 labels.modal_tip.text=(text("touch_controls") if portrait else text("controls")+"\n\n"+text("intro_tip")) if intro or help_open else text("intro_tip")
 labels.modal_footer.text=text("saved_tip")

func ui_snapshot() -> Dictionary:
 var result: Dictionary = {}
 var modal := intro or confirming or help_open or bool(state.get("paused",false)) or str(state.get("mode","")) in ["victory","defeat","won","lost"]
 for key: String in controls:
  var button: Button = controls[key]
  if not button.visible: continue
  if modal and key not in ["start","resume","restart","confirm_restart","cancel","language","mute"]: continue
  var r := button.get_global_rect()
  result[key]={"x":r.position.x,"y":r.position.y,"w":r.size.x,"h":r.size.y,"enabled":not button.disabled}
 var rendered: Array[String]=[]
 for l: Label in labels.values():
  if l.visible: rendered.append(l.text)
 for b: Button in controls.values():
  if b.visible: rendered.append(b.text)
 return {"controls":result,"labels":rendered,"portrait":portrait,"intro":intro,"shop":shop,"minimap":{"x":minimap_rect.position.x,"y":minimap_rect.position.y,"w":minimap_rect.size.x,"h":minimap_rect.size.y}}

func blocks_world(point: Vector2) -> bool:
 if intro or confirming or help_open or bool(state.get("paused",false)): return true
 for p: Panel in panels.values():
  if p.visible and p.get_global_rect().has_point(point): return true
 for b: Button in controls.values():
  if b.visible and b.get_global_rect().has_point(point): return true
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
 var hero: Dictionary=state.get("hero",{})
 var p: Panel=panels.hero_panel
 var hp := float(hero.get("hp",240))/maxf(1,float(hero.get("max_hp",240)))
 var bar := Rect2(p.position.x+12,p.position.y+p.size.y-8,p.size.x-24,3)
 draw_rect(bar,Color(.1,.2,.2))
 bar.size.x *= hp
 draw_rect(bar,TEAL)
 var boss:Dictionary=state.get("boss",{})
 if not boss.is_empty() and panels.boss_panel.visible:
  var r:Rect2=panels.boss_panel.get_rect()
  var health_bar:=Rect2(r.position.x+12,r.position.y+32,r.size.x-24,4)
  draw_rect(health_bar,Color(.22,.08,.12))
  health_bar.size.x*=float(boss.get("hp",0))/maxf(1,float(boss.get("max_hp",1)))
  draw_rect(health_bar,Color("e5748c"))
 # Original compass emblem anchors the HUD without a third-party image.
 if not portrait:
  var center := Vector2(40,44)
  draw_arc(center,10,0,TAU,30,GOLD,1.4,true)
