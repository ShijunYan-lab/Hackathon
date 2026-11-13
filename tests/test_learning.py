from server.agents.sandbox import BLocalSandbox


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
