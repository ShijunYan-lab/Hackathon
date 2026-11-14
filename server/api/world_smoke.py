"""Real HTTP smoke for milestones 05--08; synthetic client positions, no mock world."""
import json
from pathlib import Path
from uuid import uuid4

from server.api.smoke import BASE_URL, call


def main():
    state = call('/v1/worlds', {'request_id': uuid4().hex, 'seed': 42,
                              'player_name': 'C demo'})['data']['state']
    path = '/v1/worlds/' + state['world_id']
    npc_id = state['actors'][1]['id']
    weapon_id = state['actors'][1]['equipped_item_id']

    def command(kind, payload):
        nonlocal state
        body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
                'kind': kind, 'payload': payload}
        result = call(path + '/commands', body)
        assert call(path + '/commands', body) == result
        state = result['data']['state']

    command('CHECKPOINT', {'region_id': state['current_region_id'], 'positions': [
        {'actor_id': npc_id, 'tile': state['actors'][0]['tile']}]})
    command('GIVE', {'actor_id': npc_id, 'target_id': state['player_id'], 'item_id': weapon_id})
    command('EQUIP', {'actor_id': state['player_id'], 'item_id': weapon_id})
    assert state['actors'][0]['equipped_item_id'] == weapon_id
    assert next(item for item in state['items'] if item['id'] == weapon_id)['owner_id'] == state['player_id']
    body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
            'npc_id': npc_id, 'text': 'Hello'}
    result = call(path + '/dialogue', body)
    assert call(path + '/dialogue', body) == result
    state = result['data']['state']
    dialogue_mode = result['data']['mode']
    for _ in range(3):
        body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
                'reason': 'debug_step', 'trigger_event_ids': []}
        result = call(path + '/advance', body)
        assert call(path + '/advance', body) == result
        state = result['data']['state']
    assert state['tick'] == 3
    assert call(path + '/story')['data']['memories']
    assert call(path + '/state')['data']['state'] == state
    artifact = Path('runtime/world_demo.json')
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps({'state': state, 'advance_request': body, 'advance_response': result},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'world_id': state['world_id'], 'tick': state['tick'],
        'dialogue_mode': dialogue_mode, 'director': result['data']['director'],
        'state_url': BASE_URL + path + '/state',
        'story_url': BASE_URL + path + '/story'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
