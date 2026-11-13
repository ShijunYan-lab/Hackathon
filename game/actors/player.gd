extends "res://actors/actor.gd"
## Shared inventory/equipment slots live in Actor. 1=melee, 2=ranged.
## Z/X cycle available melee/ranged subtypes in the offline demo.
signal hit_detected(payload: Dictionary)
signal interaction_requested(npc_id: String)
signal pickup_requested(loot_id: String)
signal weapon_changed(weapon_name: String)
signal dodge_started(actor_id: String)

const SLASH_FX = preload("res://combat/slash_fx.gd")
const PROJECTILE = preload("res://combat/projectile.gd")
const INPUT_DEFAULTS = preload("res://controllers/input_defaults.gd")

@export var walk_speed: float = 108.0
@export var sprint_speed: float = 175.0
@export var dodge_speed: float = 295.0
@export var dodge_duration_ms: int = 230
@export var dodge_cooldown_ms: int = 850

var facing: Vector2 = Vector2.RIGHT
var movement_facing: Vector2 = Vector2.RIGHT
var previous_attack_ms: int = -10000
var last_dodge_ms: int = -10000
var dodge_until_ms: int = 0
var dodge_direction: Vector2 = Vector2.RIGHT
var attack_count: int = 0
var animation_attack_until_ms: int = 0
var weapon_tween: Tween = null

func _ready() -> void:
	INPUT_DEFAULTS.ensure_actions()
	actor_kind = "player"
	sprite_skin = "knight"
	super._ready()
	# Do not create mock items in the actor scene: the test map loads these separately.
	loadout_changed.connect(_on_loadout_changed)
	var camera := get_node_or_null("Camera2D") as Camera2D
	if camera != null:
		camera.position_smoothing_enabled = true
		camera.position_smoothing_speed = 7.0
		camera.make_current()

func _physics_process(delta: float) -> void:
	if not alive:
		velocity = Vector2.ZERO
		return
	if controls_locked:
		velocity = knockback_velocity
		move_and_slide()
		decay_knockback(delta)
		play_move_animation(Vector2.ZERO, facing)
		return
	var now_ms: int = Time.get_ticks_msec()
	var mouse_delta: Vector2 = get_global_mouse_position() - global_position
	if mouse_delta.length() > 6.0:
		facing = mouse_delta.normalized()
	var move_direction: Vector2 = Input.get_vector("move_left", "move_right", "move_up", "move_down")
	if move_direction.length() > 0.1:
		movement_facing = move_direction.normalized()
	var running: bool = Input.is_action_pressed("sprint") and move_direction.length() > 0.1
	if now_ms < dodge_until_ms:
		velocity = dodge_direction * dodge_speed + knockback_velocity
	else:
		velocity = move_direction * (sprint_speed if running else walk_speed) + knockback_velocity
	move_and_slide()
	decay_knockback(delta)
	if now_ms < dodge_until_ms:
		if visual.animation != &"dodge":
			play_dodge_visual(dodge_duration_ms)
	else:
		play_move_animation(velocity, facing, running)
	if now_ms >= animation_attack_until_ms:
		_pose_weapon_idle()
	if Input.is_action_just_pressed("slot_melee"):
		set_active_weapon_slot("melee")
	if Input.is_action_just_pressed("slot_ranged"):
		set_active_weapon_slot("ranged")
	if Input.is_action_just_pressed("attack"):
		try_attack()
	if Input.is_action_just_pressed("dodge"):
		try_dodge(move_direction)
	if Input.is_action_just_pressed("interact"):
		try_interact()

func try_attack() -> void:
	var now_ms: int = Time.get_ticks_msec()
	if now_ms < dodge_until_ms:
		return
	var item: Dictionary = active_weapon()
	if item.is_empty():
		return
	var stats: Dictionary = item.get("stats", {})
	var cooldown_ms: int = roundi(float(stats.get("cooldown_s", 0.50)) * 1000.0)
	if now_ms - previous_attack_ms < cooldown_ms:
		return
	previous_attack_ms = now_ms
	attack_count += 1
	var swing_ms: int = WEAPON_CATALOG.swing_duration(item)
	animation_attack_until_ms = now_ms + swing_ms
	play_attack_visual(swing_ms)
	_animate_weapon_swing(swing_ms, active_weapon_slot == "ranged")
	var attack_id: String = "%s_attack_%d" % [entity_id, attack_count]
	if active_weapon_slot == "ranged":
		_shoot_projectile(item, attack_id)
	else:
		_melee_hit_test(item, attack_id)

func _shoot_projectile(item: Dictionary, attack_id: String) -> void:
	var projectile = Area2D.new()
	projectile.set_script(PROJECTILE)
	projectile.configure(self, item, attack_id, facing)
	projectile.hit_target.connect(_relay_projectile_hit)
	get_tree().current_scene.add_child(projectile)
	projectile.global_position = global_position + facing * 17.0

func _relay_projectile_hit(payload: Dictionary) -> void:
	hit_detected.emit(payload)

