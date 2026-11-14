import time

from fastapi.testclient import TestClient

from server.main import create_app
from server.evaluation.learning import fallback_update
from shared.evaluation_protocol import EvaluationReportData
from test_transport import create_run, arrive


def wait_learning(client, path):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        data = client.get(path + '/report').json()['data']
        if data['session']['status'] == 'ready_for_second':
            return data
        time.sleep(.02)
    raise AssertionError('automatic learning did not finish')


def test_automatic_failure_learning_only_updates_attempted_strategy_once(tmp_path):
    now = [1000.]
    db = tmp_path / 'world.sqlite3'
    app = create_app(db, clock=lambda: now[0])
    with TestClient(app) as client:
        path, data = create_run(client)
        now[0] += 46
        app.state.evaluations.expire()
        report = wait_learning(client, path)
        EvaluationReportData.model_validate(report)
        update = report['learning_update']
        assert abs(update['updated_profile']['values']['direct'] - .12) < 1e-9
        assert update['updated_profile']['values']['escort'] == .5
        assert update['updated_profile']['version'] == 1
        assert update['updated_profile']['retrieval_epoch'] == 1
        assert update['source_run_id'] == data['run']['run_id']
        assert set(update['source_event_ids']) == set(report['runs'][0]['source_event_ids'])
        with app.state.store.connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM events WHERE world_id=? AND body LIKE '%learning_committed%'",
                (data['run']['world_id'],)).fetchone()[0]
            assert count == 1
    with TestClient(create_app(db, clock=lambda: now[0])) as client:
        assert client.get(path + '/report').json()['data'] == report


def test_success_learning_does_not_force_strategy_switch(tmp_path):
    with TestClient(create_app(tmp_path / 'world.sqlite3')) as client:
        path, data = create_run(client)
        arrive(client, data)
        update = wait_learning(client, path)['learning_update']
        assert abs(update['updated_profile']['values']['direct'] - .92) < 1e-9
        assert update['updated_profile']['values']['escort'] == .5


def test_invalid_learning_is_audited_and_replaced_by_rule_fallback(tmp_path):
    def malicious(profile, outcome):
        update = fallback_update(profile, outcome)
        update.updated_profile.values['escort'] = 1
        return update
    app = create_app(tmp_path / 'world.sqlite3', learn_provider=malicious)
    with TestClient(app) as client:
        path, data = create_run(client)
        arrive(client, data)
        report = wait_learning(client, path)
        assert report['learning_update']['updated_profile']['values']['escort'] == .5
        with app.state.store.connection() as connection:
            records = [row[0] for row in connection.execute('SELECT body FROM events WHERE world_id=?',
                       (data['run']['world_id'],))]
        assert any('PROVIDER_FAILED_OR_INVALID_UPDATE' in record for record in records)
