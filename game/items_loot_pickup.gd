extends Node2D
## Offline ground-bag rendering. In production, C sends item ownership and coin drops.
var loot_id: String = ""
var contents: Array[Dictionary] = []
var coins: int = 0

func setup(id: String, items: Array[Dictionary], money: int) -> void:
    loot_id = id
    contents = items.duplicate(true)
    coins = money
    add_to_group("world_loot")
    queue_redraw()

func _draw() -> void:
    draw_circle(Vector2(0, 4), 12, Color(0.08, 0.07, 0.03, 0.5))
    draw_rect(Rect2(-9, -10, 18, 17), Color("#936037"))
    draw_rect(Rect2(-7, -13, 14, 7), Color("#b7874d"))
    draw_rect(Rect2(-4, -3, 8, 5), Color("#eac15e"))
    draw_string(ThemeDB.fallback_font, Vector2(-14, -21), "LOOT", HORIZONTAL_ALIGNMENT_LEFT, -1, 9, Color("#fff3c2"))
