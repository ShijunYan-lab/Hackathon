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
        if event.type != "positions_checkpointed":
            memory_id = stable_id("mem", npc_id, event.id)
            memory = {"id": memory_id, "npc_id": npc_id, "statement": event_summary(event)[:300],
                      "source_type": "observation", "source_event_ids": [event.id],
                      "confidence": 1.0, "status": "supported"}
            if event.type in ("speech", "info_shared"):
                memory.update(source_type="report", confidence=.4, status="unverified")
            connection.execute("INSERT OR IGNORE INTO npc_memories VALUES (?, ?, ?, ?)",
                               (world_id, npc_id, memory_id, json.dumps(memory, ensure_ascii=False)))
    if event.type == "positions_checkpointed":
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


def memories(connection, world_id, npc_id):
    rows = connection.execute("SELECT body FROM npc_memories WHERE world_id=? AND npc_id=? ORDER BY rowid",
                              (world_id, npc_id)).fetchall()
    return [json.loads(row[0]) for row in rows]


def save_memory_proposals(connection, world_id, npc_id, proposals: list[MemoryProposal]):
    known = {event.id for event in known_events(connection, world_id, npc_id)}
    for proposal in proposals:
        if not set(proposal.source_event_ids) <= known:
            raise WorldError("UNKNOWN_EVIDENCE", "记忆引用了该 NPC 未知的事件。")
        # The same root sources do not become independent evidence when phrased again.
        memory_id = stable_id("mem_proposal", npc_id, proposal.source_type, sorted(set(proposal.source_event_ids)))
        body = proposal.model_dump(mode="json")
        body.update(id=memory_id, npc_id=npc_id)
        connection.execute("INSERT OR REPLACE INTO npc_memories VALUES (?, ?, ?, ?)",
                           (world_id, npc_id, memory_id, json.dumps(body, ensure_ascii=False)))


def story_view(connection, world_id, player_id=None):
    visible = None
    if player_id is not None:
        visible = set()
        for row in connection.execute("SELECT body FROM events WHERE world_id=?", (world_id,)):
            event = Event.model_validate_json(row[0])
            if player_id in event.witness_ids:
                visible.add(event.id)
    world_memories = [WorldMemory.model_validate_json(row[0]) for row in connection.execute(
        "SELECT body FROM world_memories WHERE world_id=? ORDER BY seq", (world_id,))]
    threads = [StoryThread.model_validate_json(row[0]) for row in connection.execute(
        "SELECT body FROM story_threads WHERE world_id=? ORDER BY rowid", (world_id,))]
    if visible is not None:
        world_memories = [memory for memory in world_memories if set(memory.source_event_ids) <= visible]
        threads = [thread for thread in threads if set(thread.source_event_ids) <= visible]
    return {"memories": [memory.model_dump(mode="json") for memory in world_memories],
            "story_threads": [thread.model_dump(mode="json") for thread in threads]}
