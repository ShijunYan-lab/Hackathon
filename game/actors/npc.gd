extends "res://actors/actor.gd"
## Generic body for arbitrarily generated NPCs. No model or fixed NPC biographies.
## C schedules task IDs, A executes visible movement/combat, B owns cognition.
signal hit_detected(payload: Dictionary)
signal task_reported(payload: Dictionary)

const PROJECTILE = preload("res://combat/projectile.gd")

@export_enum("civilian", "guard", "wolf", "wisp") var npc_type: String = "civilian"
var player_ref: Node2D = null
var world_map = null
var active_task: Dictionary = {}
var current_task_id: String = ""
var target_position: Vector2 = Vector2.ZERO
var task_stuck_s: float = 0.0
var attack_counter: int = 0
var last_attack_ms: int = -10000
var completed_move: bool = false
var path_points: PackedVector2Array = PackedVector2Array()
var path_index: int = 0
var path_destination_tile: Vector2i = Vector2i(-999, -999)
var path_refresh_s: float = 0.0

func _ready() -> void:
	actor_kind = "monster" if npc_type in ["wolf", "wisp"] else "npc"
	super._ready()

func _physics_process(delta: float) -> void:
	if not alive:
		velocity = Vector2.ZERO
		return
	path_refresh_s -= delta
	if not current_task_id.is_empty():
		_execute_active_task(delta)
		return
	if npc_type in ["wolf", "wisp"]:
		_monster_logic(delta)
		return
	velocity = knockback_velocity
	move_and_slide()
	decay_knockback(delta)
	play_move_animation(velocity, velocity if velocity.length() > 0.1 else Vector2.RIGHT)

func _monster_logic(delta: float) -> void:
	var target = _nearest_nonmonster(195.0)
	if target == null:
		velocity = knockback_velocity
		move_and_slide()
		decay_knockback(delta)
		play_move_animation(Vector2.ZERO, Vector2.RIGHT)
		return
	var offset: Vector2 = target.global_position - global_position
	var range_target: float = 135.0 if npc_type == "wisp" else 29.0
	if offset.length() > range_target:
		_move_toward(delta, target.global_position, range_target - 9.0)
	else:
		velocity = knockback_velocity
		move_and_slide()
		decay_knockback(delta)
		play_move_animation(Vector2.ZERO, offset)
	if offset.length() < (170.0 if npc_type == "wisp" else 37.0):
		_attack_target(target)

func _nearest_nonmonster(max_distance: float):
	var result = null
	var best_distance: float = max_distance
	for actor in get_tree().get_nodes_in_group("world_actors"):
		if actor == self or not actor.alive or actor.region_id != region_id or actor.actor_kind == "monster":
			continue
		var distance: float = global_position.distance_to(actor.global_position)
		if distance < best_distance:
			best_distance = distance
			result = actor
	return result

func _nearest_monster(max_distance: float):
	var result = null
	var best_distance: float = max_distance
	for actor in get_tree().get_nodes_in_group("world_actors"):
		if actor == self or not actor.alive or actor.region_id != region_id or actor.actor_kind != "monster":
			continue
		var distance: float = global_position.distance_to(actor.global_position)
		if distance < best_distance:
			best_distance = distance
			result = actor
	return result

func _attack_target(target) -> void:
	var now_ms: int = Time.get_ticks_msec()
	var weapon: Dictionary = active_weapon()
	var is_ranged: bool = active_weapon_slot == "ranged" and not weapon.is_empty()
	var range_px: float = WEAPON_CATALOG.attack_range(weapon) if not weapon.is_empty() else 32.0
	if target.global_position.distance_to(global_position) > range_px:
		return
	var cooldown_ms: int = roundi(float(weapon.get("stats", {}).get("cooldown_s", 1.15)) * 1000.0)
	if now_ms - last_attack_ms < cooldown_ms:
		return
	last_attack_ms = now_ms
	attack_counter += 1
	var aim: Vector2 = (target.global_position - global_position).normalized()
	var swing_ms: int = WEAPON_CATALOG.swing_duration(weapon) if not weapon.is_empty() else 270
	play_attack_visual(swing_ms)
	if weapon_pivot != null:
		weapon_pivot.rotation = aim.angle() + PI / 2.0
	var attack_id: String = "%s_attack_%d" % [entity_id, attack_counter]
	if is_ranged:
		var projectile = Area2D.new()
		projectile.set_script(PROJECTILE)
		projectile.configure(self, weapon, attack_id, aim)
		projectile.hit_target.connect(_relay_projectile_hit)
		get_tree().current_scene.add_child(projectile)
		projectile.global_position = global_position + aim * 17.0
	elif not (target.has_method("is_dodging") and target.is_dodging()):
		hit_detected.emit(_hit_payload(target, attack_id, str(weapon.get("id", "natural_attack"))))

func _relay_projectile_hit(payload: Dictionary) -> void:
	hit_detected.emit(payload)

func _hit_payload(target, attack_id: String, weapon_id: String) -> Dictionary:
	return {
		"attack_id": attack_id, "attacker_id": entity_id,
		"target_id": str(target.entity_id), "weapon_id": weapon_id,
		"region_id": region_id,
		"attacker_tile": {"x": global_position.x / TILE_SIZE, "y": global_position.y / TILE_SIZE},
		"target_tile": {"x": target.global_position.x / TILE_SIZE, "y": target.global_position.y / TILE_SIZE}
	}

