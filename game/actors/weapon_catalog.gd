extends RefCounted
## Game-side display/animation defaults. Server ItemState.stats override mock defaults.
## Weapon type is NOT the equipment slot: sword/axe/hammer -> melee;
## bow/crossbow/staff -> ranged.

const MELEE_TYPES: Array[String] = ["sword", "axe", "hammer"]
const RANGED_TYPES: Array[String] = ["bow", "crossbow", "staff"]
const EQUIPMENT_SLOTS: Array[String] = [
    "melee", "ranged", "offhand", "head", "chest", "hands", "legs", "boots",
    "accessory", "ring_1", "ring_2"
]
const WEAPONS: Dictionary = {
    "sword": {"name": "Iron Sword", "damage": 11, "cooldown_s": 0.38, "range_px": 51.0, "swing_ms": 250},
    "axe": {"name": "Broad Axe", "damage": 17, "cooldown_s": 0.65, "range_px": 56.0, "swing_ms": 410},
    "hammer": {"name": "War Hammer", "damage": 21, "cooldown_s": 0.82, "range_px": 49.0, "swing_ms": 490},
    "bow": {"name": "Longbow", "damage": 9, "cooldown_s": 0.56, "range_px": 310.0, "swing_ms": 280, "projectile_speed": 460.0},
    "crossbow": {"name": "Crossbow", "damage": 16, "cooldown_s": 1.12, "range_px": 350.0, "swing_ms": 420, "projectile_speed": 590.0},
    "staff": {"name": "Arcane Staff", "damage": 13, "cooldown_s": 0.72, "range_px": 300.0, "swing_ms": 330, "projectile_speed": 350.0}
}

static func is_weapon(base_type: String) -> bool:
    return WEAPONS.has(base_type)

static func group_for_type(base_type: String) -> String:
    if base_type in MELEE_TYPES:
        return "melee"
    if base_type in RANGED_TYPES:
        return "ranged"
    return ""

static func equipment_slot(item: Dictionary) -> String:
    var explicit_slot: String = str(item.get("equipment_slot", item.get("slot", "")))
    if explicit_slot in EQUIPMENT_SLOTS:
        return explicit_slot
    return group_for_type(str(item.get("base_type", "")))

static func icon_path(base_type: String) -> String:
    if is_weapon(base_type):
        return "res://actors/assets/weapons/%s.png" % base_type
    return ""

static func demo_item(base_type: String, owner_id: String = "") -> Dictionary:
    var entry: Dictionary = WEAPONS.get(base_type, {})
    if entry.is_empty():
        return {}
    return {
        "id": "item_demo_%s_%s" % [owner_id, base_type],
        "name": str(entry["name"]),
        "base_type": base_type,
        "quality": "common",
        "material_id": "iron" if base_type != "staff" else "ashwood",
        "stats": {
            "damage": int(entry["damage"]),
            "cooldown_s": float(entry["cooldown_s"]),
            "armor": 0
        },
        "range_px": float(entry["range_px"]),
        "swing_ms": int(entry["swing_ms"]),
        "projectile_speed": float(entry.get("projectile_speed", 0.0)),
        "owner_id": owner_id
    }

static func attack_range(item: Dictionary) -> float:
    var base_type: String = str(item.get("base_type", ""))
    var default_range: float = float(WEAPONS.get(base_type, {}).get("range_px", 50.0))
    return float(item.get("range_px", default_range))

static func swing_duration(item: Dictionary) -> int:
    var base_type: String = str(item.get("base_type", ""))
    return int(item.get("swing_ms", WEAPONS.get(base_type, {}).get("swing_ms", 300)))

static func projectile_speed(item: Dictionary) -> float:
    var base_type: String = str(item.get("base_type", ""))
    return float(item.get("projectile_speed", WEAPONS.get(base_type, {}).get("projectile_speed", 400.0)))
