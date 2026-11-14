extends RefCounted
## Authored settlements and points of interest on a 4x-area continuous landscape.
const SIZE:=Vector2i(320,224)
const TILE:=32
const FOREST_EDGE:=112
const SPAWN:=Vector2(56,165.5)*TILE
const REGIONS:={"market":Rect2i(0,112,320,112),"greenwood":Rect2i(0,0,160,112),"moonwood":Rect2i(160,0,160,112)}
const BUILDINGS:=["home","tavern","smith","cottage","warehouse","windmill","chapel","gatehouse","merchant"]
const EXITS:={"market":[["greenwood",Vector2(76.5,0.5),Vector2(76.5,111.5)],["moonwood",Vector2(250.5,0.5),Vector2(90.5,111.5)]],"greenwood":[["market",Vector2(76.5,111.5),Vector2(76.5,0.5)],["moonwood",Vector2(159.5,86.5),Vector2(0.5,86.5)]],"moonwood":[["market",Vector2(90.5,111.5),Vector2(250.5,0.5)],["greenwood",Vector2(0.5,86.5),Vector2(159.5,86.5)]]}
var ground:Dictionary={}
var objects:Array[Dictionary]=[]
var blocked:Dictionary={}
var reserved:Array[Rect2]=[]
var rng:=RandomNumberGenerator.new()
var routes:Array=[]
var landmarks:Array=[
	{"name":"灰橡镇","pos":Vector2(63,165),"kind":"village"},
	{"name":"鸦渡镇","pos":Vector2(246,161),"kind":"village"},
	{"name":"黑枝林地","pos":Vector2(64,65),"kind":"forest"},
	{"name":"暮钟修道院","pos":Vector2(237,46),"kind":"ruin"},
	{"name":"断誓堡","pos":Vector2(191,74),"kind":"ruin"},
	{"name":"苔石猎营","pos":Vector2(89,92),"kind":"camp"},
	{"name":"寂鸦墓园","pos":Vector2(269,100),"kind":"grave"},
	{"name":"旧王大道","pos":Vector2(142,143),"kind":"bridge"},
	{"name":"苇岸渡口","pos":Vector2(166,174),"kind":"dock"},
	{"name":"枯井驿站","pos":Vector2(116,202),"kind":"camp"},
	{"name":"风磨丘","pos":Vector2(41,191),"kind":"mill"},
	{"name":"圣烬礼拜堂","pos":Vector2(76,148),"kind":"chapel"}]

func river_x(y:float)->float: return 155+sin(y*0.035)*7+sin(y*0.09)*3

func build()->void:
	rng.seed=20261114
	var noise:=FastNoiseLite.new()
	noise.seed=713
	noise.frequency=0.036
	for y in range(SIZE.y):
		for x in range(SIZE.x):
			var cell:=Vector2i(x,y)
			var n:=noise.get_noise_2d(x,y)
			var kind:=1 if y<FOREST_EDGE else 0
			if y<FOREST_EDGE and n>0.27: kind=7
			if y>=FOREST_EDGE and n>0.25: kind=8
			if y>=FOREST_EDGE and n< -0.28: kind=11
			if x>282 and y>130: kind=7
			if absf(x-river_x(y))<4.7:
				kind=4
				blocked[cell]=true
			elif absf(x-river_x(y))<6.5: kind=9
			# An irregular north-west lake, distinct from the winding river.
			if pow((x-31)/16.0,2)+pow((y-38)/12.0,2)<1+n*0.3:
				kind=4
				blocked[cell]=true
			ground[cell]=kind
	routes=[
		[Vector2(63,165),Vector2(90,164),Vector2(104,143),Vector2(181,143),Vector2(210,161),Vector2(247,161)],
		[Vector2(63,165),Vector2(75,191),Vector2(115,202),Vector2(184,202),Vector2(217,190),Vector2(247,161)],
		[Vector2(63,165),Vector2(42,166),Vector2(33,181),Vector2(41,193),Vector2(75,191)],
		[Vector2(63,165),Vector2(72,133),Vector2(76,112)],
		[Vector2(247,161),Vector2(254,136),Vector2(250,112)]]
	for route in routes: paint_route(route,1.8,2)
	for y in [143,202]: bridge(y)
	# The northern wooden crossing has no roads leading into the forest.
	fill(Rect2i(150,85,18,4),6)
	village(Vector2(63,165),false)
	village(Vector2(246,161),true)
	wilderness_sites()
	vegetation()
	export_footprints()

