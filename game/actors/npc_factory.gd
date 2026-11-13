extends RefCounted
## Generic NPC instantiation. D can feed C's ActorState to this factory.
## No fixed person/occupation is required; the backend owns identity, AI and count.
const NPC_SCENE = preload("res://actors/npc.tscn")

static func spawn(parent: Node2D, state: Dictionary, owned_items: Array, equipment: Dictionary, world_map: Node = null):
    var npc = NPC_SCENE.instantiate()
    npc.entity_id = str(state.get("id", "npc_generated"))
    npc.display_name = str(state.get("name", "Traveler"))
    npc.sprite_skin = str(state.get("appearance_key", "merchant"))
    npc.npc_type = str(state.get("visual_role", "civilian"))
    npc.region_id = str(state.get("region_id", "overworld"))
    npc.max_hp = int(state.get("max_hp", 65))
    npc.hp = int(state.get("hp", npc.max_hp))
    npc.world_map = world_map
    parent.add_child(npc)
    npc.apply_actor_state(state)
    npc.apply_inventory_snapshot(owned_items, equipment, int(state.get("coins", 0)))
    var preferred_slot: String = str(state.get("active_weapon_slot", ""))
    if preferred_slot not in ["melee", "ranged"]:
        preferred_slot = "ranged" if equipment.has("ranged") and not equipment.has("melee") else "melee"
    npc.set_active_weapon_slot(preferred_slot)
    if state.get("tile") is Dictionary:
        var tile: Dictionary = state["tile"]
        npc.global_position = Vector2(float(tile.get("x", 0.5)), float(tile.get("y", 0.5))) * 32.0
    return npc
