extends Node2D
var item:Dictionary
func _ready()->void: queue_redraw()
func _draw()->void:
	draw_circle(Vector2.ZERO,9,Color(0,0,0,0.3))
	draw_line(Vector2(0,-22),Vector2(0,-5),Color("b5a0cf"),1)
	draw_rect(Rect2(-6,-11,12,9),Color("715334"))
	draw_rect(Rect2(-6,-11,12,9),Color("c3a676"),false)
	draw_rect(Rect2(-1,-11,2,9),Color("d8c39a"))