func village(c:Vector2,east:bool)->void:
	reserved.append(Rect2(c-Vector2(24,23),Vector2(49,47)))
	var village_name:="鸦渡镇" if east else "灰橡镇"
	# An irregular market square and connected lanes, rather than a rectangular slab.
	for y in range(-4,7):
		for x in range(-10,11):
			if absf(x)+absf(y)*0.6<12: fill(Rect2i(Vector2i(c)+Vector2i(x,y),Vector2i.ONE),3)
	for x in [-18,-8,8,18]: paint_route([c+Vector2(x,-17),c+Vector2(x,20)],1.1,2)
	for y in [-14,-5,8,18]: paint_route([c+Vector2(-22,y),c+Vector2(23,y)],1.2,2)
	var plots:Array=[
		[Vector2(-7,-3),"home","旅人的家" if not east else "渡口管事宅"],
		[Vector2(7,-5),"tavern","铜鹿酒馆" if not east else "淹鸦酒馆"],
		[Vector2(18,1),"smith","霍尔特的铁砧" if not east else "河港锻坊"],
		[Vector2(-18,-5),"cottage","草药师的小屋"],
		[Vector2(-17,9),"merchant","缝纫铺"],
		[Vector2(18,12),"warehouse","麦穗粮仓" if not east else "税关货栈"],
		[Vector2(-7,18),"cottage","玛尔塔的院落"],
		[Vector2(6,17),"merchant","木匠作坊"],
		[Vector2(-16,-17),"cottage","酿酒人的家"],
		[Vector2(-5,-16),"warehouse","旧镇公所"],
		[Vector2(10,-18),"chapel","圣烬礼拜堂" if not east else "河神小礼拜堂"],
		[Vector2(21,-12),"cottage","烛匠小屋"]]
	for plot in plots:
		var p:Vector2=c+plot[0]
		building(plot[1],p,plot[2],village_name+"的旧木与石墙留下了几代人的手艺。")
		garden(p+Vector2(-2,1.7),rng.randi_range(0,2))
		add("barrel",p+Vector2(3,0.5),Vector2(10,8))
		add("firewood",p+Vector2(-3,-0.5),Vector2(16,8))
		if int(p.x)%2==0: add("bench",p+Vector2(2,1.8),Vector2(18,5))
	for p in [Vector2(-5,4),Vector2(3,4),Vector2(8,1)]:
		add("stall",c+p,Vector2(40,13),true,"集市摊位","摊布下有面包、药草、苹果和装满谷物的陶罐。")
	add("well",c+Vector2(0,-1),Vector2(22,12),true,"镇中水井","木桶沿着旧井壁缓缓下降。")
	add("noticeboard",c+Vector2(-1,6),Vector2(20,6),false,"布告栏","林道失修、磨坊缺工、渡口停航……镇民的纸条层层叠叠。")
	add("cart",c+Vector2(13,8),Vector2(30,16),true,"商旅马车","麻布车篷上还有上一场雨留下的水痕。")
	for p in [Vector2(-10,0),Vector2(10,7),Vector2(-12,11),Vector2(3,10),Vector2(1,-8),Vector2(20,5)]: add("lamp",c+p,Vector2(3,3))
	for i in range(12):
		add("fence",c+Vector2(-23+i*2,22),Vector2(27,4))
	# Several crop types and an orchard outside the residential lanes.
	var farm:=c+Vector2(-30,10)
	fill(Rect2i(Vector2i(farm),Vector2i(9,13)),5)
	fill(Rect2i(Vector2i(c+Vector2(23,10)),Vector2i(8,12)),5)
	for y in range(3):
		for x in range(4): add("tree_2",c+Vector2(-30+x*3,-15+y*4),Vector2(9,7))
	add("scarecrow",farm+Vector2(4,5),Vector2(6,5))
	if not east:
		building("windmill",Vector2(41,191),"风磨丘磨坊","风从麦田吹来，磨盘旁积着一层细白的粉。")
		fill(Rect2i(28,194,18,10),5)
		reserved.append(Rect2(29,183,22,24))
		paint_route([Vector2(41,191),Vector2(45,193)],1.3,2)

