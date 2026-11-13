extends Node2D
## A-only OFFLINE MOCK, deliberately separate from B/C real AI and persistent world.
## One continuous map, following camera, A* NPC travel, two weapon slots,
## inventory+coins+loot for ALL actors. Open game/main.tscn with F5 to test.
const WORLD_SCENE = preload("res://maps/seamless_world.tscn")
const PLAYER_SCENE = preload("res://actors/player.tscn")
const NPC_FACTORY = preload("res://actors/npc_factory.gd")
const WEAPONS = preload("res://actors/weapon_catalog.gd")
const INPUT_DEFAULTS = preload("res://controllers/input_defaults.gd")
const LOOT_SCRIPT = preload("res://items_loot_pickup.gd")
const INVENTORY_PANEL = preload("res://ui/equipment_panel.gd")

var world_map = null
var player = null
var entities: Dictionary = {}
var ground_loot: Dictionary = {}
var processed_attacks: Dictionary = {}
var processed_deaths: Dictionary = {}
var info_label: Label = null
var logs_label: Label = null
var weapon_icons: Array[TextureRect] = []
var equipment_panel = null
var event_log: Array[String] = []
var agent_tick: int = 0
var dynamic_count: int = 0
var hud_refresh_s: float = 0.0

func _ready() -> void:
    INPUT_DEFAULTS.ensure_actions()
    world_map = WORLD_SCENE.instantiate()
    add_child(world_map)
    _spawn_player()
    _spawn_mock_people()
    _setup_hud()
    var timer := Timer.new()
    timer.wait_time = 5.0
    timer.autostart = true
    timer.timeout.connect(_mock_agent_step)
    add_child(timer)
    _log("MOCK world: one shared map, no scene transitions.")
    _log("WASD / Shift sprint / Space dodge / LMB attack / 1 melee / 2 ranged")
    _log("Z / X cycle weapons, Tab inventory, F inspect NPC, N spawn NPC, E interact")

func _process(delta: float) -> void:
    hud_refresh_s -= delta
    if hud_refresh_s <= 0.0:
        hud_refresh_s = 0.25
        _update_hud()

func _spawn_player() -> void:
    player = PLAYER_SCENE.instantiate()
    player.region_id = "overworld"
    add_child(player)
    player.global_position = world_map.spawn_position("player")
    player.hit_detected.connect(_mock_hit)
    player.interaction_requested.connect(_mock_talk)
    player.pickup_requested.connect(_pickup_bag)
    player.weapon_changed.connect(_on_weapon_changed)
    player.actor_died.connect(_on_actor_died)
    entities[player.entity_id] = player
    player.coins = 30
    for base in WEAPONS.MELEE_TYPES + WEAPONS.RANGED_TYPES:
        var starter: Dictionary = WEAPONS.demo_item(base, player.entity_id)
        player.preview_add_item(starter)
    player.preview_equip_item(WEAPONS.demo_item("sword", player.entity_id))
    player.preview_equip_item(WEAPONS.demo_item("bow", player.entity_id))
    player.set_active_weapon_slot("melee")
    player.preview_add_item(_material_item("item_player_potion", "Healing Potion", "consumable", player.entity_id))
    var camera := player.get_node("Camera2D") as Camera2D
    var world_size: Vector2 = world_map.world_pixel_size()
    camera.limit_left = 0
    camera.limit_top = 0
    camera.limit_right = int(world_size.x)
    camera.limit_bottom = int(world_size.y)

func _mock_actor(id: String, name: String, spawn: String, skin: String, kind: String, hp: int, weapon: String, money: int, bag_item: String):
    var spawn_position: Vector2 = world_map.spawn_position(spawn)
    var state: Dictionary = {
        "id":id, "name":name, "appearance_key":skin,
        "region_id":"overworld", "max_hp":hp, "hp":hp, "alive":true,
        "kind":"monster" if kind in ["wolf", "wisp"] else "npc",
        "visual_role":kind, "coins":money,
        "tile":{"x":spawn_position.x / 32.0,"y":spawn_position.y / 32.0}
    }
    var items: Array[Dictionary] = []
    var equipment: Dictionary = {}
    if WEAPONS.is_weapon(weapon):
        var item: Dictionary = WEAPONS.demo_item(weapon, id)
        items.append(item)
        var slot: String = WEAPONS.group_for_type(weapon)
        equipment[slot] = str(item["id"])
    if not bag_item.is_empty():
        items.append(_material_item("%s_%s" % [id, bag_item], bag_item.capitalize(), bag_item, id))
    var npc = NPC_FACTORY.spawn(self, state, items, equipment, world_map)
    npc.player_ref = player
    if WEAPONS.group_for_type(weapon) == "ranged":
        npc.set_active_weapon_slot("ranged")
    npc.hit_detected.connect(_mock_hit)
    npc.task_reported.connect(_on_task_report)
    npc.actor_died.connect(_on_actor_died)
    entities[id] = npc
    return npc

