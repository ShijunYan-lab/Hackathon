extends Node2D
## Reusable melee telegraphs: sword narrow, axe wide, hammer heavy.
var age: float = 0.0
var weapon_type: String = "sword"

func _process(delta: float) -> void:
    age += delta
    if age >= (0.47 if weapon_type == "hammer" else (0.40 if weapon_type == "axe" else 0.27)):
        queue_free()
    else:
        queue_redraw()

func _draw() -> void:
    var duration: float = 0.47 if weapon_type == "hammer" else (0.40 if weapon_type == "axe" else 0.27)
    var alpha: float = maxf(0.0, 1.0 - age / duration)
    if weapon_type == "hammer":
        draw_arc(Vector2.ZERO, 29, -0.65, 0.72, 16, Color(1.0, 0.85, 0.34, alpha), 11.0)
        draw_circle(Vector2(30, 0), 9, Color(1.0, 0.93, 0.58, alpha * 0.7))
    elif weapon_type == "axe":
        draw_arc(Vector2.ZERO, 31, -1.1, 1.08, 22, Color(1.0, 0.55, 0.22, alpha), 8.0)
        draw_arc(Vector2.ZERO, 36, -1.1, 1.08, 22, Color(1.0, 0.88, 0.57, alpha * 0.7), 3.0)
    else:
        draw_arc(Vector2.ZERO, 25, -0.9, 0.87, 22, Color(0.68, 0.91, 1.0, alpha), 4.0)
        draw_arc(Vector2.ZERO, 31, -0.9, 0.87, 22, Color(0.96, 1.0, 1.0, alpha * 0.65), 2.0)