func wilderness_sites()->void:
	var rx:=roundi(river_x(174))
	fill(Rect2i(rx+2,170,12,8),6)
	paint_route([Vector2(rx+13,174),Vector2(205,174),Vector2(227,161)],1.5,2)
	reserved.append(Rect2(rx-3,166,23,21))
	building("warehouse",Vector2(rx+18,170),"苇岸税关","渡船与商队都要在这里留下货单。")
	add("boat",Vector2(rx+0.8,177),Vector2.ZERO,false,"苇岸渡船","旧船桨倚在船边，缆绳紧紧绕着木桩。")
	add("boat",Vector2(rx-2,185),Vector2.ZERO)
	for i in range(7): add("crate",Vector2(rx+7+i%3,171+i/3),Vector2(11,7))
	for p in [Vector2(89,92),Vector2(116,202),Vector2(208,115)]:
		reserved.append(Rect2(p-Vector2(6,6),Vector2(13,13)))
		add("tent",p+Vector2(-2,-1),Vector2(27,12),true,"旅人营地","炭灰还留着暖意，木桩上挂着一只旧水壶。")
		add("fire",p+Vector2(2,1),Vector2(13,7))
		add("log",p+Vector2(-1,3),Vector2(29,8))
		add("barrel",p+Vector2(-4,0),Vector2(11,8))
		add("cart",p+Vector2(4,-2),Vector2(27,14))
	for center in [Vector2(237,46),Vector2(191,74)]:
		reserved.append(Rect2(center-Vector2(15,14),Vector2(31,30)))
		fill(Rect2i(Vector2i(center)-Vector2i(9,6),Vector2i(19,15)),10)
		add("gatehouse",center,Vector2.ZERO,false,"暮钟修道院" if center.x>200 else "断誓堡","藤蔓爬过断墙，旧日的誓言只剩石上的凿痕。")
		for x in [-4.5,4.5]: add("pillar",center+Vector2(x,-0.4),Vector2(15,14),true)
		for p in [Vector2(-8,-5),Vector2(8,-5),Vector2(-8,6),Vector2(8,6),Vector2(-5,9),Vector2(5,9)]:
			add("ruin_wall",center+p,Vector2(28,13),true)
		for p in [Vector2(-3,5),Vector2(3,6),Vector2(0,8)]: add("crystal",center+p,Vector2(7,5))
		for i in range(20): add("rubble",center+Vector2(rng.randf_range(-10,10),rng.randf_range(-6,11)),Vector2.ZERO)
	var grave:=Vector2(269,100)
	reserved.append(Rect2(grave-Vector2(8,8),Vector2(17,17)))
	for y in range(3):
		for x in range(3): add("grave",grave+Vector2(x*3-3,y*3-3),Vector2(25,10),true)
	add("sign",grave+Vector2(0,7),Vector2(4,4),false,"寂鸦墓园","名字已被苔藓覆盖，只有鸦声仍在回应。")
	for center in [Vector2(35,128),Vector2(106,56),Vector2(292,146),Vector2(287,196)]:
		for i in range(12): add("rock",center+Vector2(rng.randf_range(-7,7),rng.randf_range(-5,5)),Vector2(20,12),true)
	for p in [Vector2(92,148),Vector2(210,159),Vector2(102,202),Vector2(77,115),Vector2(252,115)]: add("sign",p,Vector2(5,4),false,"旧王国路标","灰橡镇 · 鸦渡镇 · 苇岸渡口。林中的旧路早已被岁月吞没。")

func vegetation()->void:
	# Separate authored land-use areas from broad natural vegetation fields.
	for y in range(3,SIZE.y-3,3):
		for x in range(3,SIZE.x-3,3):
			var p:=Vector2(x+rng.randf_range(-0.8,0.8),y+rng.randf_range(-0.8,0.8))
			var forest:=y<FOREST_EDGE
			if rng.randf()>(0.9 if forest else 0.22): continue
			if not clear_for_tree(p): continue
			var variant:=rng.randi_range(0,2)
			if x>190 and y<70 and rng.randf()<0.18: variant=3
			add("tree_"+str(variant),p,Vector2(10,8),true)
	for i in range(3500):
		var p:=Vector2(rng.randf_range(2,SIZE.x-2),rng.randf_range(2,SIZE.y-2))
		var kind:int=ground.get(Vector2i(p),4)
		if kind not in [0,1,7,8,11]: continue
		var choices:=["tuft","tuft","flowers","fern","mushrooms","pebbles","shrub"]
		add(choices[i%choices.size()],p,Vector2.ZERO)
	for y in range(3,SIZE.y-3,3):
		for side in [-1,1]: add("reeds",Vector2(river_x(y)+side*6.1,y),Vector2.ZERO)
	for i in range(90):
		var p:=Vector2(rng.randf_range(5,315),rng.randf_range(6,110))
		if clear_for_tree(p): add("log",p,Vector2(25,8),true)

func garden(p:Vector2,variant:int)->void:
	for i in range(5): add("flowers" if variant!=1 else "pot",p+Vector2(i*0.65,0),Vector2.ZERO)
	add("fence",p+Vector2(0,1),Vector2(25,4))

