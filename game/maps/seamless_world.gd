extends Node2D
## One persistent, continuous overworld; biomes are labels, not scene transitions.
## Pathfinding shares the same 32px world tile coordinates as character snapshots.
const DATA_PATH: String = "res://maps/overworld_data.json"
const TEXTURE_PATH: String = "res://maps/assets/seamless_overworld.png"
var tile_size: int = 32
var width_tiles: int = 96
var height_tiles: int = 60
var region_id: String = "overworld"
var spawn_tiles: Dictionary = {}
var biomes: Array = []
var path_grid: AStarGrid2D = AStarGrid2D.new()

func _ready() -> void:
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(DATA_PATH))
    if not (parsed is Dictionary):
        push_error("Overworld data missing or invalid: " + DATA_PATH)
        return
    var data: Dictionary = parsed
    tile_size = int(data.get("tile_size", 32))
    width_tiles = int(data.get("width_tiles", 96))
    height_tiles = int(data.get("height_tiles", 60))
    region_id = str(data.get("region_id", "overworld"))
    spawn_tiles = data.get("spawn_tiles", {})
    biomes = data.get("biomes", [])
    var map_sprite := Sprite2D.new()
    map_sprite.name = "Terrain"
    map_sprite.centered = false
    map_sprite.texture = load(TEXTURE_PATH) as Texture2D
    map_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    map_sprite.z_index = -20
    add_child(map_sprite)
    path_grid.region = Rect2i(0, 0, width_tiles, height_tiles)
    path_grid.cell_size = Vector2(tile_size, tile_size)
    path_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
    path_grid.update()
    for cell_data in data.get("blocked_cells", []):
        if cell_data is Array and cell_data.size() >= 2:
            var cell := Vector2i(int(cell_data[0]), int(cell_data[1]))
            if path_grid.is_in_boundsv(cell):
                path_grid.set_point_solid(cell, true)
                _create_wall_cell(cell)

func _create_wall_cell(cell: Vector2i) -> void:
    var body := StaticBody2D.new()
    body.collision_layer = 1
    body.collision_mask = 0
    body.position = cell_center(cell)
    var shape := CollisionShape2D.new()
    var rect := RectangleShape2D.new()
    rect.size = Vector2(tile_size, tile_size)
    shape.shape = rect
    body.add_child(shape)
    add_child(body)

func world_to_cell(world_position: Vector2) -> Vector2i:
    return Vector2i(floori(world_position.x / float(tile_size)), floori(world_position.y / float(tile_size)))

func cell_center(cell: Vector2i) -> Vector2:
    return (Vector2(cell) + Vector2(0.5, 0.5)) * float(tile_size)

func spawn_position(name: String) -> Vector2:
    var tile: Dictionary = spawn_tiles.get(name, {"x": 15.5, "y": 29.5})
    return Vector2(float(tile.get("x", 15.5)), float(tile.get("y", 29.5))) * float(tile_size)

func biome_name(world_position: Vector2) -> String:
    var cell: Vector2i = world_to_cell(world_position)
    for zone in biomes:
        if not (zone is Dictionary):
            continue
        var area: Dictionary = zone.get("rect", {})
        var bounds := Rect2i(int(area.get("x", 0)), int(area.get("y", 0)), int(area.get("w", 0)), int(area.get("h", 0)))
        if bounds.has_point(cell):
            return str(zone.get("label", zone.get("id", "")))
    return "未探明边境"

func nearest_walkable(cell: Vector2i) -> Vector2i:
    if path_grid.is_in_boundsv(cell) and not path_grid.is_point_solid(cell):
        return cell
    for radius in range(1, 8):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                var trial := cell + Vector2i(dx, dy)
                if path_grid.is_in_boundsv(trial) and not path_grid.is_point_solid(trial):
                    return trial
    return Vector2i(-1, -1)

func find_path(start_position: Vector2, goal_position: Vector2) -> PackedVector2Array:
    var start: Vector2i = nearest_walkable(world_to_cell(start_position))
    var target: Vector2i = nearest_walkable(world_to_cell(goal_position))
    var result := PackedVector2Array()
    if start.x < 0 or target.x < 0:
        return result
    var cells: Array[Vector2i] = path_grid.get_id_path(start, target)
    for cell in cells:
        result.append(cell_center(cell))
    return result

func is_walkable_world(world_position: Vector2) -> bool:
    var tile := world_to_cell(world_position)
    return path_grid.is_in_boundsv(tile) and not path_grid.is_point_solid(tile)

func world_pixel_size() -> Vector2:
    return Vector2(width_tiles * tile_size, height_tiles * tile_size)
