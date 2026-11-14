extends Node2D
## Small native pixel details; no external particle textures or dependencies.
var elapsed := 0.0
var player: Node2D
var chimneys: Array[Vector2] = []
var lanterns: Array[Vector2] = []

func _ready() -> void:
	for landmark in get_tree().get_nodes_in_group("buildings"):
		var sprite: Sprite2D=landmark.get_node("Art")
		chimneys.append(landmark.position+Vector2(-sprite.texture.get_width()*0.26,-sprite.texture.get_height()+15))
	for child in get_parent().get_node("World/Entities").get_children():
		if str(child.name).begins_with("Lamp"): lanterns.append(child.position+Vector2(0,-36))

func _process(delta: float) -> void:
	elapsed+=delta
	queue_redraw()

func _draw() -> void:
	if not player: return
	for chimney in chimneys:
		if chimney.distance_to(player.position)>430: continue
		for i in range(5):
			var age:=fmod(elapsed*0.35+i*0.21,1.0)
			var p:=chimney+Vector2(sin(age*5+i)*4+age*13,-age*50)
			var width:=3+floori(age*7)
			draw_rect(Rect2(p.floor(),Vector2(width,width)),Color(0.78,0.78,0.66,(1-age)*0.19))
	for lantern in lanterns:
		if lantern.distance_to(player.position)>400: continue
		var pulse:=0.04+sin(elapsed*3.0+lantern.x)*0.01
		draw_circle(lantern,15,Color(0.96,0.68,0.29,pulse))
		draw_circle(lantern,8,Color(1.0,0.79,0.41,pulse*1.5))
	if player.position.y<112*32:
		for i in range(18):
			var cell:=Vector2(floori(player.position.x/256),floori(player.position.y/256))*256
			var p:=cell+Vector2(posmod(i*79,512)-128,posmod(i*137,512)-128)
			p+=Vector2(sin(elapsed*0.5+i)*8,cos(elapsed*0.7+i)*5)
			draw_rect(Rect2(p.floor(),Vector2(1,1)),Color(0.8,0.85,0.53,0.35+sin(elapsed+i)*0.2))
