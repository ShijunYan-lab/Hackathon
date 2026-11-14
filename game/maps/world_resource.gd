extends Node2D
## World resources and notices are authoritative server entities.
const ART = preload("res://assets/item_art.gd")
var data: Dictionary = {}

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST

func _draw() -> void:
	var kind: String = str(data.get("kind", "herb"))
	var remaining: int = int(data.get("remaining", 1))
	var is_board: bool = kind == "board"
	var texture: Texture2D = ART.object_texture(kind)
	var dim: float = 64.0 if is_board else 43.0
	var tint: Color = Color.WHITE if is_board or remaining > 0 else Color(0.42, 0.42, 0.43, 0.53)
	draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.3))
	draw_circle(Vector2(0, -3), 16 if is_board else 12, Color(0, 0, 0, 0.27))
	draw_set_transform(Vector2.ZERO)
	draw_texture_rect(texture, Rect2(-dim / 2.0, -dim + 4, dim, dim), false, tint)
	if remaining <= 0 and not is_board:
		draw_line(Vector2(-10, -8), Vector2(10, -8), Color("978776"), 1.0)
