"""Real model probe with a synthetic hit; does not assert a predetermined story."""
import argparse
import json
import time
from pathlib import Path
from uuid import uuid4
from server.api.smoke import call


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--npc-follow-up', action='store_true')
    args = parser.parse_args()
    state = call('/v1/worlds', {'request_id': uuid4().hex, 'seed': 73,
                              'player_name': 'Director verification'})['data']['state']
    path = '/v1/worlds/' + state['world_id']
    player, target = state['actors'][:2]
    moved = call(path + '/commands', {'request_id': uuid4().hex,
        'expected_world_version': state['world_version'], 'kind': 'CHECKPOINT', 'payload': {
        'region_id': player['region_id'], 'positions': [{'actor_id': player['id'], 'tile': target['tile']}]}})
    state = moved['data']['state']
    player = state['actors'][0]
    hit = call(path + '/commands', {'request_id': uuid4().hex,
        'expected_world_version': state['world_version'], 'kind': 'HIT', 'payload': {
        'attack_id': uuid4().hex, 'attacker_id': player['id'], 'target_id': target['id'],
        'weapon_id': player['equipped_item_id'], 'region_id': player['region_id'],
        'attacker_tile': player['tile'], 'target_tile': target['tile']}})
    state = hit['data']['state']
    source = next(e['id'] for e in hit['data']['events'] if e['type'] == 'hit_applied')
    body = {'request_id': uuid4().hex, 'expected_world_version': state['world_version'],
            'reason': 'major_event', 'trigger_event_ids': [source]}
    start = time.monotonic()
    result = call(path + '/advance', body)
    elapsed = round(time.monotonic() - start, 2)
    assert call(path + '/advance', body) == result, 'Retry must reuse persisted model result'
    audit = call(path + '/director/debug')['data']
    report = {'world_id': state['world_id'], 'synthetic_hit': True, 'seconds': elapsed,
              'director': result['data']['director'], 'audit': audit}
    if args.npc_follow_up:
        queued = next((row for row in audit['focus'] if row['status'] == 'queued'), None)
        assert queued, 'The model chose no follow-up in this run'
        next_turn = call(path + '/advance', {'request_id': uuid4().hex,
            'expected_world_version': result['world_version'], 'reason': 'debug_step'})['data']
        planned = next(row for row in next_turn['decision_summaries'] if row['npc_id'] == queued['npc_id'])
        assert planned['mode'] == 'live' and planned['intent_status'] != 'rejected', planned
        processed = call(path + '/director/debug')['data']['focus']
        assert any(row['id'] == queued['id'] and row['status'] == 'consumed' for row in processed)
        report['npc_follow_up'] = planned
    Path('runtime/director_live_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    assert result['data']['director']['mode'] == 'live', 'Provider unavailable/rejected; inspect safe reason code'


if __name__ == '__main__':
    main()
