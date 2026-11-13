"""First authoritative command: a trusted client's position checkpoint."""
import math

from shared.protocol import CheckpointPayload, StateView


class WorldError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def apply_checkpoint(state: StateView, payload: dict, region: dict) -> list[str]:
    checkpoint = CheckpointPayload.model_validate(payload)
    if checkpoint.region_id != state.current_region_id:
        raise WorldError("OUT_OF_RANGE", "位置报告必须属于当前地图。")
    actors = {actor.id: actor for actor in state.actors}
    identifiers = [position.actor_id for position in checkpoint.positions]
    if len(identifiers) != len(set(identifiers)):
        raise WorldError("PRECONDITION_FAILED", "同一位置报告包含重复角色。")
    blocked = {tuple(cell) for cell in region["blocked_tiles"]}
    for position in checkpoint.positions:
        actor = actors.get(position.actor_id)
        if actor is None:
            raise WorldError("ACTOR_NOT_FOUND", "角色不存在。", 404)
        if not actor.alive:
            raise WorldError("NPC_DEAD", "死亡角色不能移动。")
        if actor.region_id != checkpoint.region_id:
            raise WorldError("OUT_OF_RANGE", "角色不属于报告地图。")
        tile = position.tile
        if not (math.isfinite(tile.x) and math.isfinite(tile.y)
                and 0 <= tile.x < region["width_tiles"]
                and 0 <= tile.y < region["height_tiles"]):
            raise WorldError("OUT_OF_RANGE", "坐标超出地图范围。")
        if (int(tile.x), int(tile.y)) in blocked:
            raise WorldError("OUT_OF_RANGE", "目标格不可通行。")
    # Apply only after every position has passed validation.
    for position in checkpoint.positions:
        actors[position.actor_id].tile = position.tile
    return identifiers
