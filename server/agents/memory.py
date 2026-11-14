"""Bounded retrieval from the NPC's C-provided knowledge."""
from shared.protocol import AgentContext, MemoryProposal


def owned_memories(context: AgentContext):
    return [
        memory for memory in context.memories
        if memory.get("npc_id", context.npc_id) == context.npc_id
        and isinstance(memory.get("id"), str)
        and isinstance(memory.get("policy_version", 0), int)
        and memory.get("policy_version", 0) <= context.policy_version
    ]


def retrieve(context: AgentContext, event_ids=(), text: str = ""):
    memories = owned_memories(context)
    recent = memories[-8:]
    selected = set(event_ids)
    entities = [
        str(entity["id"]) for entity in context.known_entities
        if entity.get("id") and entity.get("name") and str(entity["name"]) in text
    ]
    related = [
        memory for memory in memories[:-8]
        if selected.intersection(memory.get("source_event_ids") or [])
        or any(entity in (memory.get("entity_ids") or []) for entity in entities)
    ]
    return [*recent, *related[-4:]]


def _source_roots(source_ids, known_events):
    """Deduplicate a rumour by its original evidence rather than relay event IDs."""
    roots = set()
    for source_id in source_ids:
        # Resolve chains when C supplies the visible event ancestry.
        frontier = [source_id]
        visited = set()
        while frontier:
            current = frontier.pop()
            if current in visited:
                continue
            visited.add(current)
            event = known_events.get(current)
            origins = (event.facts.get("source_event_ids") or []) if event else []
            if origins and all(isinstance(item, str) for item in origins):
                frontier.extend(origins)
            else:
                roots.add(current)
    return frozenset(roots)


def validate_proposals(context: AgentContext, proposals: list[MemoryProposal], events):
    known_events = {event.id: event for event in context.known_events}
    known_events.update(events)
    seen = {
        (str(memory.get("statement", "")).strip(),
         _source_roots(memory.get("source_event_ids") or [], known_events))
        for memory in owned_memories(context)
    }
    normalized = []
    for proposal in proposals:
        sources = set(proposal.source_event_ids)
        if not sources <= events.keys():
            raise ValueError("记忆引用了未提供的事件")
        # A relay of the same root source is not independent evidence.
        roots = _source_roots(sources, known_events)
        key = (proposal.statement.strip(), roots)
        if key in seen:
            continue
        seen.add(key)
        seen.add((proposal.statement.strip(), frozenset(sources)))
        update = {"source_event_ids": list(dict.fromkeys(proposal.source_event_ids))}
        if any(
            events[source].facts.get("source_type") == "report"
            or events[source].type.lower() in {"report", "rumor", "rumour", "speech", "conversation", "share_info", "dialogue"}
            or context.npc_id not in {
                events[source].actor_id, events[source].target_id, *events[source].witness_ids
            }
            for source in sources
        ):
            update.update(source_type="report", status="unverified", confidence=min(proposal.confidence, .5))
        elif proposal.source_type != "observation":
            update.update(status="unverified", confidence=min(proposal.confidence, .5))
        normalized.append(proposal.model_copy(update=update))
    return normalized