func _melee_hit_test(item: Dictionary, attack_id: String) -> void:
	var fx := Node2D.new()
	fx.set_script(SLASH_FX)
	fx.rotation = facing.angle()
	fx.set("weapon_type", str(item.get("base_type", "sword")))
	fx.z_index = 20
	# Visual effect follows the torso of the 48x64 sheet; HIT geometry remains
	# in the shared 32px world-coordinate system.
	fx.position = visual.position
	add_child(fx)
	var range_px: float = WEAPON_CATALOG.attack_range(item)
	var type: String = str(item.get("base_type", "sword"))
	var aim_dot: float = 0.18 if type == "axe" else (0.42 if type == "hammer" else 0.32)
	for body in get_tree().get_nodes_in_group("world_actors"):
		if body == self or not body.alive or body.region_id != region_id:
			continue
		var to_body: Vector2 = body.global_position - global_position
		if to_body.length() < 1.0 or to_body.length() > range_px:
			continue
		if facing.dot(to_body.normalized()) < aim_dot:
			continue
		hit_detected.emit({
			"attack_id": attack_id, "attacker_id": entity_id,
			"target_id": str(body.entity_id), "weapon_id": str(item.get("id", "")),
			"region_id": region_id,
			"attacker_tile": {"x": global_position.x / TILE_SIZE, "y": global_position.y / TILE_SIZE},
			"target_tile": {"x": body.global_position.x / TILE_SIZE, "y": body.global_position.y / TILE_SIZE}
		})

func try_dodge(move_direction: Vector2 = Vector2.ZERO) -> void:
	var now_ms: int = Time.get_ticks_msec()
	if now_ms - last_dodge_ms < dodge_cooldown_ms or now_ms < animation_attack_until_ms:
		return
	last_dodge_ms = now_ms
	dodge_until_ms = now_ms + dodge_duration_ms
	dodge_direction = move_direction.normalized() if move_direction.length() > 0.1 else movement_facing
	play_dodge_visual(dodge_duration_ms)
	dodge_started.emit(entity_id)

func is_dodging() -> bool:
	return alive and Time.get_ticks_msec() < dodge_until_ms

func try_interact() -> void:
	var closest_id: String = ""
	var distance: float = 45.0
	for loot in get_tree().get_nodes_in_group("world_loot"):
		var d: float = global_position.distance_to(loot.global_position)
		if d < distance:
			distance = d
			closest_id = str(loot.loot_id)
	if not closest_id.is_empty():
		pickup_requested.emit(closest_id)
		return
	for body in get_tree().get_nodes_in_group("world_actors"):
		if body == self or not body.alive or body.actor_kind != "npc" or body.region_id != region_id:
			continue
		var d: float = global_position.distance_to(body.global_position)
		if d < distance:
			distance = d
			closest_id = str(body.entity_id)
	if not closest_id.is_empty():
		interaction_requested.emit(closest_id)

func equip_weapon(item: Dictionary) -> void:
	## D may invoke after C confirms ownership/equip; test caller can use mock loadout.
	if preview_equip_item(item):
		set_active_weapon_slot(WEAPON_CATALOG.group_for_type(str(item.get("base_type", ""))))

func equip_mock(base_type: String) -> void:
	## Backward-compatible test helper, not persistent equipment.
	var item: Dictionary = WEAPON_CATALOG.demo_item(base_type, entity_id)
	if not item.is_empty():
		equip_weapon(item)

func cycle_mock_weapon(group: String) -> void:
	var candidates: Array[String] = []
	for item in inventory_items:
		if WEAPON_CATALOG.group_for_type(str(item.get("base_type", ""))) == group:
			candidates.append(str(item.get("id", "")))
	if candidates.is_empty():
		return
	var current: String = str(equipment_slots.get(group, ""))
	var next_index: int = (candidates.find(current) + 1) % candidates.size()
	equipment_slots[group] = candidates[next_index]
	set_active_weapon_slot(group)

func receive_mock_loot(items: Array[Dictionary], amount_coins: int) -> void:
	## Offline test only; real acquisition is a C-confirmed PICKUP command.
	for item in items:
		var copy: Dictionary = item.duplicate(true)
		copy["owner_id"] = entity_id
		preview_add_item(copy)
	coins += maxi(0, amount_coins)
	loadout_changed.emit(entity_id)

func get_weapon_damage_mock() -> int:
	return int(active_weapon().get("stats", {}).get("damage", 0))

func get_weapon_name_mock() -> String:
	return str(active_weapon().get("name", "Unarmed"))

func _on_loadout_changed(_actor_id: String) -> void:
	_pose_weapon_idle(true)
	weapon_changed.emit(get_weapon_name_mock())

func _pose_weapon_idle(force: bool = false) -> void:
	if weapon_pivot == null or (not force and Time.get_ticks_msec() < animation_attack_until_ms):
		return
	if force and weapon_tween != null and weapon_tween.is_running():
		weapon_tween.kill()
	weapon_pivot.rotation = facing.angle() + PI / 2.0 - 0.30

func _animate_weapon_swing(duration_ms: int, ranged: bool = false) -> void:
	if weapon_pivot == null:
		return
	if weapon_tween != null and weapon_tween.is_running():
		weapon_tween.kill()
	var base_angle: float = facing.angle() + PI / 2.0
	if ranged:
		weapon_pivot.rotation = base_angle - 0.18
		weapon_tween = create_tween()
		weapon_tween.tween_property(weapon_pivot, "rotation", base_angle + 0.14, float(duration_ms) / 1000.0)
	else:
		weapon_pivot.rotation = base_angle - 1.1
		weapon_tween = create_tween()
		weapon_tween.set_trans(Tween.TRANS_CUBIC)
		weapon_tween.set_ease(Tween.EASE_OUT)
		weapon_tween.tween_property(weapon_pivot, "rotation", base_angle + 1.2, float(duration_ms) / 1000.0)

func set_controls_locked(value: bool) -> void:
	super.set_controls_locked(value)
	if value:
		velocity = Vector2.ZERO

func _kill_local() -> void:
	if weapon_visual != null:
		weapon_visual.visible = false
	super._kill_local()
