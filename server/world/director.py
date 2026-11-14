"""World-director boundary. Suggestions require a separate world transaction."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, model_validator

from shared.protocol import DTO, Event, StateView, Tile


class MapLocation(DTO):
    """A named place on the continuous map, supplied by the map integrator."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    tile: Tile
    tags: list[str] = Field(default_factory=list)


class DirectorConfig(DTO):
    enabled: bool = True
    interval_ticks: int = Field(default=3, ge=1)
    timeout_s: float = Field(default=8, gt=0, le=8)
    npc_alive_limit: int = Field(default=10, ge=1)
    max_proposals: int = Field(default=2, ge=1, le=4)
    locations: list[MapLocation] = Field(default_factory=list)
    resource_limits: dict[str, int] = Field(default_factory=lambda: {'iron': 20, 'wood': 20, 'herb': 20})
    event_budget: int = Field(default=128, ge=16, le=512)
    memory_budget: int = Field(default=24, ge=1, le=64)
    thread_budget: int = Field(default=12, ge=1, le=32)

    @model_validator(mode="after")
    def unique_locations(self):
        if len({place.id for place in self.locations}) != len(self.locations):
            raise ValueError("Location IDs must be unique")
        if any(not key or not 1 <= value <= 20 for key, value in self.resource_limits.items()):
            raise ValueError('Resource limits must have names and quantities between 1 and 20')
        return self

    @classmethod
    def from_file(cls, path: str | Path) -> DirectorConfig:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class WorldMemory(DTO):
    """A source-linked summary, scoped to the saved world branch."""

    id: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)
    source_event_ids: list[str] = Field(min_length=1)
    through_event_seq: int = Field(ge=0)


class StoryThread(DTO):
    id: str = Field(min_length=1)
    topic: str = Field(min_length=1, max_length=300)
    status: Literal["open", "resolved", "abandoned"] = "open"
    entity_ids: list[str] = Field(default_factory=list)
    source_event_ids: list[str] = Field(min_length=1)


class DirectorContext(DTO):
    state: StateView
    events: list[Event]
    memories: list[WorldMemory] = Field(default_factory=list)
    story_threads: list[StoryThread] = Field(default_factory=list)
    locations: list[MapLocation] = Field(default_factory=list)
    resource_needs: list[dict] = Field(default_factory=list)
    history_scope: str = 'full'
    execution_rules: dict = Field(default_factory=dict)
    allowed_proposals: list[Literal["FOLLOW_UP", "RESOURCE_NEED", "MIGRATION"]]

    @model_validator(mode="after")
    def check_sources(self):
        events = {event.id: event for event in self.events}
        if len(events) != len(self.events):
            raise ValueError("Duplicate event IDs")
        sequences = [event.event_seq for event in self.events]
        if sequences != sorted(set(sequences)):
            raise ValueError("Events must have unique increasing sequence numbers")
        if any(event.tick > self.state.tick for event in self.events):
            raise ValueError("Future events are unavailable")
        for record in [*self.memories, *self.story_threads]:
            if not set(record.source_event_ids) <= events.keys():
                raise ValueError("World memory and threads require loaded source events")
        for memory in self.memories:
            if any(events[source].event_seq > memory.through_event_seq
                   for source in memory.source_event_ids):
                raise ValueError("Memory includes events beyond its recorded boundary")
        return self


class DirectorProposal(DTO):
    kind: Literal["FOLLOW_UP", "RESOURCE_NEED", "MIGRATION"]
    source_event_ids: list[str] = Field(min_length=1)
    reason_summary: str = Field(min_length=1, max_length=300)
    target_id: str | None = None
    location_id: str | None = None
    resource: str = 'iron'
    quantity: int = Field(default=1, ge=1, le=20)
    npc_name: str = Field(default='迁入旅人', min_length=1, max_length=30)


class DirectorDecision(DTO):
    summary: str = Field(default="", max_length=1000)
    source_event_ids: list[str] = Field(default_factory=list)
    proposals: list[DirectorProposal] = Field(default_factory=list, max_length=4)


class DirectorProvider(Protocol):
    """B's model adapter implements this callable; C owns its input/output."""

    async def __call__(self, context: DirectorContext) -> DirectorDecision: ...


class DirectorResult(DTO):
    world_id: str
    expected_world_version: int
    mode: Literal["live", "fallback"]
    status: Literal["proposed", "skipped", "unavailable", "rejected"]
    reason_code: str
    decision: DirectorDecision | None = None


