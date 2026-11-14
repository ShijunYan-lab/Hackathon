extends Node2D
## Client-only presentation of a real ground item, not an independent inventory.
const ART = preload("res://assets/item_art.gd")
var item: Dictionary = {}
var elapsed: float = 0.0

func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	set_process(true)

func _process(delta: float) -> void:
	elapsed += delta
	if elapsed >= 0.08:
		elapsed = 0.0
		queue_redraw()

func _draw() -> void:
	var quality: String = str(item.get("quality", "common"))
	var tint: Color = Color("d4b36e") if quality in ["rare", "epic", "legendary"] else Color("91a5a0")
	draw_set_transform(Vector2(0, -4), 0, Vector2(1, 0.34))
	draw_circle(Vector2.ZERO, 12, Color(0, 0, 0, 0.29))
	draw_set_transform(Vector2.ZERO)
	var texture: Texture2D = ART.item_texture(item)
	var float_y: float = sin(Time.get_ticks_msec() * 0.0025 + float(abs(hash(str(item.get("id", "")))) % 100)) * 2.0
	draw_texture_rect(texture, Rect2(-15, -29 + float_y, 30, 30), false)
	if quality in ["rare", "epic", "legendary"]:
		draw_arc(Vector2(0, -12 + float_y), 17.0, 0, TAU, 24, tint, 1.0, true)
