"""Synthetic client reports for API verification; NOT a Godot performance benchmark."""
import json
import time
from uuid import uuid4

from server.api.smoke import call


def main():
    created = call('/v1/evaluations', {'request_id': uuid4().hex, 'seed': 42})['data']
    path = '/v1/evaluations/' + created['session']['evaluation_id']
    first = call(path + '/runs', {'request_id': uuid4().hex, 'kind': 'first',
                                  'expected_evaluation_version': 0})['data']

    def finish(data, status):
        state = data['state']
        task = next(task for task in state['tasks'] if task['kind'] == 'MOVE')
        payload = {'task_id': task['id'], 'actor_id': task['actor_id'], 'status': status,
                   'region_id': task['target_region_id'], 'tile': task['target_tile']}
        if status == 'failed':
            payload['failure_code'] = 'SYNTHETIC_CLIENT_FAILURE'
        return call('/v1/worlds/' + state['world_id'] + '/commands', {
            'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
            'kind': 'TASK_REPORT', 'payload': payload})

    finish(first, 'failed')
    for _ in range(100):
        report = call(path + '/report')['data']
        if report['session']['status'] == 'ready_for_second':
            break
        time.sleep(.1)
    assert report['session']['status'] == 'ready_for_second'
    second = call(path + '/runs', {'request_id': uuid4().hex, 'kind': 'second',
        'expected_evaluation_version': report['session']['evaluation_version']})['data']
    assert second['run']['strategy'] == 'escort'
    finish(second, 'succeeded')
    report = call(path + '/report')['data']
    assert report['comparable'] and report['improvement'] == 'improved'
    rolled = call(path + '/rollback', {'request_id': uuid4().hex,
        'expected_evaluation_version': report['session']['evaluation_version']})['data']
    profile = call(path + '/profile')['data']
    assert profile['active_profile'] == profile['baseline_profile']
    print(json.dumps({'ok': True, 'input_kind': 'synthetic_client_reports',
        'evaluation_id': rolled['session']['evaluation_id'], 'status': rolled['session']['status'],
        'profile_version': profile['active_profile']['version'],
        'report_url': 'http://127.0.0.1:8765' + path + '/report'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
