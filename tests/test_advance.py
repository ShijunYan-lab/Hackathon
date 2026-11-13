import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from server.world.director import DirectorConfig, DirectorDecision
from shared.protocol import AgentDecision


def new(client):
    state = client.post('/v1/worlds', json={'request_id': uuid4().hex, 'seed': 42,
                                          'player_name': 'Test'}).json()['data']['state']
    return '/v1/worlds/' + state['world_id'], state


def request(state, **extra):
    return {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
            'reason': 'debug_step', **extra}


def test_fallback_ticks_dedup_invalid_trigger_and_restart(tmp_path):
    db = tmp_path / 'world.sqlite3'
    with TestClient(create_app(db)) as client:
        path, state = new(client)
        assert client.post(path + '/advance', json=request(state, trigger_event_ids=['unknown'])).status_code == 400
        assert client.get(path + '/state').json()['data']['state'] == state
        for tick in range(1, 4):
            body = request(state)
            response = client.post(path + '/advance', json=body)
            assert response.status_code == 200, response.text
            assert client.post(path + '/advance', json=body).json() == response.json()
            data = response.json()['data']
            state = data['state']
            assert data['tick'] == tick
            assert data['decision_summaries'][0]['mode'] == 'fallback'
        assert data['director']['reason_code'] == 'PROVIDER_NOT_CONFIGURED'
        assert client.get(path + '/director/debug').status_code == 403
    with TestClient(create_app(db, allow_debug=True)) as client:
        assert client.get(path + '/state').json()['data']['state'] == state
        assert client.post(path + '/advance', json=body).json() == response.json()
        data = client.post(path + '/advance', json=request(state)).json()['data']
        assert data['director']['reason_code'] == 'NOT_DUE'
        assert len(client.get(path + '/director/debug').json()['data']['runs']) == 4


def test_director_follow_up_private_context_and_persistence(tmp_path):
    contexts = []
    target_ids = []
    async def plan(context, triggers):
        contexts.append(context)
        assert set(triggers) <= {entry.id for entry in context.known_events}
        assert not any(entry.type.startswith('director_') for entry in context.known_events)
        return AgentDecision(intent={'action': 'WAIT'})
    async def direct(context):
        target = next(actor for actor in reversed(context.state.actors) if actor.kind == 'npc')
        target_ids.append(target.id)
        return DirectorDecision(summary='安排一次评估', source_event_ids=[context.events[0].id],
            proposals=[{'kind': 'FOLLOW_UP', 'target_id': target.id,
                        'source_event_ids': [context.events[0].id], 'reason_summary': '了解当前局面'}])
    db = tmp_path / 'world.sqlite3'
    with TestClient(create_app(db, plan_provider=plan, director_provider=direct, allow_debug=True)) as client:
        path, state = new(client)
        for _ in range(3):
            data = client.post(path + '/advance', json=request(state)).json()['data']
            state = data['state']
        assert data['director']['accepted_proposals'] == 1
        assert len(target_ids) == 1
        assert all(not item['type'].startswith('director_') for item in data['events'])
    with TestClient(create_app(db, plan_provider=plan, director_provider=direct, allow_debug=True)) as client:
        data = client.post(path + '/advance', json=request(state)).json()['data']
        assert contexts[-1].npc_id == target_ids[0]
        audit = client.get(path + '/director/debug').json()['data']
        assert audit['focus'][0]['status'] == 'consumed'
        assert audit['runs'][2]['result']['decision']['summary'] == '安排一次评估'
        assert len(target_ids) == 1


def test_invalid_and_timeout_director_and_evaluation_freeze(tmp_path):
    async def invalid(context):
        return DirectorDecision(summary='无来源', source_event_ids=['unknown'])
    async def slow(context):
        await asyncio.sleep(1)
    for provider, status in [(invalid, 'rejected'), (slow, 'unavailable')]:
        app = create_app(tmp_path / (status + '.sqlite3'), director_provider=provider,
                         director_config=DirectorConfig(interval_ticks=1, timeout_s=.01))
        with TestClient(app) as client:
            path, state = new(client)
            app.state.turns.set_evaluation_active(state['world_id'], True)
            body = request(state)
            assert client.post(path + '/advance', json=body).json()['error']['code'] == 'EVALUATION_FROZEN'
            assert client.get(path + '/state').json()['data']['state'] == state
            app.state.turns.set_evaluation_active(state['world_id'], False)
            data = client.post(path + '/advance', json=body).json()['data']
            assert data['director']['status'] == status
            assert data['director']['accepted_proposals'] == 0


def test_advance_concurrent_update_does_not_commit_stale_model(tmp_path):
    entered, release = threading.Event(), threading.Event()
    async def plan(context, triggers):
        entered.set()
        while not release.is_set():
            await asyncio.sleep(.01)
        return AgentDecision(intent={'action': 'WAIT'})
    with TestClient(create_app(tmp_path / 'world.sqlite3', plan_provider=plan, allow_debug=True)) as client:
        path, state = new(client)
        body = request(state)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, path + '/advance', json=body)
            try:
                assert entered.wait(3)
                assert client.post(path + '/advance', json=body).json()['error']['code'] == 'REQUEST_IN_PROGRESS'
                result = client.post(path + '/commands', json={'request_id': uuid4().hex,
                    'expected_world_version': state['world_version'], 'kind': 'CHECKPOINT',
                    'payload': {'region_id': state['current_region_id'], 'positions': [
                        {'actor_id': state['player_id'], 'tile': {'x': 8.5, 'y': 8.5}}]}})
                assert result.status_code == 200
            finally:
                release.set()
            assert future.result().json()['error']['code'] == 'VERSION_CONFLICT'
        assert client.get(path + '/state').json()['data']['state']['tick'] == 0
        assert client.get(path + '/director/debug').json()['data']['runs'] == []


def test_turn_plan_creates_task_without_premature_resource_reward(tmp_path):
    async def gather(context, triggers):
        site = next(entity for entity in context.known_entities if entity.get('kind') == 'herb')
        return AgentDecision(intent={'action': 'GATHER', 'target_id': site['id']})
    with TestClient(create_app(tmp_path / 'world.sqlite3', plan_provider=gather)) as client:
        path, state = new(client)
        original_items = len(state['items'])
        checkpoint = client.post(path + '/commands', json={'request_id': uuid4().hex,
            'expected_world_version': state['world_version'], 'kind': 'CHECKPOINT', 'payload': {
                'region_id': state['current_region_id'], 'positions': [
                    {'actor_id': actor['id'], 'tile': state['actors'][0]['tile']}
                    for actor in state['actors'] if actor['kind'] == 'npc']}}).json()
        state = checkpoint['data']['state']
        data = client.post(path + '/advance', json=request(state)).json()['data']
        assert data['decision_summaries'][0]['intent_status'] == 'scheduled'
        assert len(data['state']['items']) == original_items
        assert data['state']['sites'][0]['remaining'] == 5
        task = data['tasks'][0]
        report = client.post(path + '/commands', json={'request_id': uuid4().hex,
            'expected_world_version': data['state']['world_version'], 'kind': 'TASK_REPORT', 'payload': {
                'task_id': task['id'], 'actor_id': task['actor_id'], 'status': 'succeeded',
                'region_id': task['target_region_id'], 'tile': task['target_tile']}}).json()
        assert report['ok']
        assert len(report['data']['state']['items']) == original_items + 1
        assert report['data']['state']['sites'][0]['remaining'] == 4
