extends SceneTree
## Bakes a regular editable Godot scene. No procedural generation at game startup.
const Layout = preload("res://maps/world_layout.gd")
var scene_root: Node2D

func _initialize() -> void:
	call_deferred("bake")

func owned(node: Node,parent: Node) -> void:
	parent.add_child(node)
	node.owner = scene_root

func bake() -> void:
	var layout := Layout.new()
	layout.build()
	scene_root = Node2D.new()
	scene_root.name = "World"
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(32,32)
	tiles.add_physics_layer()
	tiles.set_physics_layer_collision_layer(0,1)
	var atlas := TileSetAtlasSource.new()
	atlas.texture = load("res://assets/environment/terrain.png")
	atlas.texture_region_size = Vector2i(32,32)
	tiles.add_source(atlas,0)
	for y in range(12):
		for x in range(16):
			atlas.create_tile(Vector2i(x,y))
			if y == 4:
				var td := atlas.get_tile_data(Vector2i(x,y),0)
				td.set_collision_polygons_count(0,1)
				td.set_collision_polygon_points(0,0,PackedVector2Array([Vector2(-16,-16),Vector2(16,-16),Vector2(16,16),Vector2(-16,16)]))
	var edge_atlas := TileSetAtlasSource.new()
	edge_atlas.texture = load("res://assets/pixel/edges.png")
	edge_atlas.texture_region_size = Vector2i(32,32)
	for y in range(3):
		for x in range(16): edge_atlas.create_tile(Vector2i(x,y))
	tiles.add_source(edge_atlas,1)
	ResourceSaver.save(tiles,"res://maps/realm_tileset.tres")
	var terrain := TileMapLayer.new()
	terrain.name = "Terrain"
	terrain.tile_set = tiles
	owned(terrain,scene_root)
	var edges := TileMapLayer.new()
	edges.name = "SoftTerrainEdges"
	edges.tile_set = tiles
	edges.collision_enabled = false
	owned(edges,scene_root)
	var dirs := [Vector2i.UP,Vector2i.RIGHT,Vector2i.DOWN,Vector2i.LEFT]
	for cell in layout.ground:
		var kind: int = layout.ground[cell]
		terrain.set_cell(cell,0,Vector2i(posmod(cell.x*73+cell.y*31+cell.x*cell.y,16),kind))
		if kind in [2,3,4,1]:
			var mask := 0
			for i in range(4):
				var neighbor: int = layout.ground.get(cell+dirs[i],kind)
				if (kind == 4 and neighbor != 4 and neighbor != 6) or (kind in [2,3] and neighbor in [0,1]) or (kind == 1 and neighbor == 0): mask |= 1<<i
			if mask: edges.set_cell(cell,1,Vector2i(mask,1 if kind==4 else (2 if kind==1 else 0)))
	var entities := Node2D.new()
	entities.name = "Entities"
	entities.y_sort_enabled = true
	owned(entities,scene_root)
	for i in range(layout.objects.size()):
		var o: Dictionary = layout.objects[i]
		var node := Node2D.new()
		node.name = o.kind.capitalize().replace(" ","")+str(i)
		node.position = o.pos
		owned(node,entities)
		var sprite := Sprite2D.new()
		sprite.name = "Art"
		var art_path:String="res://assets/environment/"+o.kind+".png"
		if not ResourceLoader.exists(art_path): art_path="res://assets/pixel/"+o.kind+".png"
		sprite.texture = load(art_path)
		sprite.position = Vector2(0,-sprite.texture.get_height()/2.0+5)
		owned(sprite,node)
		if o.kind.begins_with("tree"):
			node.add_to_group("canopies",true)
		if o.title != "":
			node.add_to_group("landmarks",true)
			node.set_meta("title",o.title)
			node.set_meta("description",o.description)
		if o.half != Vector2.ZERO:
			body(node,o.half*2,o.collision_offset,1,"Foundation")
		if o.kind in Layout.BUILDINGS: node.add_to_group("buildings",true)
	var bounds := Node2D.new()
	bounds.name = "InvisibleMapBoundary"
	owned(bounds,scene_root)
	var width := Layout.SIZE.x*32
	var height := Layout.SIZE.y*32
	body(bounds,Vector2(width+128,64),Vector2(width/2.0,0),1,"North")
	body(bounds,Vector2(width+128,64),Vector2(width/2.0,height),1,"South")
	body(bounds,Vector2(64,height),Vector2(0,height/2.0),1,"West")
	body(bounds,Vector2(64,height),Vector2(width,height/2.0),1,"East")
	var packed := PackedScene.new()
	packed.pack(scene_root)
	ResourceSaver.save(packed,"res://maps/realm.tscn")
	var chart := Image.create(Layout.SIZE.x,Layout.SIZE.y,false,Image.FORMAT_RGBA8)
	var colors := ["68734a","4b573d","918064","777868","3c6466","67513b","8d744c","505f49","77764e","a39571","626b60","6e7b4f"]
	for cell in layout.ground: chart.set_pixelv(cell,Color(colors[layout.ground[cell]]))
	for o in layout.objects:
		if o.kind in Layout.BUILDINGS:
			var p := Vector2i(o.pos/32)
			chart.fill_rect(Rect2i(p-Vector2i(2,2),Vector2i(4,2)),Color("b5ab8b"))
	chart.save_png("res://maps/world_chart.png")
	export_regions(layout)
	print("WORLD BAKED: ",layout.ground.size()," tiles; ",layout.objects.size()," objects; ",Layout.SIZE*32," px.")
	scene_root.free()
	quit()