func _spawn_mock_people() -> void:
    _mock_actor("npc_merchant", "Merchant", "merchant", "merchant", "civilian", 70, "crossbow", 48, "healing_potion")
    _mock_actor("npc_healer", "Healer", "healer", "healer", "civilian", 68, "staff", 29, "herb")
    _mock_actor("npc_guard", "Guard", "guard", "wanderer", "guard", 92, "hammer", 12, "ore")
    _mock_actor("npc_wanderer", "Wanderer", "wanderer", "wanderer", "civilian", 76, "sword", 21, "herb")
    _mock_actor("npc_scholar", "Scholar", "scholar", "healer", "civilian", 63, "staff", 26, "ancient_scroll")
    _mock_actor("mob_wolf_1", "Wolf", "forest_wolf", "wolf", "wolf", 44, "", 3, "pelt")
    _mock_actor("mob_wolf_2", "Wolf", "far_wolf", "wolf", "wolf", 44, "", 4, "pelt")
    _mock_actor("mob_wisp", "Wisp", "wisp", "wisp", "wisp", 33, "staff", 7, "crystal")

func _material_item(id: String, name: String, base_type: String, owner: String) -> Dictionary:
    return {"id":id, "name":name, "base_type":base_type,
        "quality":"common", "material_id":"none", "stats":{"damage":0,"cooldown_s":1.0,"armor":0},
        "owner_id":owner, "origin_event_ids":[]}

func _mock_agent_step() -> void:
    agent_tick += 1
    var merchant = entities.get("npc_merchant")
    if merchant != null and merchant.alive and merchant.current_task_id.is_empty():
        var goal: Vector2 = world_map.spawn_position("wanderer") if agent_tick % 2 else world_map.spawn_position("merchant")
        _issue_mock_move(merchant, goal)
    var healer = entities.get("npc_healer")
    if healer != null and healer.alive and healer.current_task_id.is_empty():
        var goal: Vector2 = world_map.spawn_position("guard") if agent_tick % 2 else world_map.spawn_position("healer")
        _issue_mock_move(healer, goal)
    var guard = entities.get("npc_guard")
    if guard != null and guard.alive and guard.current_task_id.is_empty() and merchant != null and merchant.alive:
        guard.execute_task({"id":"mock_escort_%d" % agent_tick,
            "actor_id":guard.entity_id,"kind":"ESCORT","target_id":merchant.entity_id,
            "target_region_id":"overworld","status":"running","source_event_ids":[]})
    _log("MOCK Agent tick %d: NPCs receive cross-map tasks (not LLM)." % agent_tick)

func _issue_mock_move(npc, position: Vector2) -> void:
    npc.execute_task({"id":"mock_move_%s_%d" % [npc.entity_id, agent_tick],
        "actor_id":npc.entity_id,"kind":"MOVE","target_region_id":"overworld",
        "target_tile":{"x":position.x / 32.0,"y":position.y / 32.0},
        "status":"running","source_event_ids":[]})

func _mock_hit(hit: Dictionary) -> void:
    var key: String = "%s:%s" % [hit.get("attack_id", ""), hit.get("target_id", "")]
    if processed_attacks.has(key):
        return
    processed_attacks[key] = true
    var attacker = entities.get(str(hit.get("attacker_id", "")))
    var victim = entities.get(str(hit.get("target_id", "")))
    if attacker == null or victim == null or not attacker.alive or not victim.alive:
        return
    if victim.has_method("is_dodging") and victim.is_dodging():
        _log("DODGE succeeded for %s" % str(victim.entity_id))
        return
    var equipped: Dictionary = attacker.active_weapon()
    var damage: int = int(equipped.get("stats", {}).get("damage", 7))
    if damage <= 0:
        damage = 7
    victim.apply_damage_mock(damage, attacker.entity_id, attacker.global_position)
    _log("MOCK HIT %s -> %s (%d damage; hp=%d)" % [attacker.entity_id, victim.entity_id, damage, victim.hp])
    _update_hud()

func _on_actor_died(actor_id: String) -> void:
    if processed_deaths.has(actor_id):
        return
    processed_deaths[actor_id] = true
    var actor = entities.get(actor_id)
    if actor == null:
        return
    var loot_data: Dictionary = actor.mock_drops()
    var items: Array[Dictionary] = []
    for entry in loot_data.get("items", []):
        items.append(entry)
    var money: int = int(loot_data.get("coins", 0))
    if not items.is_empty() or money > 0:
        var bag = Node2D.new()
        bag.set_script(LOOT_SCRIPT)
        bag.setup("loot_%s" % actor_id, items, money)
        add_child(bag)
        bag.global_position = actor.global_position + Vector2(13, 0)
        ground_loot[bag.loot_id] = bag
    _log("MOCK death: %s, dropped %d items + %d coins" % [actor_id, items.size(), money])
    _update_hud()

func _pickup_bag(loot_id: String) -> void:
    var bag = ground_loot.get(loot_id)
    if bag == null or not is_instance_valid(bag):
        return
    player.receive_mock_loot(bag.contents, bag.coins)
    _log("MOCK pickup: %d items, %d coins" % [bag.contents.size(), bag.coins])
    ground_loot.erase(loot_id)
    bag.queue_free()
    _refresh_inventory()

