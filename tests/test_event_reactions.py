"""No live LLM needed for emergency action planning."""
import asyncio

import pytest

from server.agents import provider, service
from server.agents.event_reactions import legal_candidates, propose_emergency_reaction
from server.agents.errors import AgentCallFailed
from shared.protocol import AgentContext, Event


def context(personality: str, hp: int = 30, max_hp: int = 30):
    return AgentContext(
        npc_id="merchant", world_version=8,
        identity={
            "name": "艾莉", "role": "merchant", "personality": personality,
            "hp": hp, "max_hp": max_hp,
            "action_candidates": [
                {"action": "ATTACK", "target_id": "player", "params": {"weapon_id": "sword"}},
                {"action": "FLEE", "params": {"distance": 5}, "reaction_role": "escape"},
                {"action": "SHARE_INFO", "target_id": "guard", "params": {"topic": "help"},
                 "reaction_role": "seek_help"},
            ],
        },
        goals=["保住货物"], own_inventory=[],
        known_entities=[{"id": "player", "name": "旅人"}, {"id": "guard", "name": "守卫"}],
        known_events=[Event(
            id="evt_attack", event_seq=8, tick=7,
            type="hit_confirmed", actor_id="player", target_id="merchant",
            facts={"damage": 6}, caused_by=["cmd_hit"], witness_ids=["merchant"],
        )],
        memories=[], allowed_actions=["WAIT", "MOVE", "ATTACK", "FLEE", "SHARE_INFO"],
        policy={}, policy_version=0,
    )


@pytest.mark.parametrize("character,hp,expected", [
    ("胆小谨慎，会避险", 30, "FLEE"),
    ("勇敢好胜，遇险敢于防卫", 30, "ATTACK"),
    ("勇敢好胜，遇险敢于防卫", 8, "FLEE"),
    ("随和但有原则", 30, "SHARE_INFO"),
])
def test_personality_and_health_change_reaction_without_llm(monkeypatch, character, hp, expected):
    async def never_complete(*args, **kwargs):
        raise AssertionError("physical emergency must not call a model")
    monkeypatch.setattr(provider, "complete", never_complete)
    choice = asyncio.run(service.plan(context(character, hp), ["evt_attack"]))
    assert choice.intent.action == expected
    assert choice.memory_proposals[0].source_event_ids == ["evt_attack"]
    assert choice.policy_patch == {}


def test_targetless_flee_candidate_kept_and_params_unchanged():
    c = context("谨慎")
    choices = legal_candidates(c)
    flee = next(item for item in choices if item["action"] == "FLEE")
    assert flee["target_id"] is None
    assert flee["params"] == {"distance": 5}
    assert propose_emergency_reaction(c, ["evt_attack"]).intent.params == {"distance": 5}


def test_witness_only_is_not_directly_attacked():
    c = context("勇敢")
    c.known_events[0] = c.known_events[0].model_copy(update={"target_id": "guard"})
    assert propose_emergency_reaction(c, ["evt_attack"]) is None


def test_unverified_report_cannot_trigger_self_defense():
    c = context("勇敢")
    c.known_events[0] = c.known_events[0].model_copy(update={"type": "rumor"})
    assert propose_emergency_reaction(c, ["evt_attack"]) is None


def test_only_c_authorized_actions_are_used():
    c = context("勇敢")
    c.identity["action_candidates"] = [
        {"action": "ATTACK", "target_id": "unknown_actor", "params": {}},
        {"action": "FLEE", "params": {"distance": 3}},
    ]
    decision = propose_emergency_reaction(c, ["evt_attack"])
    assert decision.intent.action == "FLEE"
    assert decision.intent.params == {"distance": 3}


def test_no_candidates_means_wait_not_unapproved_attack():
    c = context("勇敢")
    c.identity["action_candidates"] = []
    decision = propose_emergency_reaction(c, ["evt_attack"])
    assert decision.intent.action == "WAIT"


def test_model_must_use_candidate_if_exact_candidates_given(monkeypatch):
    c = context("勇敢")
    # No attack trigger. The model cannot choose an undeclared target-free action.
    c.known_events = []
    c.identity["action_candidates"] = [
        {"action": "MOVE", "target_id": "guard", "params": {}},
    ]
    async def illegal_output(messages):
        return '{"intent":{"action":"FLEE"}}', "test"
    monkeypatch.setattr(provider, "complete", illegal_output)
    with pytest.raises(AgentCallFailed):
        asyncio.run(service.plan(c, []))


