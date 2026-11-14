extends Node2D
## Small procedural chest; replace the drawing without changing ownership logic.
var data: Dictionary = {}
func _draw() -> void:
	var opened: bool = bool(data.get("opened", false))
	draw_ellipse_shadow()
	draw_rect(Rect2(-13, -18, 26, 17), Color("735031"))
	draw_rect(Rect2(-13, -18, 26, 17), Color("2e2924"), false, 2)
	draw_rect(Rect2(-14, -25 if opened else -21, 28, 7), Color("9d7641"))
	draw_rect(Rect2(-8, -20, 3, 19), Color("b99b59"))
	draw_rect(Rect2(5, -20, 3, 19), Color("b99b59"))
	draw_rect(Rect2(-2, -15, 4, 6), Color("d5bf79"))
	if data.get("kind") == "merchant": draw_circle(Vector2(0, -29), 3, Color("caa65a"))
func draw_ellipse_shadow() -> void:
	draw_set_transform(Vector2.ZERO, 0, Vector2(1, 0.3))
	draw_circle(Vector2.ZERO, 16, Color(0, 0, 0, 0.3))
	draw_set_transform(Vector2.ZERO)
