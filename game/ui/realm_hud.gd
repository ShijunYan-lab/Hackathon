extends CanvasLayer
signal chat_submitted(npc_id:String,text:String)
const Layout=preload("res://maps/world_layout.gd")
const INK:=Color("231f1d")
const GOLD:=Color("b79864")
const PAPER:=Color("ddd0ac")
const MUTED:=Color("a79b7e")
var world:Node2D
var map_open:=false
var dialog_open:=false
var canvas:Control
var font:SystemFont
var chart:Texture2D
var dialogue:Control
var transcript:RichTextLabel
var entry:LineEdit
var send_button:Button
var topic_buttons:Array[Button]=[]
var current_npc:Node2D
var current_place:Node2D
var title:=""
var role:=""
var last_zone:=""
var zone_timer:=0.0
var visited:Dictionary={}
var message_count:=0

func _ready()->void:
	layer=10
	font=SystemFont.new()
	font.font_names=PackedStringArray(["Microsoft YaHei","Noto Sans CJK SC","sans-serif"])
	font.antialiasing=TextServer.FONT_ANTIALIASING_GRAY
	chart=load("res://maps/world_chart.png")
	canvas=Control.new()
	canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	canvas.mouse_filter=Control.MOUSE_FILTER_IGNORE
	canvas.draw.connect(draw_hud)
	add_child(canvas)
	build_dialogue()

func _process(delta:float)->void:
	var zone:String=Layout.zone_name(world.player.position)
	if zone!=last_zone:
		last_zone=zone
		zone_timer=3.0
	zone_timer=maxf(0,zone_timer-delta)
	for place in world.landmark_data:
		if world.player.position.distance_to(place.pos*32)<260: visited[place.name]=true
	dialogue.visible=dialog_open
	canvas.queue_redraw()

func text(p:Vector2,value:String,size:int=12,color:Color=PAPER)->void:
	canvas.draw_string(font,p,value,HORIZONTAL_ALIGNMENT_LEFT,-1,size,color)

func panel(r:Rect2,color:Color=INK)->void:
	canvas.draw_rect(Rect2(r.position+Vector2(3,4),r.size),Color(0.02,0.02,0.02,0.6))
	canvas.draw_rect(r,color)
	canvas.draw_rect(r,GOLD.darkened(0.42),false,1)
	canvas.draw_rect(r.grow(-3),Color("4b4031"),false,1)
	for p in [r.position,r.position+Vector2(r.size.x-7,0),r.end-Vector2(7,7),r.position+Vector2(0,r.size.y-7)]:
		canvas.draw_rect(Rect2(p,Vector2(7,7)),GOLD.darkened(0.2),false,1)
		canvas.draw_rect(Rect2(p+Vector2(2,2),Vector2(3,3)),GOLD)

func draw_hud()->void:
	var size:=canvas.get_viewport_rect().size
	panel(Rect2(14,13,191,57))
	text(Vector2(27,33),"未定之境",13,GOLD)
	text(Vector2(27,56),last_zone,17)
	text(Vector2(135,31),"南境 · 秋",10,MUTED)
	panel(Rect2(size.x-180,13,166,48))
	text(Vector2(size.x-166,33),"旅人手札",12,GOLD)
	text(Vector2(size.x-166,50),"已踏访 %d / %d 处地点"%[visited.size(),world.landmark_data.size()],10,MUTED)
	if not dialog_open:
		panel(Rect2(size.x/2-224,size.y-38,448,25))
		text(Vector2(size.x/2-210,size.y-21),"WASD / 方向键 移动     Shift 奔跑     E 交谈     M 地图     V 外观",11)
		if world.near_npc and not world.near_npc.get_meta("speech_active",false):
			var npc:Node2D=world.near_npc
			var screen:Vector2=npc.get_global_transform_with_canvas().origin
			var name_text:String="E  \u4ea4\u8c08"
			var width:=font.get_string_size(name_text,HORIZONTAL_ALIGNMENT_LEFT,-1,11).x+20
			panel(Rect2(screen+Vector2(-width/2,-89),Vector2(width,22)))
			text(screen+Vector2(-width/2+10,-74),name_text,11)
		elif world.interactable:
			var value:="E  "+str(world.interactable.get_meta("title"))
			var width:=font.get_string_size(value,HORIZONTAL_ALIGNMENT_LEFT,-1,11).x+22
			panel(Rect2(size.x/2-width/2,size.y-70,width,22))
			text(Vector2(size.x/2-width/2+11,size.y-55),value,11)
	if zone_timer>0 and not dialog_open and not map_open:
		var alpha:=minf(zone_timer,1)
		var width:=font.get_string_size(last_zone,HORIZONTAL_ALIGNMENT_LEFT,-1,20).x
		text(Vector2(size.x/2-width/2,90),last_zone,20,Color(PAPER,alpha))
		canvas.draw_line(Vector2(size.x/2-50,98),Vector2(size.x/2+50,98),Color(GOLD,alpha),1)
	if map_open: draw_map(size)
	if dialog_open: draw_dialogue_frame(size)

