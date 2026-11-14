import threading
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from server.evaluation.learning import fallback_update
from shared.evaluation_protocol import EvaluationReportData
from test_transport import create_run, arrive
from test_evaluation_learning import wait_learning


def test_same_baseline_second_comparison_and_complete_rollback(tmp_path):
    now = [1000.]
    db = tmp_path / 'world.sqlite3'
    app = create_app(db, clock=lambda: now[0])
    with TestClient(app) as client:
        path, first = create_run(client)
        original_actors = first['state']['actors']
        now[0] += 46
        app.state.evaluations.expire()
        learned = wait_learning(client, path)
        body = {'request_id': uuid4().hex, 'kind': 'second',
                'expected_evaluation_version': learned['session']['evaluation_version']}
        result = client.post(path + '/runs', json=body)
        assert result.status_code == 202, result.text
        second = result.json()['data']
        assert second['run']['strategy'] == 'escort'
        assert second['run']['world_id'] != first['run']['world_id']
        for old, new in zip(original_actors, second['state']['actors']):
            for field in ('hp', 'armor', 'equipped_item_id', 'tile', 'alive'):
                assert old[field] == new[field]
        now[0] += 10
        arrive(client, second)
        report = client.get(path + '/report').json()['data']
        EvaluationReportData.model_validate(report)
        assert report['comparable'] and report['improvement'] == 'improved'
        assert report['runs'][0]['metrics']['cargo_delivered'] == 0
        assert report['runs'][1]['metrics']['cargo_delivered'] == 10
        assert report['runs'][1]['metrics']['gold_spent'] == 5
        assert report['learning_update']['to_version'] == 1
        rollback = {'request_id': 'rollback', 'expected_evaluation_version': report['session']['evaluation_version']}
        restored = client.post(path + '/rollback', json=rollback).json()
        assert restored['ok'] and restored['data']['run'] is None
        assert client.post(path + '/rollback', json=rollback).json() == restored
        profile = client.get(path + '/profile').json()['data']
        assert profile['baseline_profile'] == profile['active_profile']
        assert profile['active_profile']['memories'] == []
        assert profile['active_profile']['retrieval_epoch'] == 0
        check = client.post(path + '/runs', json={'request_id': 'check', 'kind': 'rollback_check',
            'expected_evaluation_version': restored['data']['session']['evaluation_version']}).json()['data']
        assert check['run']['strategy'] == 'direct' and check['run']['profile_version'] == 0
        arrive(client, check)
        assert client.get(path + '/profile').json()['data']['active_profile']['version'] == 0
        assert client.get(path + '/report').json()['data']['runs'][:2] == report['runs']
    with TestClient(create_app(db, clock=lambda: now[0])) as client:
        assert client.get(path + '/profile').json()['data']['active_profile'] == profile['baseline_profile']


def test_rollback_invalidates_in_flight_learning(tmp_path):
    entered, release = threading.Event(), threading.Event()
    def delayed(profile, outcome):
        entered.set()
        release.wait(3)
        return fallback_update(profile, outcome)
    app = create_app(tmp_path / 'world.sqlite3', learn_provider=delayed)
    with TestClient(app) as client:
        path, first = create_run(client)
        arrive(client, first)
        try:
            assert entered.wait(2)
            session = client.get(path).json()['data']['session']
            result = client.post(path + '/rollback', json={'request_id': 'rollback',
                'expected_evaluation_version': session['evaluation_version']})
            assert result.status_code == 200
        finally:
            release.set()
        client.portal.call(app.state.evaluations.learn_pending)
        data = client.get(path + '/profile').json()['data']
        assert data['active_profile'] == data['baseline_profile']
        assert client.get(path + '/report').json()['data']['learning_update'] is None


def test_running_rollback_cancels_old_world_and_conditions_change_is_rejected(tmp_path):
    app = create_app(tmp_path / 'world.sqlite3')
    with TestClient(app) as client:
        path, first = create_run(client)
        restored = client.post(path + '/rollback', json={'request_id': 'rollback',
            'expected_evaluation_version': first['session']['evaluation_version']}).json()['data']
        old_path = '/v1/worlds/' + first['state']['world_id']
        old = client.get(old_path + '/state').json()['data']['state']
        assert all(task['status'] == 'cancelled' for task in old['tasks'])
        assert client.post(old_path + '/commands', json={'request_id': 'late',
            'expected_world_version': old['world_version'], 'kind': 'CHECKPOINT', 'payload': {
                'region_id': old['current_region_id'], 'positions': [
                {'actor_id': old['player_id'], 'tile': old['actors'][0]['tile']}]}}).status_code == 409
        app.state.evaluations.execution_identity = {'model': 'different', 'prompt_hash': 'different'}
        result = client.post(path + '/runs', json={'request_id': 'check', 'kind': 'rollback_check',
            'expected_evaluation_version': restored['session']['evaluation_version']})
        assert result.json()['error']['code'] == 'SNAPSHOT_MISMATCH'
