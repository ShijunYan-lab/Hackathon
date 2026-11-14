"""Bounded world turns; model calls never hold a database transaction."""
import asyncio
import json
from uuid import uuid4

from shared.protocol import Event, StateView
from server.storage.sqlite import response
from server.world.agent_runtime import build_context
from server.world.commands import WorldError
from server.world.director import DirectorConfig, DirectorResult, WorldDirector
from server.world.tasks import event
from server.world import economy
from server.world.director_execution import execute as execute_director
from server.world.director_context import build as build_director_context


SCHEMA = """
CREATE TABLE IF NOT EXISTS world_runtime (
    world_id TEXT PRIMARY KEY, config TEXT NOT NULL, last_director_tick INTEGER NOT NULL,
    evaluation_active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS director_runs (
    world_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, id)
);
CREATE TABLE IF NOT EXISTS director_focus (
    world_id TEXT NOT NULL, id TEXT NOT NULL, npc_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL, status TEXT NOT NULL,
    PRIMARY KEY(world_id, id)
);
CREATE INDEX IF NOT EXISTS director_focus_by_status ON director_focus(world_id, status);
"""


class WorldTurns:
    def __init__(self, agents, config, provider=None):
        self.agents, self.store = agents, agents.store
        self.config, self.provider = config, provider
        self.last_mode = "fallback"
        with self.store.connection() as connection:
            connection.executescript(SCHEMA)

    def runtime(self, connection, world_id):
        self.store.world_row(connection, world_id)
        connection.execute("INSERT OR IGNORE INTO world_runtime VALUES (?, ?, 0, 0)",
                           (world_id, self.config.model_dump_json()))
        return connection.execute("SELECT * FROM world_runtime WHERE world_id=?", (world_id,)).fetchone()

    def set_evaluation_active(self, world_id, active):
        """C evaluation lifecycle seam. No public client override."""
        with self.store.connection(write=True) as connection:
            self.runtime(connection, world_id)
            connection.execute("UPDATE world_runtime SET evaluation_active=? WHERE world_id=?",
                               (int(active), world_id))

    def debug(self, world_id, limit=20):
        with self.store.connection() as connection:
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)["state"])
            runs = [json.loads(row[0]) for row in connection.execute(
                "SELECT body FROM director_runs WHERE world_id=? ORDER BY rowid DESC LIMIT ?", (world_id, limit))]
            runs.reverse()
            focus = [dict(row) for row in connection.execute(
                """SELECT * FROM director_focus WHERE world_id=?
                    ORDER BY (status='queued') DESC, rowid DESC LIMIT ?""", (world_id, limit))]
            return response("director_debug", state, {"runs": runs, "focus": focus})

    async def advance(self, world_id, body):
        scope = world_id + "/advance"
        with self.store.connection(write=True) as connection:
            cached, token = self.agents.reserve(connection, scope, body)
            if cached is not None:
                return cached
            state, region = self.agents.ensure_current(connection, world_id, body, scope, token)
            runtime = self.runtime(connection, world_id)
            if runtime["evaluation_active"]:
                raise WorldError("EVALUATION_FROZEN", "评审世界暂停普通世界推进。", 409)
            seq = connection.execute("SELECT MAX(seq) FROM events WHERE world_id=?", (world_id,)).fetchone()[0] + 1
            triggers = set(body.trigger_event_ids)
            if any(connection.execute("SELECT 1 FROM events WHERE world_id=? AND id=?", (world_id, source)).fetchone() is None
                   for source in triggers):
                raise WorldError("UNKNOWN_EVENT", "触发事件不属于当前世界。")
            config = DirectorConfig.model_validate_json(runtime["config"])
            state.tick += 1
            major_event = body.reason == "major_event" and bool(triggers)
            due = config.enabled and (major_event or state.tick - runtime["last_director_tick"] >= config.interval_ticks)
            director_context = build_director_context(connection, state, config, triggers) if due and self.provider else None
            eligible = sorted((actor for actor in state.actors if actor.kind == "npc"
                               and actor.alive and not actor.task_id and actor.behavior != "attacking"),
                              key=lambda actor: actor.id)
            focus = connection.execute("SELECT * FROM director_focus WHERE world_id=? AND status='queued' ORDER BY rowid",
                                       (world_id,)).fetchall()
            chosen_focus = next((row for row in focus if row["npc_id"] in {actor.id for actor in eligible}), None)
            npc_id = chosen_focus["npc_id"] if chosen_focus else (
                eligible[(state.tick - 1) % len(eligible)].id if eligible else None)
            trigger_ids = list(body.trigger_event_ids)
            if chosen_focus:
                row = connection.execute('SELECT body FROM events WHERE world_id=? AND id=?',
                                         (world_id, chosen_focus['source_event_id'])).fetchone()
                trigger_ids.extend(Event.model_validate_json(row[0]).caused_by)
            trigger_ids = list(dict.fromkeys(trigger_ids))
            context = build_context(connection, state, npc_id, trigger_ids=trigger_ids) if npc_id else None
            triggers = [value for value in trigger_ids
                        if context and value in {entry.id for entry in context.known_events}]
        try:
            async def plan():
                if context is None:
                    return None, "fallback"
                return await self.agents.gateway.call("plan", context, triggers)
            director = WorldDirector(config, self.provider)
            async def assess():
                if director_context is None:
                    reason = 'DISABLED' if not config.enabled else 'PROVIDER_NOT_CONFIGURED' if due else 'NOT_DUE'
                    return DirectorResult(world_id=world_id, expected_world_version=body.expected_world_version,
                        mode='fallback', status='unavailable' if due else 'skipped', reason_code=reason)
                async with self.agents.gateway.semaphore:
                    return await director.assess(director_context,
                        last_assessed_tick=runtime["last_director_tick"],
                        major_event=major_event)
            async def assess_with_budget():
                try:
                    return await asyncio.wait_for(assess(), timeout=10)
                except asyncio.TimeoutError:
                    return DirectorResult(world_id=world_id, expected_world_version=body.expected_world_version,
                        mode="fallback", status="unavailable", reason_code="REQUEST_BUDGET_EXHAUSTED")

            (decision, mode), result = await asyncio.gather(plan(), assess_with_budget())
            if result.status != "skipped":
                self.last_mode = result.mode
            with self.store.connection(write=True) as connection:
                state, region = self.agents.ensure_current(connection, world_id, body, scope, token)
                if self.runtime(connection, world_id)["evaluation_active"]:
                    raise WorldError("EVALUATION_FROZEN", "评审已开始，普通推进已取消。", 409)
                state.tick += 1
                emitted, task_ids, summaries = [], [], []
                if decision is not None and mode == "live":
                    state, planned, task_ids, intent_status = self.agents.apply_decision(
                        connection, state, context, decision, mode, region, seq, triggers)
                    emitted.extend(planned)
                    summaries.append({"npc_id": npc_id, "mode": mode, "intent_status": intent_status,
                                      "task_ids": task_ids})
                elif decision is not None:
                    summaries.append({"npc_id": npc_id, "mode": mode, "intent_status": "none", "task_ids": []})
                if chosen_focus and mode == "live":
                    connection.execute("UPDATE director_focus SET status='consumed' WHERE world_id=? AND id=?",
                                       (world_id, chosen_focus["id"]))
                    emitted.append(event(state, "director_follow_up_processed", seq + len(emitted),
                        None, npc_id, {"focus_id": chosen_focus["id"], "meaning": "planning_attempted"},
                        [chosen_focus["source_event_id"], *[value.id for value in emitted]], []))
                # Dead targets cannot leave an immortal queue entry.
                alive_ids = {actor.id for actor in state.actors if actor.alive}
                for pending in focus:
                    if pending["npc_id"] not in alive_ids:
                        connection.execute("UPDATE director_focus SET status='cancelled' WHERE world_id=? AND id=?",
                                           (world_id, pending["id"]))
                        emitted.append(event(state, "director_follow_up_cancelled", seq + len(emitted),
                            None, pending["npc_id"], {"focus_id": pending["id"], "reason": "ACTOR_DEAD"},
                            [pending["source_event_id"]], []))
                applied = []
                if result.status != "skipped":
                    emitted.append(event(state, "director_assessed", seq + len(emitted), None, None,
                        {"mode": result.mode, "status": result.status, "reason_code": result.reason_code,
                         "source_type": "interpretation",
                         "summary": result.decision.summary if result.decision else ""},
                        result.decision.source_event_ids if result.decision else [], []))
                if result.decision:
                    for proposal in result.decision.proposals:
                        if proposal.kind != 'FOLLOW_UP':
                            state, outcome, accepted = execute_director(connection, state, proposal,
                                config, region, seq + len(emitted))
                            emitted.append(outcome)
                            applied.append({'event_id': outcome.id, 'accepted': accepted})
                            continue
                        # Only living NPC targets have an enabled follow-up executor in this milestone.
                        target = next((actor for actor in state.actors if actor.id == proposal.target_id
                                       and actor.alive and actor.kind == "npc"), None)
                        duplicate = connection.execute(
                            "SELECT 1 FROM director_focus WHERE world_id=? AND npc_id=? AND status='queued'",
                            (world_id, proposal.target_id)).fetchone()
                        accepted = target is not None and duplicate is None
                        focus_id = "focus_" + uuid4().hex
                        outcome = event(state, "director_follow_up_queued" if accepted else "director_proposal_rejected",
                            seq + len(emitted), None, proposal.target_id,
                            {"focus_id": focus_id, "kind": proposal.kind, "reason_summary": proposal.reason_summary,
                             "execution_status": "queued" if accepted else "unsupported_target_or_already_queued"},
                            proposal.source_event_ids, [])
                        emitted.append(outcome)
                        if accepted:
                            connection.execute("INSERT INTO director_focus VALUES (?, ?, ?, ?, 'queued')",
                                               (world_id, focus_id, target.id, outcome.id))
                        applied.append({"event_id": outcome.id, "accepted": accepted})
                if result.status != "skipped":
                    connection.execute("UPDATE world_runtime SET last_director_tick=? WHERE world_id=?",
                                       (state.tick, world_id))
                    record = {"tick": state.tick, "result": result.model_dump(mode="json"), "executions": applied}
                    connection.execute("INSERT INTO director_runs VALUES (?, ?, ?)",
                                       (world_id, "director_" + uuid4().hex, json.dumps(record, ensure_ascii=False)))
                emitted.append(event(state, "world_advanced", seq + len(emitted), None, None,
                    {"reason": body.reason, "director_status": result.status}, body.trigger_event_ids, []))
                economy.reconcile(connection, state, emitted)
                state.world_version += 1
                state = StateView.model_validate(state.model_dump())
                connection.execute("UPDATE worlds SET state=? WHERE id=?", (state.model_dump_json(), world_id))
                for value in emitted:
                    self.store.append_event(connection, world_id, value)
                output = response(body.request_id, state, {"tick": state.tick,
                    "decision_summaries": summaries,
                    "tasks": [task.model_dump(mode="json") for task in state.tasks if task.id in task_ids],
                    "events": [value.model_dump(mode="json") for value in emitted if state.player_id in value.witness_ids],
                    "director": {"mode": result.mode, "status": result.status, "reason_code": result.reason_code,
                                 "accepted_proposals": sum(entry["accepted"] for entry in applied)},
                    "state": state.model_dump(mode="json")})
                self.store.remember(connection, scope, body, output)
                return output
        finally:
            self.agents.release(scope, body.request_id, token)
