from collections import Counter
from copy import deepcopy

import pytest

from server.agents.sandbox import BLocalSandbox
from server.agents.transport_learning import choose_transport, learn_transport
from shared.evaluation_protocol import LearningProfile, RunMetrics, TransportContext, TransportOutcome


def test_online_learning_changes_executed_action_only():
    s=BLocalSandbox(20261113)
    npc=s.spawn('villager','west_village')
    first=s.run(npc.id,'woodcut')
    context=first.context
    assert first.strategy=='shortcut'
    before=dict(npc.q[context])
    selected,old,new,version=s.learn()
    assert selected==first.strategy
    assert old==before[selected]
    assert new != old
    assert npc.q[context]['detour'] == before['detour']
    assert version==1
    second=s.run(npc.id,'woodcut',second=True)
    assert second.context==first.context
    assert second.route[0]==first.route[0]
    assert second.strategy == max(npc.q[context],key=lambda x:(npc.q[context][x],x=='detour'))
    assert all(m.npc_id==npc.id for m in npc.memories)
    assert first.source_events


def test_rollback_removes_future_knowledge_but_not_audit():
    s=BLocalSandbox(20261113)
    npc=s.spawn('villager','west_village')
    s.run(npc.id,'woodcut')
    s.learn()
    assert s.npcs[npc.id].version==1
    numevents=len(s.events)
    restored=s.rollback()
    assert restored.version==0
    assert restored.q[s._last.context]['shortcut']==.65
    assert restored.q[s._last.context]['detour']==.45
    assert all(m.version<=0 for m in restored.memories)
    assert len(s.events)==numevents


def test_double_learning_rejected():
    import pytest
    s=BLocalSandbox(20261113)
    n=s.spawn('villager')
    s.run(n.id,'woodcut');s.learn()
    with pytest.raises(RuntimeError):s.learn()


def test_multiple_tasks_learn_independently():
    s=BLocalSandbox(9)
    npc=s.spawn('blacksmith','east_village')
    first=s.run(npc.id,'mine')
    s.learn()
    assert first.context in s.npcs[npc.id].q
    assert 'goal=mine' in first.context


def test_similar_situation_generalizes_across_villages():
    s=BLocalSandbox(20261113)
    npc=s.spawn('villager','west_village')
    first=s.run(npc.id,'woodcut')
    s.learn()
    # Migrating NPC can reuse his own experience, even if the home village changes.
    s.npcs[npc.id].home='east_village'
    s.npcs[npc.id].hp=30
    context,strategy=s.choose(s.npcs[npc.id],'woodcut')
    assert context==first.context
    assert strategy==max(s.npcs[npc.id].q[context],key=lambda a:(s.npcs[npc.id].q[context][a],a=='detour'))


def test_autonomous_wander_gather_and_resource_refresh():
    s=BLocalSandbox(9)
    a=s.spawn('villager','east_village')
    b=s.spawn('bandit','east_village')
    events=s.step_world(9)
    assert any(e['kind']=='wander' for e in events)
    assert any(e['kind']=='resource_regrowth' for e in events)
    assert all(m.npc_id==a.id for m in a.memories)
    assert all(m.npc_id==b.id for m in b.memories)
    assert any(k.startswith('wander|') for k in a.q)
    assert a.version > 0 or b.version > 0


def test_opening_world_has_five_per_scene_and_is_seeded():
    sandbox = BLocalSandbox(20261113, populate=True)
    assert Counter(npc.location for npc in sandbox.npcs.values()) == {
        "east_village": 5, "west_village": 5, "forest": 5, "ruins": 5,
    }
    assert sandbox.npcs == BLocalSandbox(20261113, populate=True).npcs
    assert sandbox.npcs != BLocalSandbox(20261114, populate=True).npcs
    assert len({npc.personality for npc in sandbox.npcs.values()}) > 1
    events = {event["id"]: event for event in sandbox.events}
    for npc in sandbox.npcs.values():
        assert len(npc.memories) == 1
        memory = npc.memories[0]
        assert memory.npc_id == npc.id
        assert events[memory.source_event_ids[0]]["npc_id"] == npc.id


@pytest.mark.parametrize("goal", ["woodcut", "mine", "trade", "explore"])
def test_repeat_restores_snapshot_with_preexisting_simulation(goal):
    sandbox = BLocalSandbox(20261113, populate=True)
    npc = sandbox.npcs["npc_local_001"]
    sandbox.tick = 7
    sandbox.resources["forest"] = 0
    sandbox.choose(npc, goal)
    original = deepcopy(sandbox.npcs)
    market = sandbox.market_gold.copy()
    random_state = sandbox.rng.getstate()
    first = sandbox.run(npc.id, goal)
    sandbox.learn()
    sandbox.resources["forest"] = 3
    second = sandbox.run(npc.id, goal, second=True)
    assert second.context == first.context
    if goal == "woodcut":
        assert first.resources == second.resources == 0
        assert not first.success and not second.success
    audit_count = len(sandbox.events)
    restored = sandbox.rollback()
    assert restored.version == 0
    assert sandbox.npcs == original
    assert sandbox.resources["forest"] == 0
    assert sandbox.market_gold == market
    assert sandbox.tick == 7
    assert sandbox.rng.getstate() == random_state
    assert len(sandbox.events) == audit_count
    with pytest.raises(RuntimeError):
        sandbox.run(npc.id, goal, second=True)


def test_transport_uses_actual_outcome_and_restores_old_choice():
    profile = LearningProfile(profile_id="p", learner_id="npc", version=0, context_key="delivery",
                              alpha=.8, values={"direct": .6, "escort": .5}, retrieval_epoch=0)
    context = TransportContext(learner_id="npc", context_key="delivery",
                               available_strategies=["direct", "escort"], own_gold=8,
                               escort_cost=2, guard_id="guard", known_event_ids=["loss"])
    assert choose_transport(context, profile).strategy == "direct"
    metrics = RunMetrics(cargo_initial=10, cargo_delivered=2, gold_initial=8, gold_spent=0,
                         duration_ms=1000, merchant_survived=True, task_success=False,
                         delivered_ratio=.2, reward=.2)
    outcome = TransportOutcome(run_id="first", learner_id="npc", context_key="delivery",
                               profile_version=0, strategy="direct", metrics=metrics,
                               source_event_ids=["loss"])
    update = learn_transport(profile, outcome)
    assert update.updated_profile.values == pytest.approx({"direct": .28, "escort": .5})
    assert list(update.changed_values) == ["direct"]
    assert update.updated_profile.memories[0].source_event_ids == ["loss"]
    assert choose_transport(context, update.updated_profile).strategy == "escort"
    assert choose_transport(context, profile).evidence_memory_ids == []
    assert choose_transport(context, profile).strategy == "direct"
    with pytest.raises(ValueError):
        learn_transport(update.updated_profile, outcome)
