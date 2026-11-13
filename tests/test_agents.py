from server.agents.sandbox import BLocalSandbox


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
