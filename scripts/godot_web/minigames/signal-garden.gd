extends Node2D
# Signal Garden: original compact rotating-network puzzle. All art is native drawing.
const SLUG = "signal-garden"
const TITLES = ["SIGNAL GARDEN", "信号花园"]
const DIRS = [Vector2i(0,-1),Vector2i(1,0),Vector2i(0,1),Vector2i(-1,0)]
const GREEN = Color("a5f4b0")
const INK = Color("ecf5d9")
const DIM = Color("719487")
const BG = Color("0b201c")
const FLOWER = Color("ffb0ce")
# Authored spanning paths; no random generation or unverified unsolvable boards.
const PATHS = [
 [0,1,2,3,7,6,5,4,8,9,10,11,15,14,13,12],
 [0,4,8,12,13,9,5,1,2,6,10,14,15,11,7,3],
 [0,1,5,4,8,12,13,14,10,9,6,2,3,7,11,15]
]
# Third path uses an additional branch at 9->5, so every adjacent edge is explicit.
const EDGES3 = [[0,1],[1,5],[5,4],[4,8],[8,12],[12,13],[13,14],[14,10],[10,9],[9,5],[5,6],[6,2],[2,3],[3,7],[7,11],[11,15]]
var zh = false
var mobile = false
var dims = Vector2(1120,780)
var origin = Vector2(330,170)
var cell = 118.0
var font: Font
var clock_time = 0.0
var publish_clock = 0.0
var level = 0
var turns = 0
var selected = 0
var masks = []
var initial = []
var solved = []
var powered = []
var growth = []
var history = []
var won = false
var paused = false
var muted = false
var elapsed = 0.0
var bloom_time = 0.0
var started = false
var status = "ready"
var sparks = []
var tones = []
var players = []
var buttons = {}
var js_callback
var save_status = "ready"

func _ready():
	Engine.max_fps=30
	var args = OS.get_cmdline_user_args()
	zh = "--lang=zh" in args
	muted = "--muted" in args
	mobile = "--mobile-layout" in args
	font = load("res://garden-font.otf")
	if mobile:
		dims=Vector2(720,1100);origin=Vector2(56,294);cell=152.0
	get_window().content_scale_size=Vector2i(dims)
	get_window().content_scale_mode=Window.CONTENT_SCALE_MODE_CANVAS_ITEMS
	get_window().content_scale_aspect=Window.CONTENT_SCALE_ASPECT_EXPAND
	_prepare_sound()
	_new_level(0)
	if OS.has_feature("web"):
		js_callback=JavaScriptBridge.create_callback(_web_command)
		JavaScriptBridge.get_interface("window").showcaseCommand=js_callback
	_publish()
	if "--logic-test" in args:
		_logic_test()

func tr2(en, cn): return cn if zh else en
func _rect(x,y,w,h): return Rect2(x,y,w,h)
func _panel(r, color, radius=18.0, border=Color.TRANSPARENT):
	var s=StyleBoxFlat.new();s.bg_color=color
	s.set_corner_radius_all(int(radius))
	if border.a>0:s.border_color=border;s.set_border_width_all(2)
	draw_style_box(s,r)
func _text(p,text,size=24,color=INK): draw_string(font,p,str(text),HORIZONTAL_ALIGNMENT_LEFT,-1,size,color)
func _center(p,text,size=24,color=INK):
	var w=font.get_string_size(str(text),HORIZONTAL_ALIGNMENT_LEFT,-1,size).x
	_text(p-Vector2(w/2,0),text,size,color)
func _button(key,r,text,enabled=true):
	buttons[key]=r
	_panel(r,Color("214a3d") if enabled else Color("122d27"),14,GREEN if key=="next" and won else Color("416657"))
	_center(r.get_center()+Vector2(0,10),text,28 if mobile else 21,INK if enabled else DIM)
func _rotate_mask(mask): return ((int(mask)<<1)&15)|(int(mask)>>3)
func _new_level(n):
	level=n%3;turns=0;elapsed=0;won=false;paused=false;selected=0;history.clear();sparks.clear()
	solved.assign([0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0])
	if level==2:
		for edge in EDGES3:_edge(edge[0],edge[1])
	else:
		for k in range(15):_edge(PATHS[level][k],PATHS[level][k+1])
	masks=solved.duplicate()
	for i in range(16):
		var rotations=(i*7+level*3+1)%4
		for j in range(rotations):masks[i]=_rotate_mask(masks[i])
	initial=masks.duplicate();growth.assign([0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.,0.]);_connect();save_status="ready"
