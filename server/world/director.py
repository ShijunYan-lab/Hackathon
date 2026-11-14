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
    chapters: list[dict] = Field(default_factory=list)
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
    source_event_ids: list[str] = Field(min_length=1, max_length=16)
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

    async def __call__(self, context: DirectorContext) -> DirectorDecision | dict: ...


class DirectorResult(DTO):
    world_id: str
    expected_world_version: int
    mode: Literal["live", "fallback"]
    status: Literal["proposed", "skipped", "unavailable", "rejected"]
    reason_code: str
    decision: DirectorDecision | None = None
    issues: list[str] = Field(default_factory=list)


def proposal_issue(context, proposal, config, event_ids):
    if proposal.kind not in context.allowed_proposals:
        return 'PROPOSAL_DISABLED'
    if not set(proposal.source_event_ids) <= event_ids:
        return 'UNKNOWN_EVENT_REFERENCE'
    if proposal.kind == 'FOLLOW_UP':
        if not any(actor.id == proposal.target_id and actor.kind == 'npc' and actor.alive
                   for actor in context.state.actors):
            return 'FOLLOW_UP_TARGET_INVALID'
    elif proposal.kind == 'RESOURCE_NEED':
        if proposal.quantity > config.resource_limits.get(proposal.resource, 0):
            return 'RESOURCE_LIMIT'
        if not any(org.id == proposal.target_id and org.status == 'active' for org in context.state.organizations):
            return 'ORGANIZATION_INVALID'
    else:
        if proposal.target_id is not None:
            return 'MIGRATION_TARGET_INVALID'
        if sum(actor.alive and actor.kind == 'npc' for actor in context.state.actors) >= config.npc_alive_limit:
            return 'POPULATION_LIMIT'
        if not any(place.id == proposal.location_id and 'migration_entry' in place.tags
                   for place in context.locations):
            return 'MIGRATION_ENTRY_INVALID'
    if proposal.location_id is not None and not any(place.id == proposal.location_id for place in context.locations):
        return 'UNKNOWN_LOCATION'
    return None


def review_decision(context, raw, config):
    """An invalid suggestion must not discard other independent, valid output."""
    if isinstance(raw, DirectorDecision):
        raw = raw.model_dump()
    if not isinstance(raw, dict) or not set(raw) <= DirectorDecision.model_fields.keys():
        raise ValueError('Invalid decision object')
    event_ids = {event.id for event in context.events}
    issues = []
    try:
        decision = DirectorDecision.model_validate({key: raw[key] for key in ('summary', 'source_event_ids') if key in raw})
        if ((decision.summary and not decision.source_event_ids)
                or not set(decision.source_event_ids) <= event_ids):
            raise ValueError('Invalid summary evidence')
    except (ValueError, TypeError):
        decision = DirectorDecision()
        issues.append('SUMMARY_EVIDENCE_INVALID')
    proposals = raw.get('proposals', [])
    if not isinstance(proposals, list):
        return decision, issues + ['PROPOSALS_FORMAT_INVALID']
    if len(proposals) > 4:
        issues.append('PROPOSAL_BUDGET_EXCEEDED')
    for candidate in proposals[:4]:
        if len(decision.proposals) >= config.max_proposals:
            issues.append('PROPOSAL_BUDGET_EXCEEDED')
            break
        try:
            proposal = DirectorProposal.model_validate(candidate)
        except (ValueError, TypeError):
            issues.append('PROPOSAL_FORMAT_INVALID')
            continue
        code = proposal_issue(context, proposal, config, event_ids)
        if code:
            issues.append(code)
        else:
            decision.proposals.append(proposal)
    return decision, list(dict.fromkeys(issues))


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
            decision, result.issues = review_decision(snapshot, raw, self.config)
        except (ValueError, TypeError):
            result.status = "rejected"
            result.reason_code = "INVALID_DECISION"
            return result
        if result.issues and not (decision.summary or decision.proposals):
            result.status = "rejected"
            result.reason_code = result.issues[0]
            return result
        result.mode = "live"
        result.status = "proposed"
        result.reason_code = ("PARTIAL_DECISION" if result.issues else
                              "AWAITING_WORLD_VALIDATION" if decision.proposals else "NO_ACTION_PROPOSED")
        result.decision = decision
        return result
