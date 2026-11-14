extends RefCounted
## One deterministic source for the editor scene, collision and region manifest.
const SIZE := Vector2i(160, 112)
const TILE := 32
const SPAWN := Vector2(28.5, 80.5) * TILE
const REGIONS := {"market": Rect2i(0, 56, 160, 56), "greenwood": Rect2i(0, 0, 80, 56), "moonwood": Rect2i(80, 0, 80, 56)}
var ground := {}
var objects: Array[Dictionary] = []
var blocked := {}
var routes: Array = []
var rng := RandomNumberGenerator.new()
var landmarks := [
	{"name": "炉溪村", "pos": Vector2(30, 81), "kind": "village"},
	{"name": "苇湾村", "pos": Vector2(119, 80), "kind": "village"},
	{"name": "翠影密林", "pos": Vector2(35, 30), "kind": "forest"},
	{"name": "月隐遗迹", "pos": Vector2(116, 26), "kind": "ruin"},
	{"name": "北桥", "pos": Vector2(78, 71), "kind": "bridge"},
	{"name": "南桥", "pos": Vector2(75, 97), "kind": "bridge"}]

func river_x(y: float) -> float: return 78.0 + sin(y * 0.065) * 4.0 + sin(y * 0.14) * 1.5

func build() -> void:
	rng.seed = 20261113
	for y in range(SIZE.y):
		for x in range(SIZE.x):
			var cell := Vector2i(x, y)
			ground[cell] = 1 if y < 56 else 0
			if absf(x - river_x(y)) < 3.4:
				ground[cell] = 4
				blocked[cell] = true
	# Two completely traversable village-to-village routes, plus a western loop.
	routes = [
		[Vector2(30,81),Vector2(43,81),Vector2(49,71),Vector2(92,71),Vector2(105,80),Vector2(121,80)],
		[Vector2(30,81),Vector2(37,94),Vector2(54,97),Vector2(96,97),Vector2(110,91),Vector2(121,80)],
		[Vector2(30,81),Vector2(17,81),Vector2(14,92),Vector2(25,98),Vector2(54,97)],
		[Vector2(30,81),Vector2(33,65),Vector2(36,56)],
		[Vector2(121,80),Vector2(123,67),Vector2(119,56)]]
	for route in routes: paint_route(route, 1.6, 2)
	for y in [71,97]:
		var rx := roundi(river_x(y))
		fill(Rect2i(rx-7,y-2,15,5),6)
		for x in range(rx-7,rx+8,2):
			add("fence",Vector2(x+0.5,y-2.0),Vector2(25,4),true)
			add("fence",Vector2(x+0.5,y+2.8),Vector2(25,4),true)
	# The forest is intentionally pathless, including around the ruined crossing.
	fill(Rect2i(74,43,13,3),6)
	fill(Rect2i(24,78,15,9),3)
	fill(Rect2i(112,77,17,9),3)
	fill(Rect2i(13,85,8,7),5)
	fill(Rect2i(131,85,8,9),5)
	fill(Rect2i(112,22,10,10),3)
	# Buildings use a bottom-centre anchor; players collide only with foundations.
	building("home",Vector2(27,78),"你的家","一盏窗灯，等候归来的旅人。")
	building("tavern",Vector2(36,77),"余烬酒馆","木牌上刻着酒杯，炉火仍然温暖。")
	building("smith",Vector2(43,84),"炉溪铁匠铺","炉膛里的铁火映亮了石墙。")
	building("cottage",Vector2(19,78),"药草小屋","窗台晾着来自翠影林的草药。")
	building("cottage",Vector2(22,91),"农人的家","麦田在屋后的风里起伏。")
	building("warehouse",Vector2(36,91),"谷仓","木箱与干草收在高高的屋檐下。")
	building("cottage",Vector2(45,69),"林边守望屋","向北走，石路会消失在林缘。")
	building("tavern",Vector2(119,76),"渡鸦酒馆","旅人沿着北桥和南桥来到这里。")
	building("smith",Vector2(130,80),"苇湾铁匠铺","河港的船钉与工具在这里打造。")
	building("home",Vector2(110,75),"河湾民居","蓝灰色的屋顶遮住了临河的小窗。")
	building("cottage",Vector2(110,88),"织工小屋","门边的花盆长满了浅紫色小花。")
	building("warehouse",Vector2(124,91),"河港货栈","这里通往西边的木码头。")
	building("cottage",Vector2(135,72),"磨坊人家","远处的田垄一直延伸到山坡。")
	for p in [Vector2(26,84),Vector2(33,84),Vector2(115,83),Vector2(123,83)]:
		add("stall",p,Vector2(39,11),true,"露天集市","棚布下摆着苹果、麦穗与陶器。")
	for p in [Vector2(30,80),Vector2(120,79)]: add("well",p,Vector2(20,10),true,"村井","石井里传来清凉的回响。")
	var dock_x := roundi(river_x(84))
	fill(Rect2i(dock_x+2,81,8,6),6)
	paint_route([Vector2(dock_x+9,84),Vector2(100,84),Vector2(110,80)],1.2,2)
	add("boat",Vector2(dock_x+1,85),Vector2.ZERO,false,"渡船","小舟系在木桩上，河水轻轻拍着船舷。")
	add("boat",Vector2(dock_x-1,91),Vector2.ZERO)
	add("ruin",Vector2(117,29),Vector2.ZERO,false,"月隐遗迹","石环上的古老纹章仍透着微光。")
	# The arch opening is walkable; its two pillars are separate physical bodies.
	for p in [Vector2(115.3,28.4),Vector2(118.4,28.4),Vector2(112,25),Vector2(122,26),Vector2(113,32)]:
		add("pillar",p,Vector2(15,11),true)
	for p in [Vector2(114,30),Vector2(120,31),Vector2(109,22)]: add("rock",p,Vector2(19,10),true)
	for p in [Vector2(24,80),Vector2(38,80),Vector2(41,86),Vector2(31,88),Vector2(112,80),Vector2(127,80),Vector2(dock_x+7,84),Vector2(117,87)]: add("lamp",p,Vector2(3,3),false)
	for p in [Vector2(34,82),Vector2(126,85),Vector2(34,60)]: add("sign",p,Vector2(4,4),false,"路牌","北行入翠影密林；南北双桥连接炉溪与苇湾。")
	for p in [Vector2(40,86),Vector2(127,82),Vector2(100,53)]: add("fire",p,Vector2(14,7),false)
	for center in [Vector2(14,85),Vector2(132,86)]:
		for i in range(4): add("fence",center+Vector2(i*2,-1),Vector2(27,4),true)
	for base in [Vector2(34,90),Vector2(124,90),Vector2(dock_x+8,82),Vector2(43,83)]:
		for i in range(3): add("crate",base+Vector2(i*0.8,0.6),Vector2(12,8),true)
	# Forest spacing guarantees passages between trunks without painting trails.
	for y in range(3,109,2):
		for x in range(3,157,2):
			var p := Vector2(x+rng.randf_range(-0.4,0.4),y+rng.randf_range(-0.4,0.4))
			var forest := y < 56
			if rng.randf() > (0.82 if forest else 0.12): continue
			if not clear_for_tree(p): continue
			add("tree_"+str(rng.randi_range(0,3)),p,Vector2(9,7),true)
	for n in range(420):
		var p := Vector2(rng.randf_range(2,158),rng.randf_range(2,110))
		if ground.get(Vector2i(p),0) not in [0,1]: continue
		if not clear_for_tree(p): continue
		add("flowers" if n%4 else "rock",p,Vector2.ZERO)
	for y in range(3,109,3):
		for side in [-1,1]: add("reeds",Vector2(river_x(y)+side*4.3,y),Vector2.ZERO)
	# Export occupied footprint tiles conservatively for server/path integration.
	for o in objects:
		var half: Vector2 = o.half
		if half == Vector2.ZERO: continue
		var center: Vector2 = o.pos + o.collision_offset
		var lo := Vector2i((center-half)/TILE)
		var hi := Vector2i((center+half)/TILE)
		for y in range(lo.y,hi.y+1):
			for x in range(lo.x,hi.x+1): blocked[Vector2i(x,y)] = true
	for x in range(SIZE.x):
		blocked[Vector2i(x,0)] = true
		blocked[Vector2i(x,SIZE.y-1)] = true
	for y in range(SIZE.y):
		blocked[Vector2i(0,y)] = true
		blocked[Vector2i(SIZE.x-1,y)] = true

