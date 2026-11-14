extends Node2D
var grid:=AStarGrid2D.new()
var region:Dictionary
func _ready()->void:
	region=JSON.parse_string(FileAccess.get_file_as_string("res://maps/backend_world.json")).regions[0]
	grid.region=Rect2i(0,0,320,224)
	grid.cell_size=Vector2(32,32)
	grid.offset=Vector2(16,16)
	grid.diagonal_mode=AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	grid.update()
	# Exact grid solids agree with C checkpoints and A's body/projectile collision.
	var tile_set:=TileSet.new()
	tile_set.tile_size=Vector2i(32,32)
	tile_set.add_physics_layer()
	tile_set.set_physics_layer_collision_layer(0,1)
	var atlas:=TileSetAtlasSource.new()
	var pixel:=Image.create(32,32,false,Image.FORMAT_RGBA8)
	atlas.texture=ImageTexture.create_from_image(pixel)
	atlas.texture_region_size=Vector2i(32,32)
	atlas.create_tile(Vector2i.ZERO)
	tile_set.add_source(atlas,0)
	var tile:=atlas.get_tile_data(Vector2i.ZERO,0)
	tile.set_collision_polygons_count(0,1)
	tile.set_collision_polygon_points(0,0,PackedVector2Array([Vector2(-16,-16),Vector2(16,-16),Vector2(16,16),Vector2(-16,16)]))
	var solids:=TileMapLayer.new()
	solids.tile_set=tile_set
	add_child(solids)
	for cell in region.blocked_tiles:
		var at:=Vector2i(int(cell[0]),int(cell[1]))
		grid.set_point_solid(at)
		solids.set_cell(at,0,Vector2i.ZERO)

func world_to_cell(point:Vector2)->Vector2i: return Vector2i((point/32).floor())
func find_path(start:Vector2,end:Vector2)->PackedVector2Array:
	var a:=world_to_cell(start)
	var b:=world_to_cell(end)
	if not grid.is_in_boundsv(a) or not grid.is_in_boundsv(b) or grid.is_point_solid(b): return PackedVector2Array()
	return grid.get_point_path(a,b)