func body(parent: Node,size: Vector2,offset: Vector2,layer: int,label: String) -> void:
	var b := StaticBody2D.new()
	b.name = label
	b.collision_layer = layer
	b.collision_mask = 0
	b.position = offset
	owned(b,parent)
	var collision := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = size
	collision.shape = shape
	owned(collision,b)

func export_regions(layout: RefCounted) -> void:
	var result := {"schema_version":"v1","tile_size_px":32,"fixture_only":false,"regions":[]}
	var transitions:Dictionary=Layout.EXITS
	for id in Layout.REGIONS:
		var region: Rect2i = Layout.REGIONS[id]
		var blocked_tiles := []
		for cell in layout.blocked:
			if region.has_point(cell): blocked_tiles.append({"x":cell.x-region.position.x,"y":cell.y-region.position.y})
		var exits := []
		for entry in transitions[id]:
			exits.append({"id":id+"_to_"+entry[0],"tile":xy(entry[1]),"destination_region_id":entry[0],"destination_tile":xy(entry[2])})
		var spawn: Vector2 = Layout.region_tile(Layout.SPAWN) if id=="market" else (Vector2(76.5,111.5) if id=="greenwood" else Vector2(90.5,111.5))
		result.regions.append({"id":id,"width_tiles":region.size.x,"height_tiles":region.size.y,"blocked_tiles":blocked_tiles,"spawn_tile":xy(spawn),"exits":exits})
	var file := FileAccess.open("res://../shared/regions.json",FileAccess.WRITE)
	file.store_string(JSON.stringify(result,"  ")+"\n")
	var manifest := {"world_size_tiles":xy(Vector2(Layout.SIZE)),"tile_size_px":32,"region_offsets":{},"landmarks":[],"source":"res://maps/world_layout.gd"}
	for id in Layout.REGIONS: manifest.region_offsets[id]=xy(Vector2(Layout.REGIONS[id].position))
	for landmark in layout.landmarks: manifest.landmarks.append({"name":landmark.name,"tile":xy(landmark.pos),"kind":landmark.kind})
	FileAccess.open("res://maps/world_manifest.json",FileAccess.WRITE).store_string(JSON.stringify(manifest,"  ")+"\n")

func xy(p: Vector2) -> Dictionary: return {"x":p.x,"y":p.y}
