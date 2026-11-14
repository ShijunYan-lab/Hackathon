extends Node2D
## Grounded atmosphere props. Decorative interactions never fabricate an item or a quest.
const ART = preload("res://assets/item_art.gd")
var data: Dictionary = {}
var phase: float = 0.0

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	add_to_group("scene_props")
	set_process(str(data.get("kind", "")) in ["fire", "furnace", "cauldron"])

func _process(delta: float) -> void:
	phase += delta
	if phase >= 0.11:
		phase = 0.0
		queue_redraw()

func _draw() -> void:
	var kind: String = str(data.get("kind", "crate"))
	var texture: Texture2D = ART.object_texture(kind)
	var dim: float = float(data.get("size", 64))
	draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, dim / 4.0, Color(0,0,0,0.23))
	draw_set_transform(Vector2.ZERO)
	var pulse: float = 0.93 + sin(Time.get_ticks_msec() * 0.005 + position.x) * 0.07
	var tint: Color = Color(1.0, pulse, pulse * 0.93) if kind in ["fire", "furnace", "cauldron"] else Color.WHITE
	draw_texture_rect(texture, Rect2(-dim / 2.0, -dim + 6, dim, dim), false, tint)
