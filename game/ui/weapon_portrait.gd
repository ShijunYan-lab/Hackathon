extends Control
## Hand-drawn native Godot pixel illustrations, independent of tiny world icons.
var kind:="sword"
const OUT=Color("16131b")
const STEEL=Color("718191")
const EDGE=Color("e1e5d5")
const GOLD=Color("b49b63")
const WOOD=Color("6b4938")
func show_weapon(value:String)->void:
	kind=value
	queue_redraw()
func rect(x:float,y:float,w:float,h:float,c:Color)->void: draw_rect(Rect2(x,y,w,h),c)
func poly(points:Array,c:Color)->void: draw_colored_polygon(PackedVector2Array(points),c)
func shaft(x:float,y:float,w:float,h:float)->void:
	rect(x-2,y-2,w+4,h+4,OUT)
	rect(x,y,w,h,WOOD)
	rect(x,y,2,h,Color("b68a5b"))
	for offset in range(6,int(h),8): rect(x,y+offset,w,2,Color("3b2c2c"))
func _draw()->void:
	draw_rect(Rect2(Vector2.ZERO,size),Color("19191b"))
	draw_rect(Rect2(Vector2.ZERO,size),Color("776246"),false,1)
	var scale_factor:=minf(size.x/128,size.y/160)
	draw_set_transform((size-Vector2(128,160)*scale_factor)/2,0,Vector2.ONE*scale_factor)
	for i in range(10): rect(11+i*11,12,1,136,Color("211f22"))
	draw_arc(Vector2(64,79),48,0,TAU,48,Color("38312f"),1,false)
	draw_arc(Vector2(64,79),43,0,TAU,48,Color("29272a"),1,false)
	match kind:
		"sword":
			poly([Vector2(64,16),Vector2(73,35),Vector2(71,104),Vector2(57,104),Vector2(55,35)],OUT)
			poly([Vector2(64,20),Vector2(70,36),Vector2(68,102),Vector2(60,102),Vector2(58,36)],STEEL)
			poly([Vector2(64,20),Vector2(64,101),Vector2(60,101),Vector2(58,36)],EDGE)
			rect(64,34,2,61,Color("b7c7cb"))
			shaft(60,106,8,24)
			rect(43,101,42,7,OUT); rect(45,102,38,4,GOLD)
			rect(60,130,8,8,OUT);rect(61,131,6,5,GOLD)
		"axe":
			shaft(61,35,8,103)
			poly([Vector2(49,28),Vector2(91,23),Vector2(104,42),Vector2(102,66),Vector2(87,84),Vector2(70,69),Vector2(49,66)],OUT)
			poly([Vector2(51,32),Vector2(88,28),Vector2(99,43),Vector2(96,64),Vector2(86,77),Vector2(72,65),Vector2(51,62)],STEEL)
			poly([Vector2(88,28),Vector2(99,43),Vector2(96,64),Vector2(86,77),Vector2(91,56),Vector2(92,39)],EDGE)
			rect(54,44,22,8,GOLD);rect(61,45,7,6,Color("554738"))
		"hammer":
			shaft(60,64,9,73)
			rect(28,30,72,37,OUT);rect(32,34,64,29,STEEL)
			rect(32,34,64,5,EDGE);rect(35,40,10,18,Color("a5b4bb"))
			rect(84,39,9,24,Color("424959"));rect(57,32,15,33,GOLD)
			for x in [39,87]: rect(x,47,3,3,Color("d5c8aa"))
		"bow":
			var bow:=PackedVector2Array([Vector2(79,20),Vector2(60,28),Vector2(45,45),Vector2(35,76),Vector2(45,109),Vector2(60,127),Vector2(79,138)])
			draw_polyline(bow,OUT,9,false);draw_polyline(bow,WOOD,5,false);draw_polyline(bow,Color("b9925f"),2,false)
			draw_line(Vector2(79,20),Vector2(79,138),Color("cfbea1"),1,false)
			shaft(32,65,7,25)
			draw_line(Vector2(28,79),Vector2(103,79),Color("d0b68e"),2,false)
			poly([Vector2(110,79),Vector2(100,75),Vector2(100,83)],EDGE)
		"crossbow":
			shaft(58,48,12,91)
			var limbs:=PackedVector2Array([Vector2(19,72),Vector2(29,51),Vector2(48,40),Vector2(80,40),Vector2(99,51),Vector2(109,72)])
			draw_polyline(limbs,OUT,9,false);draw_polyline(limbs,STEEL,5,false)
			draw_line(Vector2(19,72),Vector2(109,72),EDGE,1,false)
			rect(56,68,16,12,GOLD);rect(62,28,3,58,EDGE)
			poly([Vector2(63,20),Vector2(58,32),Vector2(68,32)],STEEL)
		"staff":
			shaft(61,55,8,83)
			poly([Vector2(64,15),Vector2(84,37),Vector2(74,61),Vector2(54,61),Vector2(44,37)],OUT)
			poly([Vector2(64,20),Vector2(79,38),Vector2(70,56),Vector2(58,56),Vector2(49,38)],Color("8956ac"))
			poly([Vector2(64,20),Vector2(64,54),Vector2(53,38)],Color("d8b6ee"))
			poly([Vector2(64,20),Vector2(79,38),Vector2(64,54)],Color("643a91"))
			rect(53,57,22,6,GOLD);rect(58,92,14,4,GOLD)
			for p in [Vector2(35,27),Vector2(93,49),Vector2(84,12)]:
				draw_line(p-Vector2(3,0),p+Vector2(3,0),Color("d9b0f2"),1);draw_line(p-Vector2(0,3),p+Vector2(0,3),Color("d9b0f2"),1)
		_:
			rect(44,60,40,42,WOOD);rect(46,62,36,38,GOLD)
	draw_set_transform(Vector2.ZERO)