func draw_map(size:Vector2)->void:
	canvas.draw_rect(Rect2(Vector2.ZERO,size),Color(0.05,0.045,0.035,0.84))
	var box:=Rect2(20,18,size.x-40,size.y-36)
	panel(box,Color("302b23"))
	text(box.position+Vector2(18,27),"南境诸地   ·   旧王国行路图",17,GOLD)
	text(box.position+Vector2(box.size.x-107,25),"M / Esc  收起",11,MUTED)
	var origin:=box.position+Vector2(18,44)
	var scale:=1.48
	var map_size:=Vector2(Layout.SIZE)*scale
	canvas.draw_texture_rect(chart,Rect2(origin,map_size),false,Color("d6caa5"))
	canvas.draw_rect(Rect2(origin,map_size),GOLD.darkened(0.25),false,1)
	for place in world.landmark_data:
		var p:Vector2=origin+place.pos*scale
		canvas.draw_circle(p,3,INK)
		canvas.draw_circle(p,1.5,GOLD if visited.has(place.name) else MUTED)
		if place.kind in ["village","ruin","forest"]:
			text(p+Vector2(-18,-8),place.name,10,Color("1a221b"))
			text(p+Vector2(-19,-9),place.name,10,PAPER)
	var player_point:Vector2=origin+world.player.position/32*scale
	canvas.draw_circle(player_point,5,Color("252126"))
	canvas.draw_circle(player_point,3,Color("d7bcdd"))
	var side:=origin+Vector2(494,10)
	text(side,"N  ↑",13,GOLD)
	text(side+Vector2(0,33),"定居与荒野",15,PAPER)
	text(side+Vector2(0,56),"灰橡镇 · 鸦渡镇",11,MUTED)
	text(side+Vector2(0,79),"北桥与南桥连接商路",11,MUTED)
	text(side+Vector2(0,112),"黑枝林地没有铺设道路",11,MUTED)
	text(side+Vector2(0,135),"修道院、猎营与墓园隐于林中",10,MUTED)
	text(side+Vector2(0,179),"●  你的位置",12,Color("d7bcdd"))
	text(side+Vector2(0,212),"已踏访的地点",12,GOLD)
	var row:=0
	for value in visited:
		if row>=4: break
		text(side+Vector2(0,232+row*18),str(value),10,MUTED)
		row+=1

func build_dialogue()->void:
	dialogue=Control.new()
	dialogue.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	dialogue.mouse_filter=Control.MOUSE_FILTER_IGNORE
	dialogue.visible=false
	add_child(dialogue)
	transcript=RichTextLabel.new()
	transcript.position=Vector2(183,284)
	transcript.size=Vector2(551,81)
	transcript.add_theme_font_override("normal_font",font)
	transcript.add_theme_font_size_override("normal_font_size",12)
	transcript.add_theme_color_override("default_color",PAPER)
	transcript.bbcode_enabled=false
	transcript.scroll_following=true
	dialogue.add_child(transcript)
	for i in range(3):
		var b:=Button.new()
		b.text=["附近的传闻","谈谈你的手艺","告辞"][i]
		b.position=Vector2(184+i*183,371)
		b.size=Vector2(176,23)
		style_control(b)
		b.pressed.connect(topic.bind(i))
		dialogue.add_child(b)
		topic_buttons.append(b)
	entry=LineEdit.new()
	entry.position=Vector2(184,401)
	entry.size=Vector2(478,25)
	entry.max_length=120
	style_control(entry)
	entry.text_submitted.connect(submit_text)
	dialogue.add_child(entry)
	send_button=Button.new()
	send_button.text="发送"
	send_button.position=Vector2(668,401)
	send_button.size=Vector2(60,25)
	style_control(send_button)
	send_button.pressed.connect(func(): submit_text(entry.text))
	dialogue.add_child(send_button)

