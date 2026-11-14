extends RefCounted
## One authoritative visual lookup for inventory, trade, ground loot and props.
## The world still owns item IDs, quantities, owners and all combat values.
const ROOT := "res://assets/r7/"
const PLACEHOLDER := preload("res://assets/r7/unknown_item.png")
static var texture_cache: Dictionary = {}

static func _get_texture(key: String) -> Texture2D:
	if texture_cache.has(key):
		return texture_cache[key]
	var path: String = ROOT + key + ".png"
	var texture: Texture2D = load(path) if ResourceLoader.exists(path) else PLACEHOLDER
	texture_cache[key] = texture
	return texture

static func quality_index(quality: String) -> int:
	match quality.to_lower():
		"uncommon", "improved": return 1
		"rare", "fine": return 2
		"epic", "elite", "excellent": return 3
		"legendary", "masterwork": return 4
	return 0

static func item_key(item: Dictionary) -> String:
	var base: String = str(item.get("base_type", ""))
	var material: String = str(item.get("material_id", ""))
	var title: String = str(item.get("name", ""))
	var tier: int = quality_index(str(item.get("quality", "common")))
	# Armor materials such as cloth/leather must not hide their equipment icon.
	if base in ["sword", "bow", "crossbow", "axe", "hammer", "staff"]:
		return "%s_%d" % [base, tier]
	if base in ["armor", "chest", "head", "helmet", "boots", "feet", "legs", "offhand", "shield", "hands"]:
		if base in ["head", "helmet"] or title.contains("盔") or title.contains("帽"):
			return "helmet_%d" % tier
		if base in ["boots", "feet", "legs"] or title.contains("靴") or title.contains("鞋"):
			return "boots_%d" % tier
		return "armor_%d" % tier
	match material:
		"currency", "coins", "gold": return "coin"
		"healing", "potion", "medicine": return "potion" if tier <= 1 else "potion_large"
		"herb", "herbs": return "herb"
		"wood", "log", "lumber": return "wood"
		"stone", "rock": return "stone"
		"iron", "ore", "iron_ore": return "iron"
		"mushroom": return "mushroom"
		"food", "grain": return "food"
		"bandage": return "bandage"
		"cloth": return "cloth"
	if base == "consumable": return "potion" if title.contains("药") else "food"
	if base == "material": return "stone" if title.contains("石") else "wood" if title.contains("木") else "herb"
	return "unknown_item"

static func item_texture(item: Dictionary) -> Texture2D:
	return _get_texture(item_key(item))

static func object_texture(kind: String) -> Texture2D:
	var key: String = {
		"board": "sign", "stone": "stone", "merchant": "crate", "cache": "chest",
		"looted": "crate", "loot_bag": "sack", "gold": "coin"
	}.get(kind, kind)
	return _get_texture(key)
