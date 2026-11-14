import asyncio
import json

import pytest

from server.agents import provider, service
from server.agents.cli import BConsole
from server.agents.errors import AgentCallFailed
from server.agents.sandbox import BLocalSandbox
from shared.protocol import AgentContext, Event


def test_private_memories_and_rumour():
    s=BLocalSandbox(1)
    a=s.spawn('villager', 'east_village')
    b=s.spawn('merchant', 'east_village')
    c=s.spawn('guard', 'west_village')
    s.interact(a.id, b.id, '遗迹中有强盗')
    assert b.memories[-1].source_type=='report'
    assert b.memories[-1].confidence < 1
    assert not c.memories
    assert '没有亲自获知' in s.ask_offline(c.id,'你知道遗迹的强盗吗')


def test_dynamic_roles_sites_and_weapons():
    s=BLocalSandbox(4)
    for role in ('villager','merchant','blacksmith','guard','bandit','wildling'):
        p=s.spawn(role)
        assert p.weapon
        assert p.home in ('east_village','west_village')
    assert 'ruins' in s.resources


def agent_context():
    return AgentContext(
        npc_id="npc", world_version=0, identity={"hp": 30}, goals=["采矿"],
        own_inventory=[], known_entities=[{"id": "mine", "name": "矿山"}],
        known_events=[], memories=[
            {"id": "own", "npc_id": "npc", "statement": "矿山"},
            {"id": "private", "npc_id": "other", "statement": "PRIVATE DATA"},
            {"id": "future", "npc_id": "npc", "statement": "FUTURE DATA", "policy_version": 1},
        ], allowed_actions=["WAIT", "MOVE"], policy={"mine:detour": .5}, policy_version=0,
    )


def test_dialogue_repairs_json_without_lending_other_memories(monkeypatch):
    replies = iter(["bad json", '{"reply":"我打算看看矿山。","intent":{"action":"MOVE","target_id":"mine"}}'])
    calls = []

    async def complete(messages):
        calls.append(list(messages))
        assert "PRIVATE DATA" not in messages[1]["content"]
        assert "FUTURE DATA" not in messages[1]["content"]
        return next(replies), "test"

    monkeypatch.setattr(provider, "complete", complete)
    result = asyncio.run(service.dialogue(agent_context(), "你准备去哪？"))
    assert result.intent.target_id == "mine"
    assert len(calls) == 2


@pytest.mark.parametrize("output", [
    {"intent": {"action": "ATTACK", "target_id": "mine"}},
    {"intent": {"action": "MOVE", "target_id": "unknown"}},
    {"intent": {"action": "MOVE", "target_id": "mine", "params": {"hp": 0}}},
    {"evidence_memory_ids": ["private"]},
    {"policy_patch": {"mine:detour": 1}},
])
def test_model_cannot_extend_authority(monkeypatch, output):
    async def complete(messages):
        return json.dumps(output), "test"

    monkeypatch.setattr(provider, "complete", complete)
    context = agent_context()
    with pytest.raises(AgentCallFailed):
        asyncio.run(service.plan(context, []))
    assert service.safe_fallback(context).intent.action == "WAIT"


def test_reflect_keeps_report_unverified_and_applies_only_confirmed_reward(monkeypatch):
    context = agent_context()
    context.known_events = [
        Event(id="report", event_seq=1, tick=1, type="conversation", actor_id="other",
              target_id="npc", facts={}, caused_by=[], witness_ids=[]),
        Event(id="outcome", event_seq=2, tick=2, type="agent_action_outcome", actor_id="npc",
              facts={"policy_key": "mine:detour", "reward": -.5, "policy_version": 0},
              caused_by=[], witness_ids=["npc"]),
    ]

    async def complete(messages):
        return json.dumps({"memory_proposals": [{
            "statement": "矿山有强盗", "source_type": "observation", "source_event_ids": ["report"],
            "status": "supported", "confidence": 1,
        }]}), "test"

    monkeypatch.setattr(provider, "complete", complete)
    decision = asyncio.run(service.reflect(context, ["report", "outcome"]))
    memory = decision.memory_proposals[0]
    assert (memory.source_type, memory.status, memory.confidence) == ("report", "unverified", .5)
    assert decision.policy_patch == pytest.approx({"mine:detour": -.3})
    with pytest.raises(AgentCallFailed):
        asyncio.run(service.reflect(context, ["other_event"]))
    context.identity["hp"] = 0
    with pytest.raises(AgentCallFailed):
        asyncio.run(service.dialogue(context, "你好"))
    assert service.safe_fallback(context).intent is None


def test_plan_chooses_higher_policy_value_within_same_goal(monkeypatch):
    context = agent_context()
    context.identity["action_candidates"] = [
        {"action": "MOVE", "target_id": "mine", "params": {"route": route},
         "strategy_group": "gather_ore", "policy_key": f"mine:{route}"}
        for route in ("shortcut", "detour")
    ]
    context.policy["mine:shortcut"] = .6

    async def complete(messages):
        return json.dumps({"intent": {
            "action": "MOVE", "target_id": "mine", "params": {"route": "shortcut"},
        }}), "test"

    monkeypatch.setattr(provider, "complete", complete)
    assert asyncio.run(service.plan(context, [])).intent.params == {"route": "shortcut"}
    context.policy["mine:shortcut"] = .2
    assert asyncio.run(service.plan(context, [])).intent.params == {"route": "detour"}


def test_relayed_rumor_keeps_origin_and_does_not_amplify_confidence():
    sandbox = BLocalSandbox(1, populate=True)
    a, b, c, d, _ = list(sandbox.npcs)[:5]
    root = sandbox.interact(a, b, "听说遗迹有强盗")
    sandbox.interact(b, c, sandbox.npcs[b].memories[-1].text)
    sandbox.interact(b, d, sandbox.npcs[b].memories[-1].text)
    sandbox.interact(d, c, sandbox.npcs[d].memories[-1].text)
    reports = [memory for memory in sandbox.npcs[c].memories if memory.source_type == "report"]
    assert len(reports) == 1
    assert reports[0].source_event_ids[-1] == root["id"]
    assert reports[0].confidence == .45


def test_provider_rejects_missing_key_without_network(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("LLM_MODEL", "test")
    monkeypatch.setenv("LLM_API_KEY", "")
    with pytest.raises(AgentCallFailed, match="LLM_API_KEY"):
        asyncio.run(provider.complete([]))


def test_console_routes_bare_chinese_to_live_dialogue(monkeypatch, capsys):
    calls = []

    def ask_live(npc, question):
        calls.append((npc.id, question))
        return "我正在东村。", "test"

    monkeypatch.setattr(provider, "ask_live", ask_live)
    console = BConsole(20261113)
    console.onecmd("你现在在干啥")
    console.onecmd("你遇见了谁")
    console.onecmd("")
    console.onecmd("world")
    assert calls == [
        (console.selected, "你现在在干啥"),
        (console.selected, "你遇见了谁"),
    ]
    assert "[live模型=test]" in capsys.readouterr().out
    npc = console.s.npcs[console.selected]
    assert [m.source_type for m in npc.memories] == ["observation", "report", "report"]
    assert "你遇见了谁" in npc.memories[-1].text