func bridge(y:int)->void:
	var rx:=roundi(river_x(y))
	fill(Rect2i(rx-9,y-2,19,5),6)
	for x in range(rx-9,rx+10,2):
		add("fence",Vector2(x+0.5,y-2.1),Vector2(27,4))
		add("fence",Vector2(x+0.5,y+2.9),Vector2(27,4))

func building(kind:String,p:Vector2,title:String,description:String)->void:
	add(kind,p,Vector2(82,28),true,title,description,Vector2(0,-31))
	paint_route([p,p+Vector2(0,2.3)],0.95,2)

func add(kind:String,p:Vector2,half:Vector2,occludes:bool=false,title:String="",description:String="",offset:Vector2=Vector2(0,-5))->void:
	objects.append({"kind":kind,"pos":p*TILE,"half":half,"occludes":occludes,"title":title,"description":description,"collision_offset":offset})

func fill(area:Rect2i,terrain:int)->void:
	for y in range(area.position.y,area.end.y):
		for x in range(area.position.x,area.end.x):
			ground[Vector2i(x,y)]=terrain
			blocked.erase(Vector2i(x,y))

func paint_route(points:Array,width:float,terrain:int)->void:
	for i in range(points.size()-1):
		var a:Vector2=points[i]
		var b:Vector2=points[i+1]
		for y in range(int(minf(a.y,b.y)-width-1),int(maxf(a.y,b.y)+width+2)):
			if y<FOREST_EDGE: continue
			for x in range(int(minf(a.x,b.x)-width-1),int(maxf(a.x,b.x)+width+2)):
				var p:=Vector2(x+0.5,y+0.5)
				if p.distance_to(Geometry2D.get_closest_point_to_segment(p,a,b))<=width and ground.get(Vector2i(x,y))!=4: ground[Vector2i(x,y)]=terrain

func clear_for_tree(p:Vector2)->bool:
	for area in reserved:
		if area.has_point(p): return false
	for npc in preload("res://maps/npc_catalog.gd").entries():
		if p.distance_to(npc.tile)<3: return false
	if p.distance_to(SPAWN/TILE)<3: return false
	for entry in [Vector2(76.5,111.5),Vector2(250.5,111.5),Vector2(159.5,86.5)]:
		if p.distance_to(entry)<3: return false
	for y in range(-1,2):
		for x in range(-1,2):
			if ground.get(Vector2i(p)+Vector2i(x,y),4) not in [0,1,7,8,11]: return false
	return true

func export_footprints()->void:
	for o in objects:
		var half:Vector2=o.half
		if half==Vector2.ZERO: continue
		var center:Vector2=o.pos+o.collision_offset
		var lo:=Vector2i((center-half)/TILE)
		var hi:=Vector2i((center+half)/TILE)
		for y in range(lo.y,hi.y+1):
			for x in range(lo.x,hi.x+1): blocked[Vector2i(x,y)]=true
	for x in range(SIZE.x):
		blocked[Vector2i(x,0)]=true
		blocked[Vector2i(x,SIZE.y-1)]=true
	for y in range(SIZE.y):
		blocked[Vector2i(0,y)]=true
		blocked[Vector2i(SIZE.x-1,y)]=true

static func region_at(p:Vector2)->String:
	if p.y>=FOREST_EDGE*TILE: return "market"
	return "greenwood" if p.x<160*TILE else "moonwood"

static func region_tile(p:Vector2)->Vector2:
	return p/TILE-Vector2(REGIONS[region_at(p)].position)

static func zone_name(p:Vector2)->String:
	p/=TILE
	if p.distance_to(Vector2(237,46))<17: return "暮钟修道院"
	if p.distance_to(Vector2(191,74))<16: return "断誓堡"
	if p.distance_to(Vector2(269,100))<12: return "寂鸦墓园"
	if p.distance_to(Vector2(89,92))<10: return "苔石猎营"
	if p.distance_to(Vector2(41,191))<12: return "风磨丘"
	if p.distance_to(Vector2(116,202))<10: return "枯井驿站"
	if p.distance_to(Vector2(63,165))<31: return "灰橡镇"
	if p.distance_to(Vector2(246,161))<31: return "鸦渡镇"
	if absf(p.x-155)<18 and p.y>165 and p.y<190: return "苇岸渡口"
	if p.y<FOREST_EDGE: return "黑枝林地" if p.x<160 else "暮影古林"
	if p.x>282: return "灰苇湿地"
	return "旧王大道" if p.y<165 else "南境旷野"
