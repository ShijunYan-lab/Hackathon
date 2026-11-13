"""Version-1 DTO contract. Format validation is NOT game-rule validation."""
from __future__ import annotations
from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, model_validator

class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

class Tile(DTO):
    x: float = Field(ge=0)
    y: float = Field(ge=0)

class RequestBase(DTO):
    api_version: Literal["v1"] = "v1"
    request_id: str = Field(min_length=1, max_length=128)

class VersionedRequest(RequestBase):
    expected_world_version: int = Field(ge=0)

class NewWorldRequest(RequestBase):
    seed: int = Field(ge=0, le=2147483647)
    player_name: str = Field(min_length=1, max_length=30)

class DialogueRequest(VersionedRequest):
    npc_id: str
    text: str = Field(min_length=1, max_length=500)

class AdvanceRequest(VersionedRequest):
    reason: Literal["idle_timer", "major_event", "rest", "debug_step"]
    trigger_event_ids: list[str] = Field(default_factory=list)

class SaveRequest(VersionedRequest):
    label: str = Field(min_length=1, max_length=80)

class LoadRequest(RequestBase):
    pass

class PositionEntry(DTO):
    actor_id: str
    tile: Tile

class CheckpointPayload(DTO):
    region_id: str
    positions: list[PositionEntry]

class HitPayload(DTO):
    attack_id: str
    attacker_id: str
    target_id: str
    weapon_id: str
    region_id: str
    attacker_tile: Tile
    target_tile: Tile

class OwnedItemPayload(DTO):
    actor_id: str
    item_id: str

class GivePayload(OwnedItemPayload):
    target_id: str

class AcceptOfferPayload(DTO):
    actor_id: str
    offer_id: str

class ChangeRegionPayload(DTO):
    actor_id: str
    exit_id: str

class TaskReportPayload(DTO):
    task_id: str
    status: Literal["succeeded", "failed"]
    actor_id: str
    region_id: str
    tile: Tile
    failure_code: str | None = None

class JoinOrgPayload(DTO):
    actor_id: str
    org_id: str
    offer_id: str

class LeaveOrgPayload(DTO):
    actor_id: str
    org_id: str

PAYLOAD_MODELS = {
    "CHECKPOINT": CheckpointPayload, "HIT": HitPayload,
    "PICKUP": OwnedItemPayload, "EQUIP": OwnedItemPayload,
    "GIVE": GivePayload, "ACCEPT_OFFER": AcceptOfferPayload,
    "CHANGE_REGION": ChangeRegionPayload, "TASK_REPORT": TaskReportPayload,
    "JOIN_ORG": JoinOrgPayload, "LEAVE_ORG": LeaveOrgPayload,
}
CommandKind = Literal["CHECKPOINT", "HIT", "PICKUP", "EQUIP", "GIVE",
                      "ACCEPT_OFFER", "CHANGE_REGION", "TASK_REPORT",
                      "JOIN_ORG", "LEAVE_ORG"]
class CommandRequest(VersionedRequest):
    kind: CommandKind
    payload: dict[str, Any]

    @model_validator(mode="after")
    def check_payload(self):
        PAYLOAD_MODELS[self.kind].model_validate(self.payload)
        return self

class ItemStats(DTO):
    damage: int = Field(ge=0, le=100)
    cooldown_s: float = Field(gt=0, le=10)
    armor: int = Field(ge=0, le=100)

class ItemState(DTO):
    id: str
    name: str
    base_type: Literal["sword", "axe", "material", "consumable"]
    quality: Literal["common", "uncommon", "rare"]
    material_id: str
    affixes: list[str] = Field(default_factory=list, max_length=2)
    stats: ItemStats
    owner_id: str | None = None
    region_id: str | None = None
    tile: Tile | None = None
    origin_event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_location(self):
        if self.owner_id is None and (self.region_id is None or self.tile is None):
            raise ValueError("Ground item needs region_id and tile")
        if self.owner_id is not None and (self.region_id is not None or self.tile is not None):
            raise ValueError("Owned item must not also be on the ground")
        return self

