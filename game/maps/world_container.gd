extends Node2D
## Distinct visuals for merchants, common caches, high-grade caches and opened chests.
const ART = preload("res://assets/item_art.gd")
var data: Dictionary = {}

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

func _draw() -> void:
	var kind: String = str(data.get("kind", "cache"))
	var opened: bool = bool(data.get("opened", false))
	var quality: String = str(data.get("quality", "common"))
	var key: String = "crate" if kind == "merchant" else ("rare_chest" if quality in ["rare", "epic", "legendary"] else "chest")
	var texture: Texture2D = ART.object_texture(key)
	draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, 15, Color(0, 0, 0, 0.32))
	draw_set_transform(Vector2.ZERO)
	draw_texture_rect(texture, Rect2(-25, -47, 50, 50), false, Color(0.58, 0.58, 0.58, 0.75) if opened else Color.WHITE)
