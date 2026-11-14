"""Synthetic provider tests; no real model or gameplay is executed."""
import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from server.world.director import (
    DirectorConfig, DirectorContext, DirectorDecision, DirectorProposal,
    WorldDirector, WorldMemory,
)
from shared.protocol import Event, StateView


def context():
    fixture = Path(__file__).resolve().parents[1] / "examples/state_response.json"
    state = StateView.model_validate(json.loads(fixture.read_text(encoding="utf-8"))["data"]["state"])
    state.tick = 3
    return DirectorContext(
        state=state,
        events=[Event(id="evt_test", event_seq=1, tick=2, type="cargo_lost",
                      facts={"quantity": 2}, caused_by=[], witness_ids=[])],
        allowed_proposals=["FOLLOW_UP", "RESOURCE_NEED", "MIGRATION"],
    )


async def synthetic_provider(value):
    return DirectorDecision(
        summary="Recorded cargo loss requires follow-up.", source_event_ids=["evt_test"],
        proposals=[DirectorProposal(kind="FOLLOW_UP", target_id=value.state.actors[1].id,
                                    source_event_ids=["evt_test"], reason_summary="Inspect the loss.")],
    )


def assess(provider=synthetic_provider, **kwargs):
    return asyncio.run(WorldDirector(DirectorConfig(), provider).assess(
        context(), last_assessed_tick=0, **kwargs))


def test_proposal_keeps_world_unchanged_and_carries_commit_version():
    value = context()
    original = value.model_dump()
    result = asyncio.run(WorldDirector(DirectorConfig(), synthetic_provider).assess(
        value, last_assessed_tick=0))
    assert result.status == "proposed"
    assert result.expected_world_version == value.state.world_version
    assert result.world_id == value.state.world_id
    assert value.model_dump() == original


def test_unconfigured_provider_is_explicit_fallback():
    result = assess(None)
    assert result.mode == "fallback"
    assert result.reason_code == "PROVIDER_NOT_CONFIGURED"
    assert result.decision is None


def test_evaluation_freezes_world_director():
    async def forbidden(value):
        pytest.fail("Evaluation must not invoke the director")
    assert assess(forbidden, evaluation_active=True).reason_code == "EVALUATION_FROZEN"


def test_interval_and_major_event():
    director = WorldDirector(DirectorConfig(), synthetic_provider)
    assert asyncio.run(director.assess(context(), last_assessed_tick=2)).status == "skipped"
    assert asyncio.run(director.assess(context(), last_assessed_tick=2,
                                      major_event=True)).status == "proposed"


@pytest.mark.parametrize("change", ["source", "target", "capability", "migration"])
def test_invalid_suggestion_rejected(change):
    async def invalid(value):
        result = await synthetic_provider(value)
        if change == "source":
            result.proposals[0].source_event_ids = ["evt_other_world"]
        elif change == "target":
            result.proposals[0].target_id = "npc_missing"
        elif change == "capability":
            result.proposals[0].kind = "RESOURCE_NEED"
        else:
            result.proposals[0].kind = "MIGRATION"
            result.proposals[0].target_id = None
        return result
    assert assess(invalid).status == "rejected"


def test_timeout_returns_safe_status():
    async def delayed(value):
        await asyncio.sleep(1)
    result = asyncio.run(WorldDirector(DirectorConfig(timeout_s=0.001), delayed).assess(
        context(), last_assessed_tick=0))
    assert result.reason_code == "MODEL_TIMEOUT"
    assert result.decision is None


def test_future_memory_cannot_enter_context():
    value = context().model_dump()
    value["memories"] = [WorldMemory(id="mem_test", summary="Future knowledge",
        source_event_ids=["evt_future"], through_event_seq=5).model_dump()]
    with pytest.raises(ValidationError):
        DirectorContext.model_validate(value)


def test_disabled_executor_is_rejected():
    value = context()
    value.allowed_proposals = []
    result = asyncio.run(WorldDirector(DirectorConfig(), synthetic_provider).assess(
        value, last_assessed_tick=0))
    assert result.status == "rejected"
