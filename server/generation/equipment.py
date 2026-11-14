"""Small seeded equipment vocabulary with already-calculated executable stats."""
from shared.protocol import ItemState, ItemStats


def generate_weapon(rng, item_id, owner_id, origin_event_id):
    base_type = rng.choice(["sword", "axe"])
    material = rng.choice(["iron", "steel", "bronze"])
    quality = rng.choice(["common", "uncommon", "rare"])
    affixes = rng.sample(["sharp", "swift", "warding"], rng.randint(0, 2))
    damage = {"sword": 5, "axe": 7}[base_type] + {"iron": 0, "steel": 1, "bronze": 0}[material]
    damage += {"common": 0, "uncommon": 1, "rare": 2}[quality] + (2 if "sharp" in affixes else 0)
    cooldown = {"sword": .5, "axe": .7}[base_type] - (.1 if "swift" in affixes else 0)
    return ItemState(id=item_id, name=f"{material} {base_type}", base_type=base_type,
                     quality=quality, material_id=material, affixes=affixes, owner_id=owner_id,
                     origin_event_ids=[origin_event_id],
                     stats=ItemStats(damage=damage, cooldown_s=round(cooldown, 2),
                                     armor=1 if "warding" in affixes else 0))
