"""Player-visible chapters backed by the branch event ledger."""
import json
from uuid import uuid4

from pydantic import Field
from shared.protocol import DTO, Event


SCHEMA = """
CREATE TABLE IF NOT EXISTS story_chapters (
    world_id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, seq)
);
"""
# Speech is evidence of what was said, never proof that a promise was fulfilled.
TURNING_POINTS = (
    'hit_applied', 'actor_died', 'player_downed', 'task_succeeded', 'task_failed',
    'resource_gathered', 'resource_need_fulfilled', 'offer_accepted', 'npc_migrated', 'content_created',
)


class ChapterDraft(DTO):
    title: str = Field(min_length=1, max_length=60)
    narrative: str = Field(min_length=1, max_length=600)
    open_question: str = Field(default='', max_length=160)
    source_event_ids: list[str] = Field(min_length=1, max_length=12)


def read(connection, world_id, after_seq, limit, *, latest=False):
    order = 'DESC' if latest else 'ASC'
    rows = connection.execute(f"""SELECT body FROM story_chapters WHERE world_id=? AND seq>?
        ORDER BY seq {order} LIMIT ?""", (world_id, after_seq, limit))
    return [json.loads(row[0]) for row in rows]


def candidates(connection, state):
    rows = connection.execute("""SELECT body FROM events WHERE world_id=?
        AND seq > COALESCE((SELECT MAX(seq) FROM story_chapters WHERE world_id=?), 0)
        AND (json_extract(body, '$.type') IN (SELECT value FROM json_each(?))
             OR (json_extract(body, '$.type') IN ('speech', 'npc_speech')
                 AND length(trim(json_extract(body, '$.facts.text'))) > 0
                 AND (json_extract(body, '$.actor_id')=? OR json_extract(body, '$.target_id')=?)))
        AND EXISTS (SELECT 1 FROM json_each(events.body, '$.witness_ids') WHERE value=?)
        ORDER BY seq LIMIT 12""",
        (state.world_id, state.world_id, json.dumps(TURNING_POINTS),
         state.player_id, state.player_id, state.player_id))
    return [Event.model_validate_json(row[0]) for row in rows]


def recall(connection, world_id, entity_ids):
    rows = connection.execute("""SELECT body FROM story_chapters WHERE world_id=?
        ORDER BY EXISTS (SELECT 1 FROM json_each(story_chapters.body, '$.entity_ids') entity
                         WHERE entity.value IN (SELECT value FROM json_each(?))) DESC,
                 json_extract(body, '$.significance') DESC, seq DESC LIMIT 5""",
        (world_id, json.dumps(sorted(entity_ids))))
    recent = [json.loads(row[0]) for row in rows]
    first = read(connection, world_id, 0, 1)
    return first + [record for record in recent if not first or record['id'] != first[0]['id']]


def record(connection, state, evidence, draft):
    sources = {event.id: event for event in evidence}
    if not sources or set(draft.source_event_ids) != sources.keys():
        return None
    seq = max(event.event_seq for event in evidence)
    entities = sorted({actor for event in evidence for actor in (event.actor_id, event.target_id) if actor})
    chapter = {**draft.model_dump(mode='json'), 'id': 'chapter_' + uuid4().hex,
               'through_event_seq': seq, 'entity_ids': entities, 'mode': 'live',
               'significance': 2 if any(event.type == 'actor_died' for event in evidence) else 1}
    connection.execute('INSERT INTO story_chapters VALUES (?, ?, ?)',
                       (state.world_id, seq, json.dumps(chapter, ensure_ascii=False)))
    return chapter