func fill(area: Rect2i, terrain: int) -> void:
	for y in range(area.position.y,area.end.y):
		for x in range(area.position.x,area.end.x):
			ground[Vector2i(x,y)] = terrain
			blocked.erase(Vector2i(x,y))

func paint_route(points: Array, width: float, terrain: int) -> void:
	for i in range(points.size()-1):
		var a: Vector2 = points[i]
		var b: Vector2 = points[i+1]
		for y in range(int(minf(a.y,b.y)-width-1),int(maxf(a.y,b.y)+width+2)):
			for x in range(int(minf(a.x,b.x)-width-1),int(maxf(a.x,b.x)+width+2)):
				if y<56 and terrain==2: continue
				var p := Vector2(x+0.5,y+0.5)
				if p.distance_to(Geometry2D.get_closest_point_to_segment(p,a,b)) <= width and ground.get(Vector2i(x,y)) != 4:
					ground[Vector2i(x,y)] = terrain

func building(kind: String,p: Vector2,title: String,description: String) -> void:
	add(kind,p,Vector2(65,24),true,title,description,Vector2(0,-30))
	paint_route([p+Vector2(0,0.1),p+Vector2(0,2.3)],0.8,2)

func add(kind: String,p: Vector2,half: Vector2,occludes: bool=false,title: String="",description: String="",offset: Vector2=Vector2(0,-5)) -> void:
	objects.append({"kind":kind,"pos":p*TILE,"half":half,"occludes":occludes,"title":title,"description":description,"collision_offset":offset})

func clear_for_tree(p: Vector2) -> bool:
	for y in range(-1,2):
		for x in range(-1,2):
			if ground.get(Vector2i(p)+Vector2i(x,y),4) not in [0,1]: return false
	if p.distance_to(SPAWN/TILE) < 3: return false
	# Invisible clearings at entry points keep the forest accessible without paths.
	for entry in [Vector2(36.5,55.5),Vector2(119.5,55.5)]:
		if p.distance_to(entry)<2: return false
	if Rect2(109,19,17,16).has_point(p): return false
	for o in objects:
		if not o.kind.begins_with("tree") and o.half != Vector2.ZERO and p.distance_to(o.pos/TILE) < 3.3: return false
	return true

static func region_at(p: Vector2) -> String:
	if p.y >= 56*TILE: return "market"
	return "greenwood" if p.x < 80*TILE else "moonwood"

static func region_tile(p: Vector2) -> Vector2:
	var region: Rect2i = REGIONS[region_at(p)]
	return p/TILE-Vector2(region.position)
