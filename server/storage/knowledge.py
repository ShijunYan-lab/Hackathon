"""Branch-scoped event visibility, memories and factual story records."""
import json
from uuid import NAMESPACE_URL, uuid5

from shared.protocol import Event, MemoryProposal, StateView
from server.world.commands import WorldError
from server.world.director import StoryThread, WorldMemory


SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_index (
    world_id TEXT NOT NULL, event_id TEXT NOT NULL,
    PRIMARY KEY(world_id, event_id)
);
CREATE TABLE IF NOT EXISTS event_knowledge (
    world_id TEXT NOT NULL, npc_id TEXT NOT NULL, event_id TEXT NOT NULL,
    source_type TEXT NOT NULL, PRIMARY KEY(world_id, npc_id, event_id)
);
CREATE TABLE IF NOT EXISTS npc_memories (
    world_id TEXT NOT NULL, npc_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, npc_id, id)
);
CREATE INDEX IF NOT EXISTS npc_memories_by_actor ON npc_memories(world_id, npc_id);
CREATE TABLE IF NOT EXISTS world_memories (
    world_id TEXT NOT NULL, id TEXT NOT NULL, seq INTEGER NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, id)
);
CREATE TABLE IF NOT EXISTS story_threads (
    world_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, id)
);
"""


def stable_id(prefix, *values):
    return prefix + "_" + uuid5(NAMESPACE_URL, json.dumps(values, ensure_ascii=False)).hex


def event_summary(event):
    # Structured factual wording keeps a speech claim distinguishable from an observed action.
    return f"事件 {event.type}；角色 {event.actor_id}；对象 {event.target_id}；记录 {json.dumps(event.facts, ensure_ascii=False)}"[:1000]


def record_event(connection, world_id, event: Event):
    indexed = connection.execute("INSERT OR IGNORE INTO knowledge_index VALUES (?, ?)",
                                 (world_id, event.id)).rowcount
    if not indexed:
        return
    for source in event.caused_by:
        row = connection.execute("SELECT seq FROM events WHERE world_id=? AND id=?", (world_id, source)).fetchone()
        if row is None or row[0] >= event.event_seq:
            raise WorldError("INVALID_EVENT_SOURCE", "事件来源必须属于本世界且先于当前事件。")
    state = StateView.model_validate_json(connection.execute("SELECT state FROM worlds WHERE id=?", (world_id,)).fetchone()[0])
    npc_ids = {actor.id for actor in state.actors if actor.kind == "npc"}
    for npc_id in set(event.witness_ids) & npc_ids:
        connection.execute("INSERT OR IGNORE INTO event_knowledge VALUES (?, ?, ?, 'observation')",
                           (world_id, npc_id, event.id))
        if event.type not in {"positions_checkpointed", "decision_accepted"}:
            memory_id = stable_id("mem", npc_id, event.id)
            memory = {"id": memory_id, "npc_id": npc_id, "statement": event_summary(event)[:300],
                      "source_type": "observation", "source_event_ids": [event.id],
                      "confidence": 1.0, "status": "supported"}
            if event.type in ("speech", "npc_speech", "info_shared"):
                memory.update(source_type="report", confidence=.4, status="unverified")
            connection.execute("INSERT OR IGNORE INTO npc_memories VALUES (?, ?, ?, ?)",
                               (world_id, npc_id, memory_id, json.dumps(memory, ensure_ascii=False)))
    if event.type in {"positions_checkpointed", "decision_accepted", "world_advanced", "director_assessed"}:
        return
    memory = WorldMemory(id=stable_id("world_mem", event.id), summary=event_summary(event),
                         source_event_ids=[event.id], through_event_seq=event.event_seq)
    inserted = connection.execute("INSERT OR IGNORE INTO world_memories VALUES (?, ?, ?, ?)",
                                  (world_id, memory.id, event.event_seq, memory.model_dump_json())).rowcount
    if not inserted:
        return
    if event.type in ("hit_applied", "actor_died"):
        thread_id = stable_id("thread", "danger", event.target_id)
        topic = f"角色 {event.target_id} 遭遇攻击"
        status = "abandoned" if event.type == "actor_died" else "open"
    elif event.type in ("task_scheduled", "task_succeeded", "task_failed", "task_cancelled"):
        thread_id = stable_id("thread", "task", event.facts["task_id"])
        topic = f"任务 {event.facts['task_id']}"
        status = {"task_scheduled": "open", "task_succeeded": "resolved"}.get(event.type, "abandoned")
    elif event.type in ('resource_need_created', 'resource_need_supplied', 'resource_need_fulfilled'):
        thread_id = stable_id('thread', 'resource_need', event.facts['org_id'])
        topic = f"组织 {event.facts['org_id']} 的 {event.facts['resource']} 补给需求"
        status = 'resolved' if event.type == 'resource_need_fulfilled' else 'open'
    else:
        return
    previous = connection.execute("SELECT body FROM story_threads WHERE world_id=? AND id=?",
                                  (world_id, thread_id)).fetchone()
    sources = [] if previous is None else json.loads(previous[0])["source_event_ids"]
    thread = StoryThread(id=thread_id, topic=topic, status=status,
                         entity_ids=list(dict.fromkeys(value for value in (event.actor_id, event.target_id) if value)),
                         source_event_ids=list(dict.fromkeys([*sources, event.id])))
    connection.execute("INSERT OR REPLACE INTO story_threads VALUES (?, ?, ?)",
                       (world_id, thread.id, thread.model_dump_json()))


def known_events(connection, world_id, npc_id):
    rows = connection.execute("""SELECT e.body FROM events e JOIN event_knowledge k
        ON e.world_id=k.world_id AND e.id=k.event_id
        WHERE k.world_id=? AND k.npc_id=? ORDER BY e.seq""", (world_id, npc_id)).fetchall()
    return [Event.model_validate_json(row[0]) for row in rows]


def memories(connection, world_id, npc_id, limit=-1):
    rows = connection.execute("""SELECT body FROM npc_memories WHERE world_id=? AND npc_id=?
        ORDER BY rowid DESC LIMIT ?""", (world_id, npc_id, limit)).fetchall()
    return [json.loads(row[0]) for row in reversed(rows)]


def knows_event(connection, world_id, npc_id, event_id):
    return connection.execute("""SELECT 1 FROM event_knowledge
        WHERE world_id=? AND npc_id=? AND event_id=?""", (world_id, npc_id, event_id)).fetchone() is not None


def planning_events(connection, world_id, npc_id, sources):
    recent = connection.execute("""SELECT e.body FROM events e JOIN event_knowledge k
        ON e.world_id=k.world_id AND e.id=k.event_id
        WHERE k.world_id=? AND k.npc_id=? AND json_extract(e.body, '$.type') NOT IN ('positions_checkpointed', 'decision_accepted')
        ORDER BY e.seq DESC LIMIT 8""", (world_id, npc_id))
    selected = {entry.id: entry for entry in (Event.model_validate_json(row[0]) for row in recent)}
    for source in sources - selected.keys():
        if knows_event(connection, world_id, npc_id, source):
            row = connection.execute('SELECT body FROM events WHERE world_id=? AND id=?',
                                     (world_id, source)).fetchone()
            selected[source] = Event.model_validate_json(row[0])
    return sorted(selected.values(), key=lambda event: event.event_seq)


def save_memory_proposals(connection, world_id, npc_id, proposals: list[MemoryProposal]):
    for proposal in proposals:
        if any(not knows_event(connection, world_id, npc_id, source) for source in proposal.source_event_ids):
            raise WorldError("UNKNOWN_EVIDENCE", "记忆引用了该 NPC 未知的事件。")
        # The same root sources do not become independent evidence when phrased again.
        memory_id = stable_id("mem_proposal", npc_id, proposal.source_type, sorted(set(proposal.source_event_ids)))
        body = proposal.model_dump(mode="json")
        body.update(id=memory_id, npc_id=npc_id)
        connection.execute("INSERT OR REPLACE INTO npc_memories VALUES (?, ?, ?, ?)",
                           (world_id, npc_id, memory_id, json.dumps(body, ensure_ascii=False)))


def story_view(connection, world_id, player_id=None, limit=50):
    def recent(table, order):
        where = ""
        params = [world_id]
        if player_id is not None:
            where = """ AND NOT EXISTS (
                SELECT 1 FROM json_each(record.body, '$.source_event_ids') AS source
                WHERE NOT EXISTS (SELECT 1 FROM events e, json_each(e.body, '$.witness_ids') AS witness
                    WHERE e.world_id=record.world_id AND e.id=source.value AND witness.value=?))"""
            params.append(player_id)
        rows = connection.execute(
            f"SELECT record.body FROM {table} record WHERE record.world_id=?{where} ORDER BY {order} DESC LIMIT ?",
            (*params, limit)).fetchall()
        return [json.loads(row[0]) for row in reversed(rows)]

    return {"memories": recent("world_memories", "seq"), "story_threads": recent("story_threads", "rowid")}