def validate_decision(context: DirectorContext, decision: DirectorDecision,
                      config: DirectorConfig) -> None:
    """Validate references; execution must recheck current facts and authority."""
    event_ids = {event.id for event in context.events}
    if decision.summary and not decision.source_event_ids:
        raise ValueError("Summary requires source events")
    if not set(decision.source_event_ids) <= event_ids:
        raise ValueError("Summary cites unavailable events")
    if len(decision.proposals) > config.max_proposals:
        raise ValueError("Proposal budget exceeded")
    actors = {actor.id: actor for actor in context.state.actors}
    organizations = {org.id: org for org in context.state.organizations}
    sites = {site.id for site in context.state.sites}
    locations = {place.id: place for place in context.locations}
    alive_npcs = sum(actor.alive and actor.kind == "npc"
                     for actor in context.state.actors)
    for proposal in decision.proposals:
        if proposal.kind not in context.allowed_proposals:
            raise ValueError("Proposal kind has no enabled executor")
        if not set(proposal.source_event_ids) <= event_ids:
            raise ValueError("Proposal cites unavailable events")
        if proposal.location_id is not None and proposal.location_id not in locations:
            raise ValueError("Unknown map location")
        if proposal.kind == "MIGRATION":
            if proposal.target_id is not None:
                raise ValueError("Migration creates a new identity")
            if alive_npcs >= config.npc_alive_limit:
                raise ValueError("Population limit reached")
            place = locations.get(proposal.location_id)
            if place is None or "migration_entry" not in place.tags:
                raise ValueError("Migration requires a configured entry")
        elif proposal.kind == "RESOURCE_NEED":
            if proposal.resource not in config.resource_limits or proposal.quantity > config.resource_limits[proposal.resource]:
                raise ValueError('Resource request exceeds configured capabilities')
            organization = organizations.get(proposal.target_id)
            if organization is None or organization.status != "active":
                raise ValueError("Resource need requires an active organization")
        else:
            target_id = proposal.target_id
            if target_id not in actors and target_id not in organizations and target_id not in sites:
                raise ValueError("Follow-up requires an existing target")


class WorldDirector:
    """Lock-free model call. Persistence/scheduling remain with C's world service."""

    def __init__(self, config: DirectorConfig, provider: DirectorProvider | None = None):
        self.config = config.model_copy(deep=True)
        self.provider = provider

    async def assess(self, context: DirectorContext, *, last_assessed_tick: int,
                     major_event: bool = False, evaluation_active: bool = False) -> DirectorResult:
        snapshot = context.model_copy(deep=True)
        snapshot.locations = self.config.locations
        result = DirectorResult(
            world_id=snapshot.state.world_id,
            expected_world_version=snapshot.state.world_version,
            mode="fallback", status="skipped", reason_code="NOT_DUE",
        )
        if not self.config.enabled or evaluation_active:
            result.reason_code = "DISABLED" if not self.config.enabled else "EVALUATION_FROZEN"
            return result
        if not major_event and snapshot.state.tick - last_assessed_tick < self.config.interval_ticks:
            return result
        if self.provider is None:
            result.status = "unavailable"
            result.reason_code = "PROVIDER_NOT_CONFIGURED"
            return result
        try:
            raw = await asyncio.wait_for(
                self.provider(snapshot.model_copy(deep=True)), timeout=self.config.timeout_s,
            )
        except asyncio.TimeoutError:
            result.status = 'unavailable'
            result.reason_code = 'MODEL_TIMEOUT'
            return result
        except Exception as exc:
            result.status = "unavailable"
            code = getattr(exc, 'code', '')
            result.reason_code = code if code in {'MODEL_AUTH_FAILED', 'MODEL_RATE_LIMITED',
                'MODEL_HTTP_FAILED', 'MODEL_TIMEOUT', 'MODEL_CONNECTION_FAILED', 'MODEL_INVALID_OUTPUT',
                'MODEL_CONTEXT_TOO_LARGE'} else 'PROVIDER_FAILED'
            return result
        try:
            decision = DirectorDecision.model_validate(raw)
            validate_decision(snapshot, decision, self.config)
        except (ValueError, TypeError):
            result.status = "rejected"
            result.reason_code = "INVALID_DECISION"
            return result
        result.mode = "live"
        result.status = "proposed"
        result.reason_code = "AWAITING_WORLD_VALIDATION"
        result.decision = decision
        return result