def test_repeated_attack_event_does_not_repeat_memory_proposal():
    c = context("谨慎")
    c.memories.append({
        "id": "mem_evt_attack", "npc_id": "merchant",
        "statement": "我亲身遭遇来自 player 的攻击，需要重新判断安全与信任。",
        "source_event_ids": ["evt_attack"], "policy_version": 0,
    })
    decision = propose_emergency_reaction(c, ["evt_attack"])
    assert not decision.memory_proposals


def test_social_insult_appraisal_is_personalized_and_not_world_mutation():
    from server.agents.social_feedback import assess_social_event
    polite = context("随和但有原则")
    proud = context("勇敢好胜")
    insult = Event(
        id="speech_1", event_seq=9, tick=8, type="social_utterance",
        actor_id="player", target_id="merchant",
        facts={"speech_act": "insult"}, caused_by=[], witness_ids=["merchant"],
    )
    polite.known_events.append(insult)
    proud.known_events.append(insult)
    original_identity = dict(polite.identity)
    impact1 = assess_social_event(polite, "speech_1")
    impact2 = assess_social_event(proud, "speech_1")
    assert impact2.anger_delta > impact1.anger_delta
    assert impact2.hostility_delta > impact1.hostility_delta
    assert polite.identity == original_identity
    assert impact1.as_dict()["source_event_id"] == "speech_1"


def test_only_confirmed_direct_utterance_produces_social_appraisal():
    from server.agents.social_feedback import assess_social_event
    c = context("勇敢好胜")
    variants = (
        ("social_utterance", "guard", {"speech_act": "insult"}),
        ("rumor", "merchant", {"speech_act": "insult"}),
        ("social_utterance", "merchant", {}),
    )
    for kind, target, facts in variants:
        c.known_events = [Event(id="social", event_seq=9, tick=8, type=kind,
                                actor_id="player", target_id=target, facts=facts,
                                caused_by=[], witness_ids=["merchant"])]
        assert assess_social_event(c, "social") is None
    assert assess_social_event(c, "not_visible") is None


def test_apology_does_not_mean_instant_full_forgiveness():
    from server.agents.social_feedback import assess_social_event
    c = context("谨慎")
    c.known_events.append(Event(id="apology", event_seq=9, tick=8,
        type="social_utterance", actor_id="player", target_id="merchant",
        facts={"speech_act": "apology"}, caused_by=[], witness_ids=["merchant"]))
    impact = assess_social_event(c, "apology")
    assert 0 < impact.trust_delta < .5
    assert impact.hostility_delta < 0


def test_explicitly_empty_candidate_list_forbids_unapproved_intent(monkeypatch):
    c = context("随和")
    c.known_events = []
    c.identity["action_candidates"] = []
    async def bad(messages):
        return '{"intent":{"action":"ATTACK","target_id":"player"}}', "test"
    monkeypatch.setattr(provider, "complete", bad)
    with pytest.raises(AgentCallFailed):
        asyncio.run(service.plan(c, []))


def test_production_memory_relay_deduplicates_common_origin():
    from server.agents.memory import validate_proposals
    from shared.protocol import MemoryProposal
    c = context("谨慎")
    report_a = Event(id="report_a", event_seq=10, tick=9, type="conversation",
                     actor_id="player", target_id="merchant",
                     facts={"source_type": "report", "source_event_ids": ["rumor_root"]},
                     caused_by=[], witness_ids=["merchant"])
    report_b = Event(id="report_b", event_seq=11, tick=10, type="conversation",
                     actor_id="guard", target_id="merchant",
                     facts={"source_type": "report", "source_event_ids": ["rumor_root"]},
                     caused_by=[], witness_ids=["merchant"])
    c.known_events.extend([report_a, report_b])
    c.memories.append({
        "id": "mem_old", "npc_id": "merchant", "statement": "遗迹有强盗",
        "source_event_ids": ["report_a"], "policy_version": 0,
    })
    proposed = MemoryProposal(statement="遗迹有强盗", source_type="report",
                              source_event_ids=["report_b"], confidence=.45, status="unverified")
    assert validate_proposals(c, [proposed], {"report_b": report_b}) == []
