extends Area2D
## One visible projectile. It reports a candidate HIT in the established /v1 format;
## authoritative HP/ammo/ownership remains C's responsibility.
signal hit_target(payload: Dictionary)

const TILE_SIZE: float = 32.0
var shooter_id: String = ""
var shooter_node: Node2D = null
var weapon_id: String = ""
var weapon_type: String = "bow"
var attack_id: String = ""
var region_id: String = "overworld"
var direction: Vector2 = Vector2.RIGHT
var speed_px_s: float = 460.0
var remaining_px: float = 300.0
var finished: bool = false

func configure(shooter: Node2D, item: Dictionary, id: String, aim: Vector2) -> void:
    shooter_node = shooter
    shooter_id = str(shooter.get("entity_id"))
    weapon_id = str(item.get("id", ""))
    weapon_type = str(item.get("base_type", "bow"))
    region_id = str(shooter.get("region_id"))
    attack_id = id
    direction = aim.normalized() if aim.length() > 0.01 else Vector2.RIGHT
    speed_px_s = float(item.get("projectile_speed", 460.0))
    remaining_px = float(item.get("range_px", 300.0))

func _ready() -> void:
    collision_layer = 0
    collision_mask = 3  # Scenery layer 1, actors layer 2
    monitoring = true
    monitorable = false
    var hit_shape := CollisionShape2D.new()
    var circle := CircleShape2D.new()
    circle.radius = 4.5
    hit_shape.shape = circle
    add_child(hit_shape)
    var sprite := Sprite2D.new()
    sprite.texture = load("res://combat/assets/%s_projectile.png" % weapon_type) as Texture2D
    sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    sprite.rotation = direction.angle()
    # Offset only the drawn projectile to match the character's torso.
    # Collision stays at world-ground level and HIT payloads remain unchanged.
    if shooter_node != null:
        var shooter_visual := shooter_node.get_node_or_null("Visual") as AnimatedSprite2D
        if shooter_visual != null:
            sprite.position = shooter_visual.position
    add_child(sprite)
    body_entered.connect(_on_body_entered)
    add_to_group("world_projectiles")

func _physics_process(delta: float) -> void:
    if finished:
        return
    var distance: float = minf(remaining_px, speed_px_s * delta)
    global_position += direction * distance
    remaining_px -= distance
    if remaining_px <= 0.0:
        finished = true
        queue_free()

func _on_body_entered(body: Node2D) -> void:
    if finished or body == shooter_node:
        return
    if body.is_in_group("world_actors"):
        if not bool(body.get("alive")) or str(body.get("region_id")) != region_id:
            return
        finished = true
        hit_target.emit({
            "attack_id": attack_id,
            "attacker_id": shooter_id,
            "target_id": str(body.get("entity_id")),
            "weapon_id": weapon_id,
            "region_id": region_id,
            "attacker_tile": {"x": shooter_node.global_position.x / TILE_SIZE, "y": shooter_node.global_position.y / TILE_SIZE},
            "target_tile": {"x": body.global_position.x / TILE_SIZE, "y": body.global_position.y / TILE_SIZE}
        })
        queue_free()
    elif body is StaticBody2D:
        finished = true
        queue_free()