class ActorState(DTO):
    id: str
    kind: Literal["player", "npc", "monster"]
    name: str
    alive: bool
    hp: int = Field(ge=0)
    max_hp: int = Field(gt=0)
    armor: int = Field(ge=0)
    region_id: str
    tile: Tile
    appearance_key: str
    org_ids: list[str] = Field(default_factory=list)
    equipped_item_id: str | None = None
    behavior: Literal["idle", "moving", "attacking", "fleeing", "dead"] = "idle"
    task_id: str | None = None

    @model_validator(mode="after")
    def check_health(self):
        if self.hp > self.max_hp:
            raise ValueError("hp exceeds max_hp")
        if self.alive != (self.hp > 0):
            raise ValueError("alive must agree with hp")
        return self

class OrganizationView(DTO):
    id: str
    name: str
    function_tags: list[str]
    member_ids: list[str]
    representative_id: str | None
    resources: dict[str, int]
    status: Literal["active", "inactive"] = "active"

class RelationView(DTO):
    from_org_id: str
    to_org_id: str
    stance: Literal["neutral", "trade", "allied", "hostile"]
    trust: int = Field(ge=-100, le=100)
    source_event_ids: list[str]

class Task(DTO):
    id: str
    actor_id: str
    kind: str
    target_id: str | None = None
    target_region_id: str | None = None
    target_tile: Tile | None = None
    status: Literal["pending", "running", "succeeded", "failed", "cancelled"]
    started_tick: int = Field(ge=0)
    source_event_ids: list[str]

class SiteView(DTO):
    id: str
    kind: str
    region_id: str
    tile: Tile
    remaining: int = Field(ge=0)

class StateView(DTO):
    world_id: str
    seed: int
    tick: int = Field(ge=0)
    world_version: int = Field(ge=0)
    player_id: str
    current_region_id: str
    actors: list[ActorState]
    items: list[ItemState]
    organizations: list[OrganizationView]
    relations: list[RelationView]
    tasks: list[Task]
    sites: list[SiteView]

class Event(DTO):
    id: str
    event_seq: int = Field(ge=0)
    tick: int = Field(ge=0)
    type: str
    actor_id: str | None = None
    target_id: str | None = None
    facts: dict[str, Any]
    caused_by: list[str]
    witness_ids: list[str]

Action = Literal["WAIT", "MOVE", "GATHER", "TRANSFER", "SHARE_INFO",
                 "PROPOSE_RELATION", "RESPOND_PROPOSAL", "ATTACK", "FLEE",
                 "CRAFT", "JOIN_ORG", "LEAVE_ORG"]
class Intent(DTO):
    action: Action
    target_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)

class MemoryProposal(DTO):
    statement: str = Field(min_length=1, max_length=300)
    source_type: Literal["observation", "report", "inference"]
    source_event_ids: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    status: Literal["unverified", "supported", "contradicted"]

class AgentDecision(DTO):
    reply: str = Field(default="", max_length=500)
    memory_proposals: list[MemoryProposal] = Field(default_factory=list)
    intent: Intent | None = None
    policy_patch: dict[str, float] = Field(default_factory=dict)
    evidence_memory_ids: list[str] = Field(default_factory=list)
    reason_summary: str = Field(default="", max_length=160)

class AgentContext(DTO):
    npc_id: str
    world_version: int
    identity: dict[str, Any]
    goals: list[str]
    own_inventory: list[ItemState]
    known_entities: list[dict[str, Any]]
    known_events: list[Event]
    memories: list[dict[str, Any]]
    allowed_actions: list[Action]
    policy: dict[str, float]
    policy_version: int

class APIError(DTO):
    code: str
    message: str
    retryable: bool

T = TypeVar("T")
class Envelope(DTO, Generic[T]):
    api_version: Literal["v1"] = "v1"
    request_id: str
    ok: bool
    world_id: str | None = None
    world_version: int | None = None
    data: T | None = None
    error: APIError | None = None

    @model_validator(mode="after")
    def check_result(self):
        if self.ok and self.error is not None:
            raise ValueError("Success must not contain an error")
        if not self.ok and (self.error is None or self.data is not None):
            raise ValueError("Failure must contain error and null data")
        return self
