"""Select recent evidence and unresolved threads without inventing compressed facts."""
import json
from server.world.director import DirectorContext
from shared.protocol import Event


def build(connection, state, config, triggers):
    world_id = state.world_id
    recent = connection.execute("""SELECT id FROM events WHERE world_id=?
        AND json_extract(body, '$.type') NOT IN ('positions_checkpointed', 'decision_accepted', 'world_advanced', 'director_assessed')
        ORDER BY seq DESC LIMIT ?""", (world_id, config.event_budget))
    selected = triggers | {row[0] for row in recent}
    # Open problems survive the recent-event window. Keep source lists intact or skip the record.
    threads = connection.execute("""SELECT body FROM story_threads WHERE world_id=?
        ORDER BY (json_extract(body, '$.status') = 'open') DESC, rowid DESC LIMIT ?""",
        (world_id, config.thread_budget))
    kept_threads, kept_memories = [], []
    ceiling = config.event_budget * 2
    for row in threads:
        record = json.loads(row[0])
        sources = set(record['source_event_ids'])
        if len(selected | sources) <= ceiling:
            selected.update(sources)
            kept_threads.append(record)
    memories = connection.execute("""SELECT m.body FROM world_memories m
        JOIN events e ON e.world_id=m.world_id AND e.seq=m.seq
        WHERE m.world_id=? AND json_extract(e.body, '$.type') NOT IN
            ('positions_checkpointed', 'decision_accepted', 'world_advanced', 'director_assessed')
        ORDER BY m.seq DESC LIMIT ?""", (world_id, config.memory_budget))
    for row in memories:
        record = json.loads(row[0])
        sources = set(record['source_event_ids'])
        if len(selected | sources) <= ceiling:
            selected.update(sources)
            kept_memories.append(record)
    needs = [json.loads(row[0]) for row in connection.execute(
        'SELECT body FROM resource_needs WHERE world_id=?', (state.world_id,))]
    kept_needs = []
    for need in sorted(needs, key=lambda value: value['status'] == 'open', reverse=True):
        sources = set(need['source_event_ids'])
        if len(selected | sources) <= ceiling:
            selected.update(sources)
            kept_needs.append(need)
    events = sorted((Event.model_validate_json(connection.execute(
        'SELECT body FROM events WHERE world_id=? AND id=?', (world_id, source)).fetchone()[0])
        for source in selected), key=lambda entry: entry.event_seq)
    return DirectorContext(state=state, events=events,
        memories=list(reversed(kept_memories)), story_threads=kept_threads, resource_needs=kept_needs,
        locations=config.locations, history_scope='Selected recent events plus source-linked memories and unresolved threads; omitted history is not evidence of absence.',
        execution_rules={'max_proposals': config.max_proposals, 'resource_limits': config.resource_limits,
            'npc_alive_limit': config.npc_alive_limit,
            'FOLLOW_UP': 'Only a living NPC target can be queued for planning; this does not execute its actions.',
            'RESOURCE_NEED': 'One open need per active organization. quantity means desired stock, not free resources.',
            'MIGRATION': 'Requires an unused NPC death or unresolved resource_need_created event and a configured migration_entry. Never revive old identities.'},
        allowed_proposals=['FOLLOW_UP', 'RESOURCE_NEED', 'MIGRATION'])
