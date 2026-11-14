from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from test_agent_runtime import prepare, gather_provider


def test_snapshot_full_task_memory_rng_and_isolated_branches(tmp_path):
    db = tmp_path / 'world.sqlite3'
    app = create_app(db, dialogue_provider=gather_provider, allow_debug=True)
    with TestClient(app) as client:
        path, state, dialogue = prepare(client)
        state = client.post(path + '/dialogue', json=dialogue).json()['data']['state']
        save_request = {'request_id': 'save', 'expected_world_version': state['world_version'], 'label': 'S0'}
        saved = client.post(path + '/saves', json=save_request).json()
        assert saved['ok']
        assert client.post(path + '/saves', json=save_request).json() == saved
        save_id = saved['data']['save_id']
        load_path = '/v1/saves/' + save_id + '/load'
        with ThreadPoolExecutor(max_workers=2) as pool:
            copies = list(pool.map(lambda _: client.post(load_path, json={'request_id': 'load'}).json(), range(2)))
        assert copies[0] == copies[1]
        branch = copies[0]['data']['state']
        sibling = client.post(load_path, json={'request_id': 'load2'}).json()['data']['state']
        assert branch['world_id'] != sibling['world_id'] != state['world_id']
        expected = dict(saved['data']['state'], world_id=branch['world_id'])
        assert branch == expected
        branch_path = '/v1/worlds/' + branch['world_id']
        npc = dialogue['npc_id']
        assert client.get(path + f'/agents/{npc}/debug').json()['data'] == client.get(
            branch_path + f'/agents/{npc}/debug').json()['data']
        assert client.get(path + '/story?view=debug').json()['data'] == client.get(
            branch_path + '/story?view=debug').json()['data']
        task = branch['tasks'][0]
        report = {'request_id': uuid4().hex, 'expected_world_version': branch['world_version'],
            'kind': 'TASK_REPORT', 'payload': {'task_id': task['id'], 'actor_id': task['actor_id'],
                'status': 'succeeded', 'region_id': task['target_region_id'], 'tile': task['target_tile']}}
        done = client.post(branch_path + '/commands', json=report).json()
        assert done['ok']
        assert done['data']['state']['sites'][0]['remaining'] == 4
        assert client.get(path + '/state').json()['data']['state']['sites'][0]['remaining'] == 5
        assert client.get('/v1/worlds/' + sibling['world_id'] + '/state').json()['data']['state'] == sibling
        with app.state.store.connection() as connection:
            original_rng = app.state.store.world_row(connection, state['world_id'])['rng_state']
            assert app.state.store.world_row(connection, branch['world_id'])['rng_state'] == original_rng
            assert connection.execute('SELECT COUNT(*) FROM agent_requests WHERE scope LIKE ?',
                                      (branch['world_id'] + '/%',)).fetchone()[0] == 0
    with TestClient(create_app(db)) as client:
        assert client.post(load_path, json={'request_id': 'load'}).json() == copies[0]
        assert client.get(branch_path + '/state').json() == done | {'request_id': 'state', 'data': {'state': done['data']['state']}}


def test_snapshot_invalid_versions_request_reuse_and_tamper(tmp_path):
    app = create_app(tmp_path / 'world.sqlite3')
    with TestClient(app) as client:
        path, state, _ = prepare(client)
        body = {'request_id': 'save', 'expected_world_version': 999, 'label': 'S0'}
        assert client.post(path + '/saves', json=body).status_code == 409
        body['expected_world_version'] = state['world_version']
        result = client.post(path + '/saves', json=body).json()
        body['label'] = 'different'
        assert client.post(path + '/saves', json=body).json()['error']['code'] == 'REQUEST_ID_REUSED'
        save_id = result['data']['save_id']
        with app.state.store.connection(write=True) as connection:
            connection.execute("UPDATE saves SET hash='bad' WHERE id=?", (save_id,))
        assert client.post('/v1/saves/' + save_id + '/load', json={'request_id': 'load'}).json()['error']['code'] == 'SNAPSHOT_MISMATCH'
        assert client.post('/v1/saves/missing/load', json={'request_id': 'load'}).status_code == 404
