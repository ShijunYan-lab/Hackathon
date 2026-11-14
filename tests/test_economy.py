from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from server.world.director import DirectorConfig, DirectorDecision
from shared.protocol import ItemState, ItemStats, AgentDecision


def setup(client):
    state = client.post('/v1/worlds', json={'request_id': uuid4().hex, 'seed': 42, 'player_name': 'Test'}).json()['data']['state']
    path = '/v1/worlds/' + state['world_id']
    state = command(client, path, state, 'CHECKPOINT', {'region_id': state['current_region_id'],
        'positions': [{'actor_id': actor['id'], 'tile': state['actors'][0]['tile']} for actor in state['actors']]})
    return path, state


def command(client, path, state, kind, payload):
    result = client.post(path + '/commands', json={'request_id': uuid4().hex,
        'expected_world_version': state['world_version'], 'kind': kind, 'payload': payload})
    assert result.status_code == 200, result.text
    return result.json()['data']['state']


def proposal(client, path, state, **terms):
    body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'], **terms}
    result = client.post(path + '/offers', json=body)
    assert result.status_code == 200, result.text
    assert client.post(path + '/offers', json=body).json() == result.json()
    return result.json()['data']['state'], result.json()['data']['events'][0]['facts']['offer_id']


def test_trade_atomic_payment_ownership_concurrent_retry_and_snapshot(tmp_path):
    with TestClient(create_app(tmp_path / 'world.sqlite3')) as client:
        path, state = setup(client)
        seller, buyer = state['actors'][:2]
        state, offer_id = proposal(client, path, state, actor_id=seller['id'], target_id=buyer['id'], kind='trade',
                                  item_id=seller['equipped_item_id'], price=7)
        before = client.get(path + '/economy').json()['data']
        assert before['wallets'][seller['id']] == 20
        body = {'request_id': 'accept', 'expected_world_version': state['world_version'], 'kind': 'ACCEPT_OFFER',
                'payload': {'actor_id': buyer['id'], 'offer_id': offer_id}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: client.post(path + '/commands', json=body).json(), range(2)))
        assert results[0] == results[1] and results[0]['ok']
        state = results[0]['data']['state']
        after = client.get(path + '/economy').json()['data']
        assert after['wallets'][seller['id']] == 27 and after['wallets'][buyer['id']] == 13
        assert state['actors'][0]['equipped_item_id'] is None
        assert next(item for item in state['items'] if item['id'] == seller['equipped_item_id'])['owner_id'] == buyer['id']
        saved = client.post(path + '/saves', json={'request_id': 'save', 'expected_world_version': state['world_version'], 'label': 'trade'}).json()
        loaded = client.post('/v1/saves/' + saved['data']['save_id'] + '/load', json={'request_id': 'load'}).json()
        assert client.get('/v1/worlds/' + loaded['world_id'] + '/economy').json()['data'] == after


def test_insufficient_funds_no_partial_transfer_and_wrong_acceptor(tmp_path):
    with TestClient(create_app(tmp_path / 'world.sqlite3')) as client:
        path, state = setup(client)
        seller, buyer = state['actors'][:2]
        state, offer_id = proposal(client, path, state, actor_id=seller['id'], target_id=buyer['id'],
            kind='trade', item_id=seller['equipped_item_id'], price=99)
        for actor_id, code in [(buyer['id'], 'INSUFFICIENT_FUNDS'), (seller['id'], 'OFFER_INVALID')]:
            result = client.post(path + '/commands', json={'request_id': uuid4().hex,
                'expected_world_version': state['world_version'], 'kind': 'ACCEPT_OFFER',
                'payload': {'actor_id': actor_id, 'offer_id': offer_id}})
            assert result.json()['error']['code'] == code
        assert client.get(path + '/state').json()['data']['state'] == state


def test_bilateral_relation_invitation_and_representative_departure(tmp_path):
    with TestClient(create_app(tmp_path / 'world.sqlite3')) as client:
        path, state = setup(client)
        left, right = state['organizations']
        state, relation_id = proposal(client, path, state, actor_id=left['representative_id'],
            target_id=right['representative_id'], kind='relation', org_id=left['id'], target_org_id=right['id'], stance='allied')
        assert state['relations'] == []
        state = command(client, path, state, 'ACCEPT_OFFER', {'actor_id': right['representative_id'], 'offer_id': relation_id})
        assert len(state['relations']) == 2 and all(relation['stance'] == 'allied' for relation in state['relations'])
        state, invite = proposal(client, path, state, actor_id=left['representative_id'], target_id=state['player_id'],
                                  kind='invite', org_id=left['id'])
        state = command(client, path, state, 'JOIN_ORG', {'actor_id': state['player_id'], 'org_id': left['id'], 'offer_id': invite})
        assert left['id'] in state['actors'][0]['org_ids']
        state = command(client, path, state, 'LEAVE_ORG', {'actor_id': left['representative_id'], 'org_id': left['id']})
        assert state['organizations'][0]['representative_id'] != left['representative_id']