func style_control(control:Control)->void:
	control.add_theme_font_override("font",font)
	control.add_theme_font_size_override("font_size",11)
	control.add_theme_color_override("font_color",PAPER)
	var normal:=StyleBoxFlat.new()
	normal.bg_color=Color("332d23")
	normal.border_color=Color("736044")
	normal.set_border_width_all(1)
	normal.content_margin_left=8
	normal.content_margin_right=8
	var hover:=normal.duplicate() as StyleBoxFlat
	hover.bg_color=Color("504231")
	hover.border_color=GOLD
	control.add_theme_stylebox_override("normal",normal)
	control.add_theme_stylebox_override("hover",hover)
	control.add_theme_stylebox_override("focus",hover)
	control.add_theme_stylebox_override("pressed",hover)

func draw_dialogue_frame(_size:Vector2)->void:
	panel(Rect2(52,242,696,194),Color("27231e"))
	canvas.draw_line(Vector2(174,254),Vector2(174,424),Color("786342"),1)
	text(Vector2(186,269),title,17,GOLD)
	text(Vector2(374,268),role,11,MUTED)
	text(Vector2(668,268),"Esc 关闭",10,MUTED)
	panel(Rect2(68,270,92,127),Color("1d1c1b"))
	if is_instance_valid(current_npc):
		canvas.draw_texture_rect_region(current_npc.sprite.texture,Rect2(73,277,82,110),Rect2(0,0,48,64),Color.WHITE)
	elif is_instance_valid(current_place):
		var art:Sprite2D=current_place.get_node("Art")
		var dims:=art.texture.get_size()
		var factor:=minf(80/dims.x,108/dims.y)
		canvas.draw_texture_rect(art.texture,Rect2(Vector2(74,382)-Vector2(0,dims.y*factor),dims*factor),false)
	text(Vector2(87,416),"离线对白" if current_npc else "地点手札",10,MUTED)

func show_npc(npc:Node2D)->void:
	close_dialogue()
	map_open=false
	current_npc=npc
	current_place=null
	npc.set_controls_locked(true)
	title=npc.data.name
	role=npc.data.role+" · "+npc.data.place
	transcript.text=npc.data.greeting
	entry.placeholder_text="向"+title+"说点什么……"
	entry.text=""
	entry.editable=true
	send_button.disabled=false
	for b in topic_buttons: b.disabled=false
	dialog_open=true
	dialogue.show()
	world.player.set_controls_locked(true)
	entry.grab_focus()

func show_place(place:Node2D)->void:
	close_dialogue()
	current_place=place
	title=str(place.get_meta("title"))
	role="旅途见闻"
	transcript.text=str(place.get_meta("description"))
	entry.text=""
	entry.placeholder_text="这是地点记录；靠近人物可自由输入对白。"
	entry.editable=false
	send_button.disabled=true
	for i in range(2): topic_buttons[i].disabled=true
	dialog_open=true
	world.player.set_controls_locked(true)

func topic(index:int)->void:
	if index==2:
		close_dialogue()
	elif is_instance_valid(current_npc):
		submit_text("附近有什么传闻？" if index==0 else "谈谈你的工作。")

func submit_text(value:String)->void:
	if not is_instance_valid(current_npc): return
	if DisplayServer.has_feature(DisplayServer.FEATURE_IME) and DisplayServer.ime_get_text()!="": return
	value=value.strip_edges().left(120)
	if value.is_empty(): return
	transcript.add_text("\n\n你："+value+"\n"+str(current_npc.data.name)+"："+current_npc.reply_to(value))
	entry.text=""
	message_count+=1
	chat_submitted.emit(str(current_npc.data.id),value)
	entry.grab_focus()

func close_dialogue()->void:
	if is_instance_valid(current_npc): current_npc.set_controls_locked(false)
	current_npc=null
	current_place=null
	dialog_open=false
	if is_instance_valid(dialogue): dialogue.hide()
	if is_instance_valid(world.player): world.player.set_controls_locked(map_open)

func _input(event:InputEvent)->void:
	if dialog_open and event.is_action_pressed("ui_cancel"):
		close_dialogue()
		get_viewport().set_input_as_handled()
