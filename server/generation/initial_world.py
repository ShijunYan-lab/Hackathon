"""Seeded initialization on a configured, continuous map."""
from __future__ import annotations

import random
from uuid import NAMESPACE_URL, uuid5

from shared.protocol import ActorState, Event, ItemState, ItemStats, OrganizationView, SiteView, StateView, Tile
from server.generation.equipment import generate_weapon


def initial_world(world_id: str, seed: int, player_name: str, region: dict):
    rng = random.Random(seed)

    def identifier(kind: str, index: int) -> str:
        return kind + "_" + uuid5(NAMESPACE_URL, f"unwritten:{seed}:{kind}:{index}").hex[:16]

    blocked = {tuple(cell) for cell in region["blocked_tiles"]}
    spawn = Tile.model_validate(region["spawn_tile"])
    tiles = [Tile(x=x + .5, y=y + .5)
             for y in range(region["height_tiles"])
             for x in range(region["width_tiles"])
             if (x, y) not in blocked and (x, y) != (int(spawn.x), int(spawn.y))]
    npc_count = rng.randint(5, 7)
    if len(tiles) < npc_count:
        raise ValueError("Map has insufficient walkable tiles")
    npc_tiles = rng.sample(tiles, npc_count)
    player_id = identifier("player", 0)
    item_id = identifier("item", 0)
    event_id = identifier("evt", 0)
    org_ids = [identifier("org", index) for index in range(2)]
    actors = [ActorState(id=player_id, kind="player", name=player_name, alive=True,
                        hp=80, max_hp=80, armor=0, region_id=region["id"], tile=spawn,
                        appearance_key="traveler", equipped_item_id=item_id)]
    for index, tile in enumerate(npc_tiles):
        actors.append(ActorState(
            id=identifier("npc", index), kind="npc",
            name=rng.choice(["林", "岚", "石", "星", "溪"]) + rng.choice(["舟", "叶", "歌", "羽"]) + str(index + 1),
            alive=True, hp=45, max_hp=45, armor=0, region_id=region["id"], tile=tile,
            appearance_key="traveler", org_ids=[org_ids[index % len(org_ids)]],
        ))
    organizations = []
    for index, org_id in enumerate(org_ids):
        members = [actor.id for actor in actors if org_id in actor.org_ids]
        organizations.append(OrganizationView(
            id=org_id, name=rng.choice(["青叶", "晨光", "银溪"]) + ["商会", "工坊"][index],
            function_tags=[["trade"], ["craft"]][index], member_ids=members,
            representative_id=members[0], resources={"coin": rng.randint(10, 30)},
        ))
    weapon = ItemState(id=item_id, name="铁剑", base_type="sword", quality="common",
                       material_id="iron", owner_id=player_id, origin_event_ids=[event_id],
                       stats=ItemStats(damage=rng.randint(4, 8), cooldown_s=.5, armor=0))
    weapons = [weapon]
    for index, actor in enumerate(actors[1:], start=1):
        npc_weapon = generate_weapon(rng, identifier("item", index), actor.id, event_id)
        actor.equipped_item_id = npc_weapon.id
        actor.armor = npc_weapon.stats.armor
        weapons.append(npc_weapon)
    sites = [SiteView.model_validate(site) for site in region.get("sites", [])]
    if not sites:
        herb_tile = min(tiles, key=lambda tile: abs(tile.x - spawn.x - 3) + abs(tile.y - spawn.y))
        sites = [SiteView(id=identifier("site", 0), kind="herb", region_id=region["id"],
                          tile=herb_tile, remaining=5)]
    state = StateView(world_id=world_id, seed=seed, tick=0, world_version=0,
                      player_id=player_id, current_region_id=region["id"], actors=actors,
                      items=weapons, organizations=organizations, relations=[], tasks=[], sites=sites)
    event = Event(id=event_id, event_seq=1, tick=0, type="world_created",
                  actor_id=player_id, facts={"seed": seed}, caused_by=[], witness_ids=[player_id])
    return state, event, rng.getstate()
