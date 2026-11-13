extends CharacterBody2D
## Reusable visual actor. Only the backend owns permanent combat and inventory state.
signal actor_died(actor_id: String)
signal loadout_changed(actor_id: String)

const HIT_SPARK = preload("res://combat/hit_spark.gd")
const WEAPON_CATALOG = preload("res://actors/weapon_catalog.gd")
const SPRITE_SHEET = preload("res://actors/sprite_sheet_profile.gd")
const TILE_SIZE: float = 32.0

@export var entity_id: String = "actor_001"
@export var display_name: String = "Actor"
@export_enum("player", "npc", "monster") var actor_kind: String = "npc"
@export var region_id: String = "market"
@export var max_hp: int = 70
@export var hp: int = 70
@export var sprite_skin: String = "merchant"
# Actor origin stays at ground level; change these two exports if a sheet has extra padding.
@export var visual_foot_y: float = 11.0
@export var hand_offset_y: float = 0.0
var visual_frame_size: Vector2i = Vector2i(32, 32)

var alive: bool = true
var move_speed: float = 75.0
var knockback_velocity: Vector2 = Vector2.ZERO
var animation_lock_until_ms: int = 0
var controls_locked: bool = false
## Local presentation of the authoritative C inventory. A game-side mock may mutate it
## ONLY in offline test scenes. The same fields apply to player and all NPCs.
var inventory_items: Array[Dictionary] = []
var coins: int = 0
var equipment_slots: Dictionary = {
	"melee": "", "ranged": "", "offhand": "", "head": "",
	"chest": "", "hands": "", "legs": "", "boots": "",
	"accessory": "", "ring_1": "", "ring_2": ""
}
var active_weapon_slot: String = "melee"
var weapon_pivot: Node2D = null
var weapon_visual: Sprite2D = null
@onready var visual: AnimatedSprite2D = $Visual

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	collision_layer = 2  # Actors are hit targets, but do not block each other
	collision_mask = 1  # Solid scenery
	add_to_group("world_actors")
	max_hp = maxi(1, max_hp)
	hp = clampi(hp, 0, max_hp)
	alive = hp > 0
	_load_visual_frames()
	weapon_pivot = get_node_or_null("WeaponPivot") as Node2D
	weapon_visual = get_node_or_null("WeaponPivot/WeaponVisual") as Sprite2D
	_align_visual_to_ground()
	_update_weapon_visual()
	queue_redraw()

func _load_visual_frames() -> void:
	var built: Dictionary = SPRITE_SHEET.build(sprite_skin)
	if built.is_empty():
		visual.visible = false
		return
	visual.visible = true
	visual_frame_size = built["frame_size"]
	visual.sprite_frames = built["frames"]
	visual.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_align_visual_to_ground()
	_play_anim("idle")
	queue_redraw()

func _align_visual_to_ground() -> void:
	# For 32px rows, this matches the old Visual.y=-5 and WeaponPivot.y=-6.
	# For new 48x64 rows: Visual.y=-21, WeaponPivot.y=-22.
	# Collision radius (8px) and world 32px tiles are unchanged.
	if visual != null:
		visual.position = Vector2(0.0, visual_foot_y - float(visual_frame_size.y) * 0.5)
	if weapon_pivot != null:
		weapon_pivot.position = Vector2(0.0, visual_foot_y - float(visual_frame_size.y) * 0.5 - 1.0 + hand_offset_y)

func _sprite_top_y() -> float:
	return visual_foot_y - float(visual_frame_size.y)

func _draw() -> void:
	draw_circle(Vector2(0, 10), 10, Color(0.05, 0.08, 0.09, 0.35))
	var top_y: float = _sprite_top_y()
	if alive:
		draw_rect(Rect2(-13.0, top_y - 4.0, 26.0, 4.0), Color(0.1, 0.12, 0.16, 0.9))
		draw_rect(Rect2(-12.0, top_y - 3.0, 24.0 * float(hp) / float(maxi(1, max_hp)), 2.0), Color(0.34, 0.87, 0.55))
	draw_string(ThemeDB.fallback_font, Vector2(-27.0, top_y - 8.0), display_name, HORIZONTAL_ALIGNMENT_LEFT, -1, 10, Color(0.98, 0.97, 0.88))

func _play_anim(name: String) -> void:
	if visual.sprite_frames == null:
		return
	if not visual.sprite_frames.has_animation(name):
		return
	if visual.animation != StringName(name) or not visual.is_playing():
		visual.play(name)

func play_move_animation(motion: Vector2, facing: Vector2, sprinting: bool = false) -> void:
	if not alive:
		return
	if facing.x < -0.08:
		visual.flip_h = true
	elif facing.x > 0.08:
		visual.flip_h = false
	if Time.get_ticks_msec() < animation_lock_until_ms:
		return
	if motion.length() <= 5.0:
		_play_anim("idle")
	elif sprinting:
		_play_anim("sprint")
	else:
		_play_anim("run")

