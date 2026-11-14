extends Node2D
## Visibility polygon is clipped by actual sight-blocker physics, not just a vignette.
const RAYS := 256
var player: CharacterBody2D
var distances := PackedFloat32Array()
var radius := 290.0
var target_radius := 290.0
var timer := 0.0
var enabled := true
var last_origin := Vector2.ZERO
var ground_shadow: Node2D

func _ready() -> void:
	distances.resize(RAYS)
	distances.fill(radius)
	z_index = 100
	ground_shadow = Node2D.new()
	ground_shadow.name = "GroundSightShadows"
	var world := get_parent().get_node("World")
	world.add_child(ground_shadow)
	world.move_child(ground_shadow,2)
	ground_shadow.draw.connect(draw_ground_shadow)

func _physics_process(delta: float) -> void:
	if not is_instance_valid(player): return
	var p := player.global_position
	enabled = p.y < 56*32 or p.x > 98*32
	target_radius = 110.0 if p.y < 56*32 else (142.0 if p.x > 98*32 else 290.0)
	radius = move_toward(radius,target_radius,delta*230)
	global_position = p+Vector2(0,-18)
	ground_shadow.global_position = global_position
	timer -= delta
	if timer <= 0:
		timer = 1.0/20.0
		update_visibility()
	queue_redraw()
	ground_shadow.queue_redraw()

func update_visibility() -> void:
	var space := get_world_2d().direct_space_state
	last_origin = global_position
	for i in range(RAYS):
		var v := Vector2.from_angle(TAU*i/RAYS)
		var query := PhysicsRayQueryParameters2D.create(last_origin,last_origin+v*radius,2)
		query.hit_from_inside = false
		var hit := space.intersect_ray(query)
		distances[i] = minf(radius,last_origin.distance_to(hit.position)+12.0) if not hit.is_empty() else radius

func visible_from_player(point: Vector2) -> bool:
	var offset := point-last_origin
	if offset.length()>radius: return false
	var index := posmod(roundi(offset.angle()/TAU*RAYS),RAYS)
	return offset.length()<=distances[index]

func _draw() -> void:
	if not enabled: return
	var fog := Color("17282b")
	for i in range(RAYS):
		var j := (i+1)%RAYS
		var a := Vector2.from_angle(TAU*i/RAYS)
		var b := Vector2.from_angle(TAU*(i+1)/RAYS)
		var da := radius
		var db := radius
		# Opaque unexplored area, with a narrow 10px stepped penumbra.
		draw_colored_polygon(PackedVector2Array([a*da,b*db,b*1800,a*1800]),fog)
		for step in range(4):
			var outer := step*2.5
			var inner := (step+1)*2.5
			var shade := fog
			shade.a = 0.76-step*0.18
			draw_colored_polygon(PackedVector2Array([a*maxf(0,da-inner),b*maxf(0,db-inner),b*(db-outer),a*(da-outer)]),shade)

func draw_ground_shadow() -> void:
	if not enabled: return
	for i in range(RAYS):
		var j := (i+1)%RAYS
		var a := Vector2.from_angle(TAU*i/RAYS)
		var b := Vector2.from_angle(TAU*(i+1)/RAYS)
		if distances[i]>=radius and distances[j]>=radius: continue
		var p := a*minf(radius,distances[i])
		var q := b*minf(radius,distances[j])
		var r := b*radius
		var s := a*radius
		for triangle in [[p,q,r],[p,r,s]]:
			var cross_value: float = (triangle[1]-triangle[0]).cross(triangle[2]-triangle[0])
			if absf(cross_value)>0.01:
				ground_shadow.draw_colored_polygon(PackedVector2Array(triangle),Color(0.09,0.16,0.17,0.91))
