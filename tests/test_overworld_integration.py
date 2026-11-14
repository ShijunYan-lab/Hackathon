"""Compatibility seams between D's map, A's six weapons and B/C's real contract."""
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from release.run_backend import make_app
from server.world.agent_runtime import build_context

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def world(tmp_path):
    app = make_app(tmp_path / 'overworld.sqlite3')
    with TestClient(app) as client:
        state = client.post('/v1/worlds', json={'request_id':'new','seed':42,'player_name':'旅人'}).json()['data']['state']
        yield client, app, state

def command(client, state, kind, payload):
    return client.post(f"/v1/worlds/{state['world_id']}/commands", json={
        'request_id':uuid4().hex, 'expected_world_version':state['world_version'], 'kind':kind, 'payload':payload})

def test_authored_map_and_limited_agent_knowledge(world):
    client, app, state = world
    assert state['current_region_id'] == 'overworld'
    assert len(state['actors']) == 30
    assert len({actor['appearance_key'] for actor in state['actors'][1:16]}) == 15
    region = json.loads((ROOT / 'game/maps/backend_world.json').read_text(encoding='utf-8'))['regions'][0]
    assert (region['width_tiles'],region['height_tiles']) == (320,224)
    blocked = {tuple(cell) for cell in region['blocked_tiles']}
    for actor in state['actors']:
        assert (int(actor['tile']['x']),int(actor['tile']['y'])) not in blocked
    model = app.state.store.state(state['world_id'])
    with app.state.store.connection() as connection:
        context = build_context(connection, model, model.actors[1].id)
    assert context.identity['role'] == '铁匠'
    assert context.goals
    assert model.actors[-1].id not in {value['id'] for value in context.known_entities}

def grant_test_weapon(app,state,kind):
    # Combat protocol tests deliberately equip a fixture weapon. Production new
    # games must not receive the test arsenal.
    from server.world import living_world as life
    import random
    model=app.state.store.state(state['world_id'])
    with app.state.store.connection(write=True) as connection:
        source=connection.execute('SELECT id FROM events WHERE world_id=? ORDER BY seq LIMIT 1',(model.world_id,)).fetchone()[0]
        item=life._new_item(model,model.player_id,source,random.Random(10),kind=kind)
        connection.execute('UPDATE worlds SET state=? WHERE id=?',(model.model_dump_json(),model.world_id))
    return model.model_dump(mode='json'),item.model_dump(mode='json')

@pytest.mark.parametrize('kind,reach', [('sword',1),('axe',1),('hammer',1),('bow',8),('crossbow',10),('staff',8)])
def test_a_weapon_equip_and_authoritative_hit(world,kind,reach):
    client, app, state = world
    state,weapon=grant_test_weapon(app,state,kind)
    player, target = state['actors'][:2]
    response = command(client,state,'EQUIP',{'actor_id':player['id'],'item_id':weapon['id']})
    assert response.status_code == 200
    state = response.json()['data']['state']
    hit = {'attack_id':uuid4().hex,'attacker_id':player['id'],'target_id':target['id'],
           'weapon_id':weapon['id'],'region_id':'overworld','attacker_tile':{'x':120.5,'y':143.5},
           'target_tile':{'x':120.5+reach,'y':143.5}}
    result = command(client,state,'HIT',hit)
    assert result.status_code == 200, result.text
    updated = result.json()['data']['state']
    assert updated['actors'][1]['hp'] == target['hp'] - max(1,weapon['stats']['damage']-target['armor'])
    duplicate = command(client,updated,'HIT',hit).json()
    assert duplicate['data']['command_result']['applied'] is False
    assert duplicate['data']['state']['actors'][1]['hp'] == updated['actors'][1]['hp']

def test_transport_uses_reachable_big_map(world):
    client, _, _ = world
    result = client.post('/v1/evaluations',json={'request_id':'scenario','seed':42})
    assert result.status_code == 200, result.text
    assert result.json()['data']['state']['actors'][0]['tile'] == {'x':120.5,'y':143.5}

def test_equipped_ranged_weapon_cannot_hit_past_its_range(world):
    client, app, state = world
    state,bow=grant_test_weapon(app,state,'bow')
    player, target = state['actors'][:2]
    state = command(client,state,'EQUIP',{'actor_id':player['id'],'item_id':bow['id']}).json()['data']['state']
    result = command(client,state,'HIT',{'attack_id':'distant','attacker_id':player['id'],
        'target_id':target['id'],'weapon_id':bow['id'],'region_id':'overworld',
        'attacker_tile':{'x':120.5,'y':143.5},'target_tile':{'x':133.5,'y':143.5}})
    assert result.json()['error']['code'] == 'OUT_OF_RANGE'
    current = client.get(f"/v1/worlds/{state['world_id']}/state").json()['data']['state']
    assert current == state