func play_attack_visual(duration_ms: int = 300) -> void:
	if not alive:
		return
	animation_lock_until_ms = Time.get_ticks_msec() + duration_ms
	if visual.sprite_frames != null:
		var count: int = visual.sprite_frames.get_frame_count("attack")
		visual.sprite_frames.set_animation_speed("attack", 1000.0 * float(count) / float(maxi(150, duration_ms)))
		visual.play("attack")

func play_dodge_visual(duration_ms: int = 220) -> void:
	if not alive:
		return
	animation_lock_until_ms = Time.get_ticks_msec() + duration_ms
	if visual.sprite_frames != null:
		var count: int = visual.sprite_frames.get_frame_count("dodge")
		visual.sprite_frames.set_animation_speed("dodge", 1000.0 * float(count) / float(maxi(120, duration_ms)))
		visual.play("dodge")

func _hurt_visual(amount: int, from_position: Vector2) -> void:
	if amount <= 0 or not alive:
		return
	visual.play("hurt")
	animation_lock_until_ms = Time.get_ticks_msec() + 220
	visual.modulate = Color(1.0, 0.56, 0.56)
	create_tween().tween_property(visual, "modulate", Color.WHITE, 0.2)
	if from_position.distance_to(global_position) > 0.1:
		knockback_velocity = (global_position - from_position).normalized() * 125.0
	var number := Label.new()
	number.text = str(amount)
	number.position = Vector2(-9.0, _sprite_top_y() - 22.0)
	number.add_theme_color_override("font_color", Color(1.0, 0.85, 0.48))
	number.add_theme_font_size_override("font_size", 14)
	number.z_index = 30
	add_child(number)
	var spark := Node2D.new()
	spark.set_script(HIT_SPARK)
	spark.z_index = 29
	spark.position = visual.position
	add_child(spark)
	var tween: Tween = create_tween().set_parallel(true)
	tween.tween_property(number, "position", number.position + Vector2(0, -18), 0.4)
	tween.tween_property(number, "modulate:a", 0.0, 0.4)
	tween.set_parallel(false).tween_callback(number.queue_free)

func decay_knockback(delta: float) -> void:
	knockback_velocity = knockback_velocity.move_toward(Vector2.ZERO, delta * 700.0)

func apply_damage_mock(amount: int, _attacker_id: String = "", from_position: Vector2 = Vector2.ZERO) -> void:
	## Offline test only; do not call this in networked play.
	if not alive:
		return
	var original_hp: int = hp
	hp = maxi(0, hp - maxi(0, amount))
	if hp < original_hp:
		_hurt_visual(original_hp - hp, from_position)
	if hp == 0:
		_kill_local()
	queue_redraw()

func _kill_local() -> void:
	if not alive:
		return
	alive = false
	velocity = Vector2.ZERO
	collision_layer = 0
	collision_mask = 0
	animation_lock_until_ms = 0
	if visual.sprite_frames != null:
		visual.play("death")
	actor_died.emit(entity_id)

func apply_actor_state(actor: Dictionary) -> void:
	## D calls after C provides a valid ActorState snapshot.
	var old_hp: int = hp
	var old_alive: bool = alive
	entity_id = str(actor.get("id", entity_id))
	display_name = str(actor.get("name", display_name))
	actor_kind = str(actor.get("kind", actor_kind))
	region_id = str(actor.get("region_id", region_id))
	coins = int(actor.get("coins", actor.get("gold", coins)))
	var next_skin: String = str(actor.get("appearance_key", sprite_skin))
	if next_skin != sprite_skin:
		sprite_skin = next_skin
		_load_visual_frames()
	max_hp = maxi(1, int(actor.get("max_hp", max_hp)))
	hp = clampi(int(actor.get("hp", hp)), 0, max_hp)
	if actor.has("tile") and actor["tile"] is Dictionary:
		var location: Dictionary = actor["tile"]
		var active_id: Variant = get("current_task_id")
		if actor_kind != "player" and (active_id == null or str(active_id).is_empty()):
			global_position = Vector2(float(location.get("x", 0)), float(location.get("y", 0))) * TILE_SIZE
	var server_alive: bool = bool(actor.get("alive", hp > 0))
	if old_alive and hp < old_hp:
		_hurt_visual(old_hp - hp, Vector2.ZERO)
	if not server_alive:
		if old_alive:
			_kill_local()
		alive = false
	else:
		alive = true
		collision_layer = 2
		collision_mask = 1
		if not old_alive:
			_play_anim("idle")
	if actor.has("equipment") and actor["equipment"] is Dictionary:
		_set_equipment_ids(actor["equipment"])
	_update_weapon_visual()
	queue_redraw()