func _edge(a,b):
	var diff=Vector2i(b%4-a%4,int(b/4)-int(a/4))
	var d=DIRS.find(diff)
	assert(d>=0,"Authored edge must be orthogonally adjacent")
	solved[a]=int(solved[a])|(1<<d);solved[b]=int(solved[b])|(1<<((d+2)%4))
func _connect():
	var previous=powered.duplicate()
	powered.assign([false,false,false,false,false,false,false,false,false,false,false,false,false,false,false,false])
	powered[0]=true;var queue=[0]
	while not queue.is_empty():
		var i=queue.pop_front();var xy=Vector2i(i%4,int(i/4))
		for d in range(4):
			if not (int(masks[i])&(1<<d)):continue
			var p=xy+DIRS[d]
			if p.x<0 or p.x>3 or p.y<0 or p.y>3:continue
			var j=p.y*4+p.x
			if int(masks[j])&(1<<((d+2)%4)) and not powered[j]:powered[j]=true;queue.append(j)
	for i in range(16):
		if not powered[i] or (previous.size()==16 and not previous[i]):growth[i]=0.0
	var all_lit=powered.count(true)==16
	if all_lit and not won:won=true;bloom_time=clock_time;_chime(3);status="won"
	_publish();queue_redraw()
func _turn(i):
	if won or paused:return
	started=true;history.append(masks.duplicate());selected=i;turns+=1
	masks[i]=_rotate_mask(masks[i]);_connect();_chime(i%3)
	var p=origin+Vector2(i%4+0.5,int(i/4)+0.5)*cell
	for j in range(7):sparks.append({"p":p,"v":Vector2.from_angle(j*TAU/7)*75,"life":0.7})
func _undo():
	if history.is_empty() or paused:return
	masks=history.pop_back();turns=maxi(0,turns-1);won=false;_connect();_chime(0)
func _action(key):
	match key:
		"reset":_new_level(level)
		"undo":_undo()
		"next":
			if won:_new_level(level+1)
		"pause":paused=true;_publish()
		"resume":paused=false;_publish()
		"toggle":paused=not paused;_publish()
		"sound-on":muted=false;_publish()
		"sound-off":muted=true;_publish()
		"mute":muted=not muted;_publish()
		"start":started=true;_publish()
		"language":zh=not zh
		"save":_save()
		"load":_load_save()
	queue_redraw()
func _unhandled_input(event):
	if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT:
		for key in buttons:
			if buttons[key].has_point(event.position):_action(key);get_viewport().set_input_as_handled();return
		if not paused:
			var q=(event.position-origin)/cell
			if q.x>=0 and q.x<4 and q.y>=0 and q.y<4:_turn(int(q.y)*4+int(q.x))
	elif event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_TAB:selected=(selected+1)%16
			KEY_LEFT:selected=int(selected/4)*4+(selected+3)%4
			KEY_RIGHT:selected=int(selected/4)*4+(selected+1)%4
			KEY_UP:selected=(selected+12)%16
			KEY_DOWN:selected=(selected+4)%16
			KEY_SPACE,KEY_ENTER:_turn(selected)
			KEY_R:_action("reset")
			KEY_Z:_action("undo")
			KEY_N:_action("next")
			KEY_P,KEY_ESCAPE:_action("toggle")
			KEY_M:_action("mute")
			KEY_S:_action("save")
			KEY_L:_action("load")
		_publish();queue_redraw();get_viewport().set_input_as_handled()
func _process(delta):
	clock_time+=delta
	for i in range(growth.size()):
		if powered[i]:growth[i]=minf(1.0,growth[i]+delta*2.6)
	if started and not won and not paused:elapsed+=delta
	for s in sparks:s.life-=delta;s.p+=s.v*delta;s.v*=0.94
	sparks=sparks.filter(func(s):return s.life>0)
	publish_clock+=delta
	if publish_clock>0.2:publish_clock=0;_publish()
	queue_redraw()
