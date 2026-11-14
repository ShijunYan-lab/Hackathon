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
# Speech alone can be a promise or a rumor. Save its realized consequences instead.
TURNING_POINTS = (
    'hit_applied', 'actor_died', 'player_downed', 'task_succeeded', 'task_failed',
    'resource_gathered', 'resource_need_fulfilled', 'offer_accepted', 'npc_migrated',
    'quest_completed', 'quest_failed', 'shop_purchase', 'container_item_taken', 'price_negotiated',
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
        AND json_extract(body, '$.type') IN (SELECT value FROM json_each(?))
        AND EXISTS (SELECT 1 FROM json_each(events.body, '$.witness_ids') WHERE value=?)
        ORDER BY seq LIMIT 12""",
        (state.world_id, state.world_id, json.dumps(TURNING_POINTS), state.player_id))
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


def record(connection, state, evidence, draft, mode='live'):
    sources = {event.id: event for event in evidence}
    if not sources or set(draft.source_event_ids) != sources.keys():
        return None
    seq = max(event.event_seq for event in evidence)
    entities = sorted({actor for event in evidence for actor in (event.actor_id, event.target_id) if actor})
    chapter = {**draft.model_dump(mode='json'), 'id': 'chapter_' + uuid4().hex,
               'through_event_seq': seq, 'entity_ids': entities, 'mode': mode,
               'significance': 2 if any(event.type == 'actor_died' for event in evidence) else 1}
    connection.execute('INSERT INTO story_chapters VALUES (?, ?, ?)',
                       (state.world_id, seq, json.dumps(chapter, ensure_ascii=False)))
    return chapter


def factual_draft(evidence):
    """Deterministic ledger summary. Never pretends to be model-written prose."""
    if not evidence:return None
    from server.world.living_world import EVENT_LABELS
    lines=[]
    for value in evidence:
        caption=EVENT_LABELS.get(value.type,value.type)
        detail=value.facts.get('title') or value.facts.get('item_name') or ''
        lines.append(f"[{value.tick}] {caption} {detail}".strip())
    return ChapterDraft(title='\u65c5\u9014\u8bb0\u5f55',narrative='\n'.join(lines)[:600],source_event_ids=[v.id for v in evidence])
