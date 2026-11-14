extends CharacterBody2D
## D-owned, replaceable exploration body. No damage, inventory or server authority.
signal region_changed(region_id: String)
const Layout = preload("res://maps/world_layout.gd")
const WALK_SPEED := 150.0
const RUN_SPEED := 250.0
var locked := false
var direction := 0
var female := false
var clock := 0.0
var region_id := "market"
var sprite: Sprite2D
var camera: Camera2D
var male_texture: Texture2D = preload("res://assets/characters/player_male.png")
var female_texture: Texture2D = preload("res://assets/characters/player_female.png")

func _ready() -> void:
	collision_layer = 4
	collision_mask = 5
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	var shape := CollisionShape2D.new()
	var capsule := CapsuleShape2D.new()
	capsule.radius = 7
	capsule.height = 18
	shape.shape = capsule
	shape.position = Vector2(0,-5)
	shape.rotation = PI/2
	add_child(shape)
	sprite = Sprite2D.new()
	sprite.texture = male_texture
	sprite.hframes = 8
	sprite.vframes = 4
	sprite.position = Vector2(0,-30)
	add_child(sprite)
	camera = Camera2D.new()
	camera.position = Vector2(0,-48)
	camera.position_smoothing_enabled = false
	camera.limit_left = 0
	camera.limit_top = 0
	camera.limit_right = Layout.SIZE.x*32
	camera.limit_bottom = Layout.SIZE.y*32
	add_child(camera)
	queue_redraw()

func _draw() -> void:
	draw_ellipse_shadow()

func draw_ellipse_shadow() -> void:
	draw_set_transform(Vector2(0,-1),0,Vector2(1,0.38))
	draw_circle(Vector2.ZERO,12,Color(0.08,0.13,0.12,0.45))
	draw_set_transform(Vector2.ZERO)

func _physics_process(delta: float) -> void:
	var input := Vector2.ZERO if locked else Input.get_vector("move_left","move_right","move_up","move_down")
	velocity = input*(RUN_SPEED if Input.is_action_pressed("sprint") else WALK_SPEED)
	move_and_slide()
	# Belt-and-braces guard for teleports and future replacement controllers.
	position = position.clamp(Vector2(40,42),Vector2(Layout.SIZE*32)-Vector2(40,36))
	if input != Vector2.ZERO:
		clock += delta*(13.0 if Input.is_action_pressed("sprint") else 8.0)
		if absf(input.x)>absf(input.y): direction = 1 if input.x<0 else 2
		else: direction = 3 if input.y<0 else 0
		sprite.frame = direction*8+1+int(clock)%6
	else:
		clock = 0.0
		sprite.frame = direction*8
	var new_region: String = Layout.region_at(global_position)
	if new_region != region_id:
		region_id = new_region
		region_changed.emit(region_id)

func set_controls_locked(value: bool) -> void:
	locked = value
	if locked: velocity=Vector2.ZERO

func switch_appearance() -> void:
	female = not female
	sprite.texture = female_texture if female else male_texture

func collect_checkpoint() -> Dictionary:
	var tile: Vector2 = Layout.region_tile(global_position)
	return {"region_id":Layout.region_at(global_position),"positions":[{"actor_id":"local_preview_player","tile":{"x":tile.x,"y":tile.y}}]}
