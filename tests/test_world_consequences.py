from uuid import uuid4
from fastapi.testclient import TestClient
from server.main import create_app
from server.world.director import DirectorConfig, DirectorDecision
from shared.protocol import ItemState, ItemStats
from test_economy import setup
from server.world.agent_runtime import build_context


def test_need_drives_migration_then_real_supply_resolves_story(tmp_path):
    contexts = []
    async def provider(context):
        contexts.append(context)
        need = next((event for event in context.events if event.type == 'resource_need_created'), None)
        if need is None:
            return DirectorDecision(proposals=[{'kind': 'RESOURCE_NEED', 'target_id': context.state.organizations[0].id,
                'resource': 'herb', 'quantity': 2, 'source_event_ids': [context.events[0].id], 'reason_summary': '药草供应需要补充'}])
        if any(value['status'] == 'fulfilled' for value in context.resource_needs):
            return DirectorDecision(summary='补给已完成，不再请求迁入', source_event_ids=[context.events[-1].id])
        return DirectorDecision(proposals=[{'kind': 'MIGRATION', 'location_id': 'entry', 'npc_name': '药草旅人',
            'source_event_ids': [need.id], 'reason_summary': '药草需求吸引旅人寻找工作'}])
    app = create_app(tmp_path / 'world.sqlite3', director_provider=provider, allow_debug=True,
        director_config=DirectorConfig(interval_ticks=1, locations=[{'id': 'entry', 'name': '村庄入口',
            'region_id': 'market', 'tile': {'x': 8.5, 'y': 8.5}, 'tags': ['migration_entry']}]))
    with TestClient(app) as client:
        path, state = setup(client)
        def advance():
            nonlocal state
            result = client.post(path + '/advance', json={'request_id': uuid4().hex,
                'expected_world_version': state['world_version'], 'reason': 'debug_step'})
            assert result.status_code == 200, result.text
            state = result.json()['data']['state']
        advance()
        demand = client.get(path + '/economy').json()['data']['resource_needs'][0]
        assert demand['resource'] == 'herb' and demand['quantity'] == 2
        count = len(state['actors'])
        advance()
        assert len(state['actors']) == count + 1
        assert state['actors'][-1]['name'] == '药草旅人'
        model = app.state.store.state(state['world_id'])
        with app.state.store.connection() as connection:
            arrival_context = build_context(connection, model, state['actors'][-1]['id'])
            assert any(value.get('kind') == 'resource_need' for value in arrival_context.known_entities)
        bad = {'request_id': 'bad-supply', 'expected_world_version': state['world_version'],
               'actor_id': state['player_id'], 'org_id': demand['org_id'], 'item_ids': ['missing']}
        assert client.post(path + '/supply', json=bad).status_code == 400
        assert client.get(path + '/economy').json()['data']['resource_needs'][0]['quantity'] == 2
        # Explicit inventory fixture; resource gathering is separately validated.
        ids = []
        for _ in range(2):
            item_id = 'item_' + uuid4().hex
            ids.append(item_id)
            model.items.append(ItemState(id=item_id, name='herb', base_type='material', material_id='herb',
                quality='common', owner_id=model.player_id, stats=ItemStats(damage=0, armor=0, cooldown_s=1),
                origin_event_ids=demand['source_event_ids']))
        with app.state.store.connection(write=True) as connection:
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (model.model_dump_json(), model.world_id))
        body = {'request_id': 'deliver', 'expected_world_version': state['world_version'],
                'actor_id': state['player_id'], 'org_id': demand['org_id'], 'item_ids': ids}
        result = client.post(path + '/supply', json=body)
        assert result.status_code == 200, result.text
        assert client.post(path + '/supply', json=body).json() == result.json()
        state = result.json()['data']['state']
        assert state['organizations'][0]['resources']['herb'] == 2
        advance()
        assert contexts[-1].resource_needs[0]['status'] == 'fulfilled'
        assert len(state['actors']) == count + 1
        threads = client.get(path + '/story?view=debug').json()['data']['story_threads']
        assert any('补给需求' in thread['topic'] and thread['status'] == 'resolved' for thread in threads)