func _draw():
	if not font:return
	buttons.clear();draw_rect(Rect2(Vector2.ZERO,dims),BG)
	for i in range(30):
		var p=Vector2(fmod(i*173.7+sin(clock_time*0.13+i)*18,dims.x),fmod(i*91.3+cos(clock_time*0.19+i)*15,dims.y))
		draw_circle(p,1.3+0.7*sin(clock_time+i),Color(0.6,0.9,0.5,0.14))
	var title_size=44 if mobile else 43
	_text(Vector2(40,70),TITLES[1] if zh else TITLES[0],title_size)
	_text(Vector2(42,108),tr2("A LITTLE NETWORK. A LIVING GARDEN.","转动小小的网络，点亮整座花园。"),21,DIM)
	_button("language",Rect2(dims.x-(174 if mobile else 132),18 if mobile else 28,132 if mobile else 96,108 if mobile else 48),"EN" if zh else "中文")
	if mobile:
		_text(Vector2(42,173),tr2("BED %d / 3"%[level+1],"花圃 %d / 3"%[level+1]),28,GREEN)
		_text(Vector2(42,219),tr2("%d / 16 LIT   ·   %d TURNS"%[powered.count(true),turns],"已点亮 %d / 16   ·   转动 %d 次"%[powered.count(true),turns]),27)
		_text(Vector2(42,260),tr2("Tap a tile to turn its branches.","轻触方块，顺时针转动枝条。"),25,DIM)
	else:
		_text(Vector2(42,202),tr2("BED %02d"%[level+1],"花圃 %02d"%[level+1]),34,GREEN)
		_text(Vector2(42,256),tr2("%d / 16 LIT"%powered.count(true),"已点亮 %d / 16"%powered.count(true)),28)
		_text(Vector2(42,299),tr2("%d TURNS"%turns,"转动 %d 次"%turns),25,DIM)
		_text(Vector2(42,378),tr2("ROTATE THE BRANCHES", "转动枝条"),20,INK)
		_text(Vector2(42,415),tr2("Grow one connected garden.","让所有枝条连接成一体。"),19,DIM)
		_text(Vector2(42,448),tr2("Begin at the golden seed.","从金色种子出发。"),19,DIM)
		_text(Vector2(42,510),tr2("Click / Space   Rotate", "点击 / 空格  转动"),19,DIM)
		_text(Vector2(42,540),tr2("Arrows   Select tile", "方向键  选择方块"),19,DIM)
		_text(Vector2(42,570),tr2("Z   Undo    R   Reset", "Z 撤销    R 重置"),19,DIM)
	_panel(Rect2(origin-Vector2(10,10),Vector2.ONE*(cell*4+20)),Color("102b24"),24,Color("244a3d"))
	for i in range(16):_draw_tile(i)
	for s in sparks:draw_circle(s.p,3.0,Color(GREEN,s.life))
	var y=934 if mobile else 682
	var x=42 if mobile else 330
	var w=144 if mobile else 110
	_button("undo",Rect2(x,y,w,108 if mobile else 60),tr2("Undo","撤销"),not history.is_empty())
	_button("reset",Rect2(x+w+14,y,w,108 if mobile else 60),tr2("Reset","重置"))
	_button("toggle",Rect2(x+(w+14)*2,y,w,108 if mobile else 60),tr2("Resume" if paused else "Pause","继续" if paused else "暂停"))
	_button("mute",Rect2(x+(w+14)*3,y,w,108 if mobile else 60),tr2("Sound" if muted else "Mute","开启声音" if muted else "静音"))
	_center(Vector2(dims.x/2,dims.y-(15 if mobile else 12)),tr2("NO CLOCK TO RACE. FOLLOW THE LIGHT.","不必赶时间，跟随光的方向。"),20,DIM)
	if (won and clock_time-bloom_time>0.65) or paused:
		var r=Rect2(origin+Vector2(14,cell*1.18),Vector2(cell*4-28,cell*1.6))
		_panel(r,Color("ecf5d9"),20)
		_center(Vector2(r.get_center().x,r.position.y+54),tr2("GARDEN AWAKE" if won else "TAKE A BREATH","花园醒来了" if won else "休息一下"),36,BG)
		_center(Vector2(r.get_center().x,r.position.y+96),tr2("Every little light is connected." if won else "Your garden will wait.","每一道微光都已相连。" if won else "花园会在这里等你。"),22,Color("37634d"))
		_button("next" if won else "toggle",Rect2(r.get_center().x-130,r.position.y+116,260,108 if mobile else 58),tr2("Next garden" if won else "Continue","下一座花园" if won else "继续"))