def test_craft_consumes_real_materials_once_and_equips(tmp_path):
    app = create_app(tmp_path / 'world.sqlite3')
    with TestClient(app) as client:
        path, state = setup(client)
        model = app.state.store.state(state['world_id'])
        # Synthetic inventory isolates manufacturing; gather-to-material is separately tested.
        with app.state.store.connection(write=True) as connection:
            source = connection.execute('SELECT id FROM events WHERE world_id=? ORDER BY seq LIMIT 1', (model.world_id,)).fetchone()[0]
            for material in ('iron', 'iron', 'wood'):
                model.items.append(ItemState(id='item_' + uuid4().hex, name=material, base_type='material',
                    quality='common', material_id=material, owner_id=model.player_id,
                    stats=ItemStats(damage=0, cooldown_s=1, armor=0), origin_event_ids=[source]))
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (model.model_dump_json(), model.world_id))
        body = {'request_id': 'craft', 'expected_world_version': state['world_version'],
                'actor_id': state['player_id'], 'recipe_id': 'iron_sword'}
        result = client.post(path + '/craft', json=body)
        assert result.status_code == 200, result.text
        assert client.post(path + '/craft', json=body).json() == result.json()
        state = result.json()['data']['state']
        crafted_id = result.json()['data']['events'][0]['facts']['item_id']
        state = command(client, path, state, 'EQUIP', {'actor_id': state['player_id'], 'item_id': crafted_id})
        assert not any(item['base_type'] == 'material' for item in state['items'])
        body.update(request_id='again', expected_world_version=state['world_version'])
        assert client.post(path + '/craft', json=body).json()['error']['code'] == 'INSUFFICIENT_MATERIALS'


def test_migration_needs_actual_unused_death_and_preserves_dead_identity(tmp_path):
    async def director(context):
        deaths = [event.id for event in context.events if event.type == 'actor_died']
        return DirectorDecision(proposals=[{'kind': 'MIGRATION', 'location_id': 'entry',
            'source_event_ids': deaths[-1:] or [context.events[0].id], 'reason_summary': '有人迁入填补空缺'}])
    now = [1000.]
    app = create_app(tmp_path / 'world.sqlite3', clock=lambda: now[0], director_provider=director,
        director_config=DirectorConfig(interval_ticks=1, locations=[{'id': 'entry', 'name': '入口',
            'region_id': 'market', 'tile': {'x': 8.5, 'y': 8.5}, 'tags': ['migration_entry']}]))
    with TestClient(app) as client:
        path, state = setup(client)
        def advance():
            nonlocal state
            result = client.post(path + '/advance', json={'request_id': uuid4().hex,
                'expected_world_version': state['world_version'], 'reason': 'debug_step'})
            assert result.status_code == 200, result.text
            state = result.json()['data']['state']
            return result.json()['data']['director']['accepted_proposals']
        assert advance() == 0
        target_id = state['actors'][1]['id']
        for _ in range(50):
            if not next(actor for actor in state['actors'] if actor['id'] == target_id)['alive']:
                break
            now[0] += 1
            state = command(client, path, state, 'HIT', {'attack_id': uuid4().hex,
                'attacker_id': state['player_id'], 'target_id': target_id,
                'weapon_id': state['actors'][0]['equipped_item_id'], 'region_id': state['current_region_id'],
                'attacker_tile': {'x': 8.5, 'y': 8.5}, 'target_tile': {'x': 9.5, 'y': 8.5}})
        count = len(state['actors'])
        assert advance() == 1 and len(state['actors']) == count + 1
        assert not next(actor for actor in state['actors'] if actor['id'] == target_id)['alive']
        assert advance() == 0 and len(state['actors']) == count + 1


def test_invalid_model_economy_terms_are_rejected_without_server_error(tmp_path):
    async def invalid(context, text):
        target = next(value for value in context.known_entities if value.get('kind') == 'player')
        return AgentDecision(intent={'action': 'TRANSFER', 'target_id': target['id'],
            'params': {'item_id': context.own_inventory[0].id, 'price': -1}})
    with TestClient(create_app(tmp_path / 'world.sqlite3', dialogue_provider=invalid)) as client:
        path, state = setup(client)
        result = client.post(path + '/dialogue', json={'request_id': 'invalid',
            'expected_world_version': state['world_version'], 'npc_id': state['actors'][1]['id'], 'text': 'test'})
        assert result.status_code == 200
        assert result.json()['data']['intent_status'] == 'rejected'
        assert client.get(path + '/economy').json()['data']['offers'] == []
