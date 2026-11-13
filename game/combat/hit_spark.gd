extends Node2D
## Small burst at a confirmed local mock hit. Replace on server confirmation in final game.
var age: float = 0.0
const DURATION: float = 0.22

func _process(delta: float) -> void:
    age += delta
    if age >= DURATION:
        queue_free()
        return
    queue_redraw()

func _draw() -> void:
    var fade: float = 1.0 - age / DURATION
    draw_circle(Vector2.ZERO, 4.0 + age * 13.0, Color(1, 0.83, 0.52, fade * 0.45))
    for i in range(8):
        var ang: float = float(i) * TAU / 8.0
        var from_p := Vector2.RIGHT.rotated(ang) * (3.0 + age * 14.0)
        var to_p := Vector2.RIGHT.rotated(ang) * (9.0 + age * 27.0)
        draw_line(from_p, to_p, Color(1, 0.95, 0.74, fade), 2.0)