func _draw_tile(i):
	var r=Rect2(origin+Vector2(i%4,int(i/4))*cell+Vector2(4,4),Vector2.ONE*(cell-8))
	var p=r.get_center();var live=powered[i]
	_panel(r,Color("19392d") if live else Color("112c25"),16,GREEN if selected==i else Color("2a4f3e"))
	var color=GREEN if live else Color("4a7060")
	var bloom=smoothstep(0.0,1.0,growth[i])
	for d in range(4):
		if int(masks[i])&(1<<d):
			var end=p+Vector2(DIRS[d])*cell*0.49
			draw_line(p,end,Color("4a7060"),5,true)
			if live:draw_line(p,p.lerp(end,bloom),Color(color,0.15),18,true);draw_line(p,p.lerp(end,bloom),color,5,true)
			if live:
				var a=fmod(clock_time*0.38+i*0.09,1)
				draw_circle(p.lerp(end,a),3.5,Color("f6f8c5"))
	draw_circle(p,10,color)
	if i==0:
		draw_circle(p,21,Color("ddae67"));draw_circle(p,13,Color("ffe4a1"));draw_arc(p,27,clock_time,clock_time+4.4,24,Color("ffe4a1"),2,true)
	elif i in [3,12,15]:
		for j in range(5):draw_circle(p+Vector2.from_angle(j*TAU/5-clock_time*0.1)*lerpf(4,14,bloom),lerpf(5,9,bloom),FLOWER if live else Color("725268"))
		draw_circle(p,8,Color("ffe4a1") if live else DIM)

func _prepare_sound():
	# Original offline-generated PCM blips, three overtones with raised-cosine edges.
	for hz in [261.63,329.63,392.0,523.25]:
		var data=PackedByteArray();var n=11025
		data.resize(n*2)
		for i in range(n):
			var t=float(i)/44100;var env=sin(PI*float(i)/n)*exp(-t*9)
			var v=(sin(TAU*hz*t)+0.25*sin(TAU*hz*2*t))*env*0.15
			data.encode_s16(i*2,int(v*32767))
		var sound=AudioStreamWAV.new();sound.format=AudioStreamWAV.FORMAT_16_BITS;sound.mix_rate=44100;sound.data=data;tones.append(sound)
		var player=AudioStreamPlayer.new();player.stream=sound;player.max_polyphony=1;player.volume_db=-8;add_child(player);players.append(player)
func _chime(i):
	if not muted:players[i%4].play()
func _save():
	if OS.has_feature("web") and not OS.is_userfs_persistent():save_status="save_failed";_publish();return
	var f=FileAccess.open("user://signal-garden.json",FileAccess.WRITE)
	if f:f.store_string(JSON.stringify({"level":level,"masks":masks,"turns":turns}));f.close();save_status="saved"
	else:save_status="save_failed"
	_publish()
func _load_save():
	if not FileAccess.file_exists("user://signal-garden.json"):save_status="no_save";_publish();return
	var d=JSON.parse_string(FileAccess.get_file_as_string("user://signal-garden.json"))
	if not d is Dictionary or not d.get("masks") is Array or d.masks.size()!=16:save_status="invalid_save";_publish();return
	var saved_level=d.get("level")
	if not (saved_level is float or saved_level is int) or float(int(saved_level))!=float(saved_level) or saved_level<0 or saved_level>2:save_status="invalid_save";_publish();return
	for v in d.masks:
		if not (v is int or v is float) or int(v)!=v or v<1 or v>15:save_status="invalid_save";_publish();return
	_new_level(int(d.level));masks=d.masks.map(func(v):return int(v));turns=clampi(int(d.get("turns",0)),0,10000);_connect();save_status="loaded";_publish()
func _web_command(args):
	if args.size()>0:_action(str(args[0]))
func state():
	var target_state={}
	for key in buttons:
		var r=buttons[key];target_state[key]={"x":r.position.x,"y":r.position.y,"width":r.size.x,"height":r.size.y}
	return {"case":SLUG,"level":level+1,"moves":turns,"selected":selected,"won":won,"paused":paused,"muted":muted,"started":started,"lit":powered.count(true),"masks":masks,"powered":powered,"status":save_status,"persistent":OS.is_userfs_persistent(),"layout_width":dims.x,"layout_height":dims.y,"layout_size":[dims.x,dims.y],"mobile_layout":mobile,"language":"zh" if zh else "en","board":{"x":origin.x,"y":origin.y,"cell":cell,"size":4},"minimum_text_size":20,"native_targets":target_state}
func _publish():
	if OS.has_feature("web"):
		JavaScriptBridge.eval("window.showcaseReceive && window.showcaseReceive("+JSON.stringify(JSON.stringify(state()))+");")
func _logic_test():
	for n in range(3):
		_new_level(n);assert(not won);var before=masks.duplicate();_turn(0);assert(turns==1);_undo();assert(masks==before)
		masks=solved.duplicate();_connect();assert(won and powered.count(true)==16)
		_new_level(n);assert(not won and turns==0)
		_turn(2);var saved_masks=masks.duplicate();_save();assert(save_status=="saved")
		_new_level(n);_load_save();assert(save_status=="loaded" and masks==saved_masks and turns==1)
	print("SIGNAL_GARDEN_LOGIC_PASS: 3 authored connected gardens; rotate, undo, win, reset")
	get_tree().quit()