func _mock_talk(npc_id: String) -> void:
    var npc = entities.get(npc_id)
    if npc != null:
        _log("MOCK talk to %s (backend B/C dialogue not connected)." % str(npc.display_name))

func _on_task_report(payload: Dictionary) -> void:
    _log("MOCK task %s: %s" % [payload.get("task_id", ""), payload.get("status", "")])

func _on_weapon_changed(name: String) -> void:
    _log("Equipped: %s" % name)
    _update_hud()
    _refresh_inventory()

func _setup_hud() -> void:
    var ui := CanvasLayer.new()
    ui.name = "DemoHUD"
    add_child(ui)
    var background := ColorRect.new()
    background.position = Vector2(4, 3)
    background.size = Vector2(398, 53)
    background.color = Color(0.03, 0.08, 0.08, 0.72)
    ui.add_child(background)
    info_label = Label.new()
    info_label.position = Vector2(10, 6)
    info_label.add_theme_font_size_override("font_size", 11)
    info_label.add_theme_color_override("font_color", Color("#f8e8bd"))
    ui.add_child(info_label)
    for i in range(2):
        var icon := TextureRect.new()
        icon.position = Vector2(551 + 39 * i, 5)
        icon.size = Vector2(34, 34)
        icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
        icon.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
        ui.add_child(icon)
        weapon_icons.append(icon)
    logs_label = Label.new()
    logs_label.position = Vector2(9, 293)
    logs_label.add_theme_font_size_override("font_size", 9)
    logs_label.add_theme_color_override("font_color", Color("#fff6d2"))
    ui.add_child(logs_label)
    equipment_panel = PanelContainer.new()
    equipment_panel.set_script(INVENTORY_PANEL)
    ui.add_child(equipment_panel)
    _update_hud()

func _update_hud() -> void:
    if info_label == null or player == null:
        return
    var biome: String = world_map.biome_name(player.global_position)
    var slot: String = "1 MELEE" if player.active_weapon_slot == "melee" else "2 RANGED"
    info_label.text = "%s | HP %d/%d | %d gold\n%s : %s (DMG %d) | WASD/Shift/Space/LMB/E | Tab bag | F inspect" % [
        biome, player.hp, player.max_hp, player.coins, slot,
        player.get_weapon_name_mock(), player.get_weapon_damage_mock()]
    for i in range(2):
        var group: String = "melee" if i == 0 else "ranged"
        var item: Dictionary = player.equipment_item(group)
        var path: String = WEAPONS.icon_path(str(item.get("base_type", "")))
        if path.is_empty():
            weapon_icons[i].texture = null
        else:
            weapon_icons[i].texture = load(path) as Texture2D
        weapon_icons[i].modulate = Color.WHITE if group == player.active_weapon_slot else Color(0.6,0.65,0.65,0.75)

func _log(message: String) -> void:
    print(message)
    event_log.append(message)
    if event_log.size() > 4:
        event_log.pop_front()
    if logs_label != null:
        logs_label.text = "\n".join(PackedStringArray(event_log))

func _refresh_inventory() -> void:
    if equipment_panel != null:
        equipment_panel.refresh()

func _spawn_new_mock_npc() -> void:
    dynamic_count += 1
    var id: String = "npc_generated_%02d" % dynamic_count
    var appearances: Array[String] = ["merchant", "healer", "wanderer"]
    var roles: Array[String] = ["sword", "bow", "staff", "axe", "crossbow", "hammer"]
    var npc = _mock_actor(id, "Visitor-%02d" % dynamic_count, "wanderer",
        appearances[dynamic_count % appearances.size()], "civilian", 55,
        roles[dynamic_count % roles.size()], 5 + dynamic_count, "herb")
    npc.global_position = world_map.spawn_position("wanderer") + Vector2(25.0 * dynamic_count, 0)
    _log("MOCK spawned a generic NPC: %s" % id)

func _unhandled_input(event: InputEvent) -> void:
    if not (event is InputEventKey) or not event.pressed or event.echo:
        return
    match event.physical_keycode:
        KEY_Z:
            player.cycle_mock_weapon("melee")
        KEY_X:
            player.cycle_mock_weapon("ranged")
        KEY_TAB, KEY_I:
            equipment_panel.toggle_for(player)
            player.set_controls_locked(equipment_panel.visible)
        KEY_F:
            var nearest = null
            var min_distance: float = 100.0
            for actor in entities.values():
                if actor == player or not actor.alive or actor.actor_kind == "monster":
                    continue
                var dist: float = player.global_position.distance_to(actor.global_position)
                if dist < min_distance:
                    nearest = actor
                    min_distance = dist
            if nearest != null:
                equipment_panel.toggle_for(nearest)
                player.set_controls_locked(equipment_panel.visible)
            else:
                _log("No NPC nearby to inspect.")
        KEY_N:
            _spawn_new_mock_npc()
        KEY_R:
            get_tree().reload_current_scene()
    _update_hud()