func execute_task(task: Dictionary) -> void:
	if not alive:
		return
	var task_id: String = str(task.get("id", ""))
	var kind: String = str(task.get("kind", ""))
	if task_id.is_empty() or task_id == current_task_id:
		return
	if kind not in ["MOVE", "ESCORT", "ATTACK", "FLEE"]:
		return
	if task.get("target_region_id") != null and str(task.get("target_region_id")) != region_id:
		return
	current_task_id = task_id
	active_task = task.duplicate(true)
	task_stuck_s = 0.0
	completed_move = false
	path_points.clear()
	path_index = 0
	path_destination_tile = Vector2i(-999, -999)
	if kind in ["MOVE", "FLEE"] and not (task.get("target_tile") is Dictionary):
		_finish_task("failed", "missing_target_tile")
		return
	if task.get("target_tile") is Dictionary:
		var tile: Dictionary = task["target_tile"]
		target_position = Vector2(float(tile.get("x", 0)), float(tile.get("y", 0))) * TILE_SIZE

func _execute_active_task(delta: float) -> void:
	match str(active_task.get("kind", "")):
		"MOVE", "FLEE":
			_move_to_position(delta)
		"ESCORT":
			_escort(delta)
		"ATTACK":
			var victim = _actor_by_id(str(active_task.get("target_id", "")))
			if victim == null:
				_finish_task("failed", "target_missing")
			elif not victim.alive:
				_finish_task("succeeded", "")
			else:
				var item: Dictionary = active_weapon()
				var attack_range: float = WEAPON_CATALOG.attack_range(item) if not item.is_empty() else 33.0
				_move_toward(delta, victim.global_position, attack_range * 0.70)
				_attack_target(victim)
		_:
			_finish_task("failed", "unsupported_task")

func _move_to_position(delta: float) -> void:
	if global_position.distance_to(target_position) <= 15.0:
		velocity = Vector2.ZERO
		completed_move = true
		_finish_task("succeeded", "")
		return
	_move_toward(delta, target_position, 10.0)

func _move_toward(delta: float, destination: Vector2, stop_distance: float) -> void:
	if global_position.distance_to(destination) <= stop_distance:
		velocity = knockback_velocity
		move_and_slide()
		decay_knockback(delta)
		play_move_animation(Vector2.ZERO, Vector2.RIGHT)
		return
	var waypoint: Vector2 = destination
	if world_map != null and world_map.has_method("find_path"):
		var dest_tile: Vector2i = world_map.world_to_cell(destination)
		if dest_tile != path_destination_tile or path_refresh_s <= 0.0 or path_points.is_empty():
			path_destination_tile = dest_tile
			path_points = world_map.find_path(global_position, destination)
			path_index = 1 if path_points.size() >= 2 else 0
			path_refresh_s = 1.0
		if not path_points.is_empty():
			if path_index >= path_points.size():
				waypoint = destination
			else:
				waypoint = path_points[path_index]
				if global_position.distance_to(waypoint) < 11.0:
					path_index += 1
					waypoint = path_points[path_index] if path_index < path_points.size() else destination
	var before: Vector2 = global_position
	var motion: Vector2 = (waypoint - global_position).normalized()
	velocity = motion * move_speed + knockback_velocity
	move_and_slide()
	decay_knockback(delta)
	play_move_animation(velocity, motion)
	if weapon_pivot != null:
		weapon_pivot.rotation = motion.angle() + PI / 2.0 - 0.2
	if global_position.distance_to(before) < 0.15:
		task_stuck_s += delta
	else:
		task_stuck_s = 0.0
	if task_stuck_s > 4.0:
		_finish_task("failed", "path_blocked")

func _escort(delta: float) -> void:
	var escorted = _actor_by_id(str(active_task.get("target_id", "")))
	if escorted == null or not escorted.alive:
		_finish_task("failed", "escort_target_missing")
		return
	var enemy = _nearest_monster(125.0)
	if enemy != null:
		var item: Dictionary = active_weapon()
		var stop_px: float = 95.0 if active_weapon_slot == "ranged" and not item.is_empty() else 28.0
		_move_toward(delta, enemy.global_position, stop_px)
		_attack_target(enemy)
	else:
		_move_toward(delta, escorted.global_position + Vector2(23, 15), 30.0)
	if bool(escorted.get("completed_move")) and global_position.distance_to(escorted.global_position) < 75.0:
		_finish_task("succeeded", "")

func _actor_by_id(actor_id: String):
	for actor in get_tree().get_nodes_in_group("world_actors"):
		if str(actor.entity_id) == actor_id and str(actor.region_id) == region_id:
			return actor
	return null

func _finish_task(status: String, reason: String) -> void:
	var old_id: String = current_task_id
	current_task_id = ""
	active_task = {}
	velocity = Vector2.ZERO
	path_points.clear()
	if old_id.is_empty():
		return
	task_reported.emit({
		"task_id": old_id, "status": status, "actor_id": entity_id,
		"region_id": region_id,
		"tile": {"x": global_position.x / TILE_SIZE, "y": global_position.y / TILE_SIZE},
		"failure_code": reason if not reason.is_empty() else null
	})

func _kill_local() -> void:
	super._kill_local()
	if not current_task_id.is_empty():
		_finish_task("failed", "actor_dead")

func apply_actor_state(actor: Dictionary) -> void:
	super.apply_actor_state(actor)
	if actor_kind == "monster":
		npc_type = "wisp" if sprite_skin == "wisp" else "wolf"
	elif npc_type != "guard":
		npc_type = "civilian"
	if not alive and not current_task_id.is_empty():
		_finish_task("failed", "actor_dead")
