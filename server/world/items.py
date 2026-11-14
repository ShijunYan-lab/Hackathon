"""Item ownership and equipment operations used by commands and agent intents."""
import math
from uuid import uuid4

from shared.protocol import Event, StateView
from server.world.commands import WorldError


def living_actor(state, actor_id):
    actor = next((actor for actor in state.actors if actor.id == actor_id), None)
    if actor is None:
        raise WorldError("ACTOR_NOT_FOUND", "角色不存在。", 404)
    if not actor.alive:
        raise WorldError("NPC_DEAD", "死亡角色不能操作。")
    return actor


def require_near(actor, region_id, tile, distance=2):
    if actor.region_id != region_id or tile is None or math.hypot(
            actor.tile.x - tile.x, actor.tile.y - tile.y) > distance:
        raise WorldError("OUT_OF_RANGE", "需要靠近同地图中的目标。")


def remove_equipment(actor, item):
    for slot, identifier in list(actor.equipped_slots.items()):
        if identifier == item.id:
            actor.equipped_slots.pop(slot)
            actor.armor = max(0, actor.armor - item.stats.armor)
    if actor.equipped_item_id == item.id:
        actor.equipped_item_id = None
        actor.armor = max(0, actor.armor - item.stats.armor)


def apply_item_command(state: StateView, kind: str, payload: dict, seq: int) -> list[Event]:
    actor = living_actor(state, payload["actor_id"])
    item = next((item for item in state.items if item.id == payload["item_id"]), None)
    if item is None:
        raise WorldError("ITEM_NOT_FOUND", "物品不存在。", 404)
    previous_owner = item.owner_id
    target = actor
    if kind == "PICKUP":
        if item.owner_id is not None:
            raise WorldError("ITEM_NOT_ON_GROUND", "物品已被持有。")
        require_near(actor, item.region_id, item.tile)
        updated = item.model_copy(update={"owner_id": actor.id, "region_id": None, "tile": None})
    else:
        if item.owner_id != actor.id:
            raise WorldError("ITEM_NOT_OWNED", "角色不持有这件物品。")
        updated = item
        if kind == "EQUIP":
            if item.base_type == "armor":
                slot = item.equipment_slot or "chest"
                old = next((value for value in state.items if value.id == actor.equipped_slots.get(slot)), None)
                if old is not None:
                    remove_equipment(actor, old)
                actor.equipped_slots[slot] = item.id
                actor.armor += item.stats.armor
            else:
                if item.base_type not in ("sword", "axe", "hammer", "bow", "crossbow", "staff"):
                    raise WorldError("PRECONDITION_FAILED", "This item is not equipment.")
                old = next((value for value in state.items if value.id == actor.equipped_item_id), None)
                if old is not None:
                    remove_equipment(actor, old)
                actor.equipped_item_id = item.id
                actor.armor += item.stats.armor
        elif kind == "GIVE":
            target = living_actor(state, payload["target_id"])
            if target.id == actor.id:
                raise WorldError("PRECONDITION_FAILED", "赠送需要其他角色。")
            require_near(actor, target.region_id, target.tile)
            remove_equipment(actor, item)
            updated = item.model_copy(update={"owner_id": target.id})
        else:
            raise WorldError("ACTION_NOT_SUPPORTED", "物品操作尚未实现。")
    state.items = [updated if value.id == item.id else value for value in state.items]
    witnesses = sorted({actor.id, target.id} | {
        value.id for value in state.actors if value.alive and value.region_id == actor.region_id
        and math.hypot(value.tile.x - actor.tile.x, value.tile.y - actor.tile.y) <= 6
    })
    return [Event(id="evt_" + uuid4().hex, event_seq=seq, tick=state.tick,
                  type={"PICKUP": "item_picked_up", "EQUIP": "item_equipped", "GIVE": "item_given"}[kind],
                  actor_id=actor.id, target_id=target.id,
                  facts={"item_id": item.id, "previous_owner_id": previous_owner,
                         "owner_id": updated.owner_id, "equipped_item_id": actor.equipped_item_id,
                         "armor": actor.armor}, caused_by=[], witness_ids=witnesses)]