func apply_server_state(data: Dictionary) -> void:
	## Backwards-compatible name for the previous A prototype.
	apply_actor_state(data)

func collect_checkpoint() -> Dictionary:
	return {"actor_id": entity_id, "tile": {"x": global_position.x / TILE_SIZE, "y": global_position.y / TILE_SIZE}}

func set_controls_locked(value: bool) -> void:
	controls_locked = value

func witness_candidate_ids(target_position: Vector2, exclude_target_id: String) -> Array[String]:
	var result: Array[String] = []
	for actor in get_tree().get_nodes_in_group("world_actors"):
		if actor == self or not actor.alive or actor.entity_id == exclude_target_id:
			continue
		if actor.region_id == region_id and actor.global_position.distance_to(target_position) <= 110.0:
			result.append(str(actor.entity_id))
	return result


## ===== Shared NPC and player inventory / equipment presentation =====
## D: pass only owned ItemState objects and an equipment slot-to-item-ID map.
## The current server v1 only knows equipped_item_id; multi-slot and coins need C's
## protocol extension before being treated as persistent or authoritative.
func apply_inventory_snapshot(items: Array, equipped: Dictionary, total_coins: int) -> void:
	inventory_items.clear()
	for value in items:
		if value is Dictionary:
			var item: Dictionary = value
			if str(item.get("owner_id", entity_id)) == entity_id:
				inventory_items.append(item.duplicate(true))
	coins = maxi(0, total_coins)
	_set_equipment_ids(equipped)
	_update_weapon_visual()
	loadout_changed.emit(entity_id)

func _set_equipment_ids(slots: Dictionary) -> void:
	for slot in WEAPON_CATALOG.EQUIPMENT_SLOTS:
		if slots.has(slot):
			equipment_slots[slot] = str(slots[slot])
	_update_weapon_visual()
	loadout_changed.emit(entity_id)

func find_item(item_id: String) -> Dictionary:
	for item in inventory_items:
		if str(item.get("id", "")) == item_id:
			return item
	return {}

func active_weapon() -> Dictionary:
	var equipped_id: String = str(equipment_slots.get(active_weapon_slot, ""))
	return find_item(equipped_id)

func equipment_item(slot: String) -> Dictionary:
	return find_item(str(equipment_slots.get(slot, "")))

func set_active_weapon_slot(slot: String) -> void:
	if slot != "melee" and slot != "ranged":
		return
	active_weapon_slot = slot
	_update_weapon_visual()
	loadout_changed.emit(entity_id)

func _update_weapon_visual() -> void:
	if weapon_visual == null:
		return
	var item: Dictionary = active_weapon()
	var base_type: String = str(item.get("base_type", ""))
	var sprite_path: String = WEAPON_CATALOG.icon_path(base_type)
	if sprite_path.is_empty():
		weapon_visual.texture = null
	else:
		weapon_visual.texture = load(sprite_path) as Texture2D
	weapon_visual.visible = alive and weapon_visual.texture != null
	weapon_visual.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	weapon_visual.scale = Vector2.ONE * (1.14 if base_type == "hammer" else 1.0)

func preview_equip_item(item: Dictionary) -> bool:
	## Offline prototype only: C must confirm an equip command in the full game.
	var slot: String = WEAPON_CATALOG.equipment_slot(item)
	if slot.is_empty():
		return false
	var item_id: String = str(item.get("id", ""))
	if item_id.is_empty():
		return false
	var found: bool = false
	for i in range(inventory_items.size()):
		if str(inventory_items[i].get("id", "")) == item_id:
			inventory_items[i] = item.duplicate(true)
			found = true
			break
	if not found:
		inventory_items.append(item.duplicate(true))
	equipment_slots[slot] = item_id
	_update_weapon_visual()
	loadout_changed.emit(entity_id)
	return true

func preview_add_item(item: Dictionary) -> void:
	## Offline test only. Preserve the original item id; do not duplicate a drop.
	if str(item.get("id", "")).is_empty() or not find_item(str(item["id"])).is_empty():
		return
	inventory_items.append(item.duplicate(true))
	loadout_changed.emit(entity_id)

func mock_drops() -> Dictionary:
	## Caller must generate one bag per death. Real drops are created by C.
	var contents: Array[Dictionary] = []
	for item in inventory_items:
		if not bool(item.get("soulbound", false)):
			contents.append(item.duplicate(true))
	return {"coins": coins, "items": contents}

func inventory_for_ui() -> Dictionary:
	return {
		"actor_id": entity_id,
		"name": display_name,
		"coins": coins,
		"items": inventory_items.duplicate(true),
		"equipment": equipment_slots.duplicate(true),
		"active_weapon_slot": active_weapon_slot
	}
