"""Authoritative combat rules for a trusted local collision reporter."""
from __future__ import annotations

import math
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from shared.protocol import DTO, Event, HitPayload, StateView, Tile
from server.world.commands import WorldError, apply_checkpoint


class CombatRules(DTO):
    melee_range_tiles: float = Field(default=2, gt=0, le=5, allow_inf_nan=False)
    witness_range_tiles: float = Field(default=6, gt=0, le=50, allow_inf_nan=False)
    player_material_loss_fraction: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)

    @classmethod
    def from_file(cls, path: str | Path) -> CombatRules:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def validate_hit(state: StateView, hit: HitPayload, region: dict, rules: CombatRules):
    actors = {actor.id: actor for actor in state.actors}
    attacker, target = actors.get(hit.attacker_id), actors.get(hit.target_id)
    if attacker is None or target is None:
        raise WorldError("ACTOR_NOT_FOUND", "攻击者或目标不存在。", 404)
    if not hit.attack_id.strip():
        raise WorldError("PRECONDITION_FAILED", "攻击 ID 不能为空。")
    if attacker.id == target.id:
        raise WorldError("PRECONDITION_FAILED", "攻击者与目标不能相同。")
    if not attacker.alive or not target.alive:
        raise WorldError("NPC_DEAD", "死亡角色不能攻击或再次受击。")
    weapon = next((item for item in state.items if item.id == hit.weapon_id), None)
    if weapon is None or weapon.owner_id != attacker.id:
        raise WorldError("ITEM_NOT_OWNED", "攻击者不持有这件武器。")
    if attacker.equipped_item_id != weapon.id or weapon.base_type not in ("sword", "axe"):
        raise WorldError("PRECONDITION_FAILED", "攻击必须使用当前装备的近战武器。")
    if math.hypot(hit.attacker_tile.x - hit.target_tile.x,
                  hit.attacker_tile.y - hit.target_tile.y) > rules.melee_range_tiles:
        raise WorldError("OUT_OF_RANGE", "目标超出近战距离。")
    # Godot reports current hit positions, which may be newer than the last checkpoint.
    apply_checkpoint(state, {
        "region_id": hit.region_id,
        "positions": [{"actor_id": attacker.id, "tile": hit.attacker_tile.model_dump()},
                      {"actor_id": target.id, "tile": hit.target_tile.model_dump()}],
    }, region)
    return attacker, target, weapon


def settle_hit(state: StateView, hit: HitPayload, region: dict, rules: CombatRules,
               weapon_damage: int, first_event_seq: int) -> tuple[list[Event], bool]:
    """Apply a validated hit. Return events and whether the target was downed."""
    actors = {actor.id: actor for actor in state.actors}
    target = actors[hit.target_id]
    damage = max(1, weapon_damage - target.armor)
    hp_after = max(0, target.hp - damage)
    witnesses = sorted({hit.attacker_id, hit.target_id} | {
        actor.id for actor in state.actors
        if actor.alive and actor.region_id == hit.region_id
        and math.hypot(actor.tile.x - hit.target_tile.x,
                       actor.tile.y - hit.target_tile.y) <= rules.witness_range_tiles
    })
    events = []

    def emit(kind, facts, caused_by=(), actor_id=hit.attacker_id, target_id=hit.target_id):
        event = Event(id="evt_" + uuid4().hex, event_seq=first_event_seq + len(events),
                      tick=state.tick, type=kind, actor_id=actor_id, target_id=target_id,
                      facts=facts, caused_by=list(caused_by), witness_ids=witnesses)
        events.append(event)
        return event.id

    hit_id = emit("hit_applied", {
        "attack_id": hit.attack_id, "weapon_id": hit.weapon_id,
        "weapon_damage": weapon_damage, "armor": target.armor,
        "damage": damage, "hp_lost": target.hp - hp_after,
        "hp_before": target.hp, "hp_after": hp_after,
        "region_id": hit.region_id, "attacker_tile": hit.attacker_tile.model_dump(),
        "target_tile": hit.target_tile.model_dump(),
    })
    updates = {"hp": hp_after, "alive": hp_after > 0}
    if hp_after > 0:
        state.actors = [actor.model_copy(update=updates) if actor.id == target.id else actor
                        for actor in state.actors]
        return events, False

    player_down = target.kind == "player"
    death_id = emit("player_downed" if player_down else "actor_died",
                    {"region_id": target.region_id, "tile": target.tile.model_dump()}, [hit_id])
    cancelled_ids = set()
    for task in state.tasks:
        if task.status in ("pending", "running") and (task.actor_id == target.id or task.target_id == target.id):
            task.status = "cancelled"
            cancelled_ids.add(task.id)
            emit("task_cancelled", {"task_id": task.id, "reason": "ACTOR_DOWNED"},
                 [death_id], actor_id=task.actor_id)
    for actor in state.actors:
        if actor.task_id in cancelled_ids or actor.id == target.id:
            actor.task_id = None
            actor.behavior = "idle" if actor.alive else "dead"

    owned = sorted((item for item in state.items if item.owner_id == target.id), key=lambda item: item.id)
    if player_down:
        materials = [item for item in owned if item.base_type == "material"]
        owned = materials[:math.ceil(len(materials) * rules.player_material_loss_fraction)]
    dropped_ids = {item.id for item in owned}
    state.items = [item.model_copy(update={"owner_id": None, "region_id": target.region_id,
                                          "tile": target.tile.model_copy()})
                   if item.id in dropped_ids else item for item in state.items]
    for item in owned:
        emit("item_dropped", {"item_id": item.id, "previous_owner_id": target.id,
                              "region_id": target.region_id, "tile": target.tile.model_dump()}, [death_id])

    if player_down:
        updates.update(hp=target.max_hp, alive=True, behavior="idle", task_id=None,
                       region_id=region["id"], tile=Tile.model_validate(region["spawn_tile"]))
        state.current_region_id = region["id"]
        emit("player_recovered", {"region_id": region["id"], "tile": region["spawn_tile"],
                                  "hp": target.max_hp, "lost_item_ids": sorted(dropped_ids)}, [death_id])
    else:
        updates.update(behavior="dead", task_id=None, equipped_item_id=None, armor=0, org_ids=[])
        for organization in state.organizations:
            if target.id not in organization.member_ids and organization.representative_id != target.id:
                continue
            previous_representative = organization.representative_id
            organization.member_ids = [member_id for member_id in organization.member_ids
                                       if member_id != target.id and member_id in actors and actors[member_id].alive]
            if organization.representative_id not in organization.member_ids:
                organization.representative_id = next(iter(sorted(organization.member_ids)), None)
            if not organization.member_ids:
                organization.status = "inactive"
            emit("organization_membership_changed", {
                "org_id": organization.id, "removed_actor_id": target.id,
                "previous_representative_id": previous_representative,
                "representative_id": organization.representative_id,
                "status": organization.status,
            }, [death_id])
    state.actors = [actor.model_copy(update=updates) if actor.id == target.id else actor
                    for actor in state.actors]
    return events, True
