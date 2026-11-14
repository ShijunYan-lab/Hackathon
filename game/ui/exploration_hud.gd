extends CanvasLayer
var world: Node2D
var map_open := false
var dialog_open := false
var dialog_title := ""
var dialog_text := ""
var discovered_ruins := false
var canvas: Control
var font: SystemFont
var map_texture: Texture2D
var previous_zone := ""
var zone_timer := 4.0
var elapsed := 0.0
const INK := Color("172729")
const GOLD := Color("c4ad7c")
const PAPER := Color("e3dcc2")
const MUTED := Color("a0b3a3")

func _ready() -> void:
	layer=10
	font=SystemFont.new()
	font.font_names=PackedStringArray(["Microsoft YaHei","Noto Sans CJK SC","sans-serif"])
	font.antialiasing=TextServer.FONT_ANTIALIASING_GRAY
	map_texture=load("res://maps/world_chart.png")
	canvas=Control.new()
	canvas.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	canvas.mouse_filter=Control.MOUSE_FILTER_IGNORE
	canvas.draw.connect(_draw_hud)
	add_child(canvas)

func _process(delta: float) -> void:
	elapsed+=delta
	zone_timer=maxf(0,zone_timer-delta)
	var current:=zone_name()
	if current!=previous_zone:
		previous_zone=current
		zone_timer=3.5
	if world.player.position.distance_to(Vector2(117,29)*32)<160: discovered_ruins=true
	canvas.queue_redraw()

func zone_name() -> String:
	var p: Vector2 = world.player.position/32
	if p.y<56:
		if p.distance_to(Vector2(117,29))<10: return "月隐遗迹"
		return "翠影密林" if p.x<80 else "月隐之森"
	if p.distance_to(Vector2(30,81))<18: return "炉溪村"
	if p.x>98: return "苇湾村"
	if absf(p.x-78)<9: return "苇溪河畔"
	return "旧王国原野"

func text(at: Vector2,value: String,size: int=12,color: Color=PAPER) -> void:
	canvas.draw_string(font,at,value,HORIZONTAL_ALIGNMENT_LEFT,-1,size,color)

func panel(r: Rect2, color: Color=INK) -> void:
	canvas.draw_rect(Rect2(r.position+Vector2(2,3),r.size),Color(0.02,0.06,0.07,0.45))
	canvas.draw_rect(r,color)
	canvas.draw_rect(r,GOLD.darkened(0.4),false,1)
	for p in [r.position,r.position+Vector2(r.size.x-3,0),r.end-Vector2(3,3),r.position+Vector2(0,r.size.y-3)]: canvas.draw_rect(Rect2(p,Vector2(3,3)),GOLD)

func _draw_hud() -> void:
	var size:=canvas.get_viewport_rect().size
	panel(Rect2(12,12,176,49))
	text(Vector2(23,29),"未定之境",13,GOLD)
	text(Vector2(23,49),zone_name(),15)
	text(Vector2(118,29),"旅途 · 01",9,MUTED)
	# Fine compass and time-of-day ornament.
	var c:=Vector2(size.x-31,34)
	canvas.draw_circle(c,16,INK)
	canvas.draw_arc(c,16,0,TAU,32,GOLD.darkened(0.3),1)
	canvas.draw_colored_polygon(PackedVector2Array([c+Vector2(0,-12),c+Vector2(-4,4),c+Vector2(0,1),c+Vector2(4,4)]),GOLD)
	text(c+Vector2(-4,-20),"N",9,GOLD)
	text(Vector2(size.x-117,22),"薄暮 / 晴",10,PAPER)
	text(Vector2(size.x-117,37),"探索模式",9,MUTED)
	# Footprint-scale controls leave the landscape in focus.
	panel(Rect2(12,size.y-29,324,18))
	text(Vector2(20,size.y-16),"WASD 移动   Shift 奔跑   E 查看   M 地图   V 换角色",10)
	var sight:=int(world.fog.radius/32)
	text(Vector2(size.x-114,size.y-16),"视野 %d 格  ·  32×48"%sight,9,MUTED)
	if world.interactable and not dialog_open and not map_open:
		var title:=str(world.interactable.get_meta("title"))
		var w:=font.get_string_size("E  "+title,HORIZONTAL_ALIGNMENT_LEFT,-1,11).x+20
		panel(Rect2(size.x/2-w/2,size.y-61,w,22))
		text(Vector2(size.x/2-w/2+10,size.y-46),"E  "+title,11)
	if zone_timer>0 and not map_open and not dialog_open:
		var a:=minf(1,zone_timer)*0.9
		var title:=zone_name()
		var w:=font.get_string_size(title,HORIZONTAL_ALIGNMENT_LEFT,-1,19).x
		text(Vector2(size.x/2-w/2,82),title,19,Color(PAPER,a))
		canvas.draw_line(Vector2(size.x/2-44,91),Vector2(size.x/2+44,91),Color(GOLD,a),1)
	if map_open: draw_map(size)
	if dialog_open:
		panel(Rect2(100,size.y-119,size.x-200,78))
		text(Vector2(115,size.y-98),dialog_title,14,GOLD)
		text(Vector2(115,size.y-77),dialog_text,11)
		text(Vector2(size.x-198,size.y-52),"E / Esc  收起",10,MUTED)

func draw_map(size: Vector2) -> void:
	canvas.draw_rect(Rect2(Vector2.ZERO,size),Color(0.03,0.08,0.09,0.8))
	var box:=Rect2(size/2-Vector2(274,165),Vector2(548,330))
	panel(box,Color("263735"))
	text(box.position+Vector2(17,24),"苇溪流域  /  旅人手札",16,GOLD)
	text(box.position+Vector2(411,23),"M / Esc  收起",10,MUTED)
	var origin:=box.position+Vector2(24,43)
	var scale:=2.35
	canvas.draw_texture_rect(map_texture,Rect2(origin,Vector2(160,112)*scale),false,Color("ced3aa"))
	canvas.draw_rect(Rect2(origin,Vector2(160,112)*scale),GOLD.darkened(0.3),false,1)
	var labels: Array = [[Vector2(30,81),"炉溪村"],[Vector2(119,80),"苇湾村"],[Vector2(35,25),"翠影密林"],[Vector2(112,12),"月隐之森"]]
	if discovered_ruins: labels.append([Vector2(117,29),"月隐遗迹"])
	for entry in labels:
		var p: Vector2=origin+entry[0]*scale
		text(p+Vector2(-18,-7),entry[1],10,Color("101f21"))
		text(p+Vector2(-19,-8),entry[1],10,PAPER)
	var p: Vector2=origin+world.player.position/32*scale
	canvas.draw_circle(p,4,INK)
	canvas.draw_circle(p,2,GOLD)
	var side:=origin+Vector2(393,15)
	text(side,"N",13,GOLD)
	text(side+Vector2(0,31),"北境无路",12)
	text(side+Vector2(0,49),"密林遮蔽视线",10,MUTED)
	text(side+Vector2(0,85),"双桥通商",12)
	text(side+Vector2(0,103),"北路 · 南路",10,MUTED)
	text(side+Vector2(0,139),"●  当前位置",10,GOLD)
	text(side+Vector2(0,181),"徒步探索",12)
	text(side+Vector2(0,199),"没有快速传送",10,MUTED)
	text(side+Vector2(0,235),"160 × 112 格",10,MUTED)

func show_place(title: String,description: String) -> void:
	dialog_title=title
	dialog_text=description
	dialog_open=true
