from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from server.evaluation.scenario import TransportScenario
from shared.evaluation_protocol import EvaluationStateData, EvaluationReportData, TransportChoice


def create_run(client):
    body = {'request_id': uuid4().hex, 'seed': 42}
    created = client.post('/v1/evaluations', json=body)
    assert created.status_code == 200, created.text
    assert client.post('/v1/evaluations', json=body).json() == created.json()
    data = created.json()['data']
    path = '/v1/evaluations/' + data['session']['evaluation_id']
    request = {'request_id': uuid4().hex, 'expected_evaluation_version': 0, 'kind': 'first'}
    started = client.post(path + '/runs', json=request)
    assert started.status_code == 202, started.text
    assert client.post(path + '/runs', json=request).json() == started.json()
    data = started.json()['data']
    EvaluationStateData.model_validate(data)
    return path, data


def arrive(client, data):
    state = data['state']
    task = next(task for task in state['tasks'] if task['actor_id'] == data['session']['learner_id'])
    body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
        'kind': 'TASK_REPORT', 'payload': {'task_id': task['id'], 'actor_id': task['actor_id'],
        'status': 'succeeded', 'region_id': task['target_region_id'], 'tile': task['target_tile']}}
    route = '/v1/worlds/' + state['world_id'] + '/commands'
    result = client.post(route, json=body)
    assert result.status_code == 200, result.text
    assert client.post(route, json=body).json() == result.json()
    return result.json()['data']['state']


def hit(client, data, now):
    state = data['state']
    monster = next(actor for actor in state['actors'] if actor['kind'] == 'monster')
    merchant = next(actor for actor in state['actors'] if actor['id'] == data['session']['learner_id'])
    now[0] += 1
    body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'], 'kind': 'HIT',
        'payload': {'attack_id': uuid4().hex, 'attacker_id': monster['id'], 'target_id': merchant['id'],
            'weapon_id': monster['equipped_item_id'], 'region_id': state['current_region_id'],
            'attacker_tile': {'x': 9.5, 'y': 8.5}, 'target_tile': {'x': 8.5, 'y': 8.5}}}
    route = '/v1/worlds/' + state['world_id'] + '/commands'
    result = client.post(route, json=body)
    assert result.status_code == 200, result.text
    assert client.post(route, json=body).json() == result.json()
    data['state'] = result.json()['data']['state']
    return body


def test_transport_actual_hits_delivery_and_audit(tmp_path):
    now = [1000.]
    with TestClient(create_app(tmp_path / 'world.sqlite3', clock=lambda: now[0])) as client:
        path, data = create_run(client)
        assert data['run']['strategy'] == 'direct' and not data['run']['measured']
        hit(client, data, now)
        arrive(client, data)
        report = client.get(path + '/report').json()['data']
        EvaluationReportData.model_validate(report)
        metrics = report['runs'][0]['metrics']
        assert metrics['cargo_delivered'] == 8 and metrics['reward'] == .8
        assert metrics['task_success'] and metrics['gold_spent'] == 0
        assert report['session']['status'] == 'learning'
        assert not report['comparable']
        assert client.post(path + '/runs', json={'request_id': 'early', 'kind': 'second',
            'expected_evaluation_version': report['session']['evaluation_version']}).status_code == 409


def test_escort_real_payment_and_deadline(tmp_path):
    def choose(context, profile):
        return TransportChoice(strategy='escort', profile_version=profile.version, reason_summary='test double')
    now = [1000.]
    app = create_app(tmp_path / 'world.sqlite3', choose_provider=choose, clock=lambda: now[0])
    with TestClient(app) as client:
        path, data = create_run(client)
        assert {task['kind'] for task in data['state']['tasks']} == {'MOVE', 'ESCORT'}
        now[0] += 46
        app.state.evaluations.expire()
        report = client.get(path + '/report').json()['data']
        metrics = report['runs'][0]['metrics']
        assert metrics['cargo_delivered'] == 0 and metrics['gold_spent'] == 5
        assert metrics['reward'] == -.025 and not metrics['task_success']
        with app.state.store.connection() as connection:
            row = connection.execute('SELECT body FROM evaluation_runs WHERE id=?', (data['run']['run_id'],)).fetchone()
            import json
            assert json.loads(row[0])['guard_gold'] == 5
        app.state.evaluations.expire()
        assert client.get(path + '/report').json()['data'] == report


def test_merchant_death_is_terminal_and_score_cannot_be_submitted(tmp_path):
    now = [1000.]
    with TestClient(create_app(tmp_path / 'world.sqlite3', clock=lambda: now[0])) as client:
        path, data = create_run(client)
        for _ in range(6):
            merchant = next(actor for actor in data['state']['actors'] if actor['id'] == data['session']['learner_id'])
            if not merchant['alive']:
                break
            hit(client, data, now)
        report = client.get(path + '/report').json()['data']
        assert report['runs'][0]['metrics']['merchant_survived'] is False
        assert report['runs'][0]['metrics']['cargo_delivered'] == 0
        assert client.post(path + '/runs', json={'request_id': 'cheat', 'kind': 'second',
            'expected_evaluation_version': 2, 'reward': 1}).status_code == 422


def test_escort_requires_consent(tmp_path):
    def invalid(context, profile):
        assert 'escort' not in context.available_strategies
        return TransportChoice(strategy='escort', profile_version=0, reason_summary='invalid test double')
    with TestClient(create_app(tmp_path / 'world.sqlite3', choose_provider=invalid,
        transport_scenario=TransportScenario(guard_consents=False))) as client:
        data = client.post('/v1/evaluations', json={'request_id': 'create', 'seed': 42}).json()['data']
        path = '/v1/evaluations/' + data['session']['evaluation_id']
        result = client.post(path + '/runs', json={'request_id': 'run', 'kind': 'first', 'expected_evaluation_version': 0})
        assert result.status_code == 400
        assert client.get(path).json()['data']['session']['status'] == 'ready'
