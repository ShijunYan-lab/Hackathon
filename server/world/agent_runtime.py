"""C-owned orchestration around B's optional asynchronous agent functions."""
from __future__ import annotations

import asyncio
import importlib
import json
import math
import time
from uuid import uuid4

from shared.protocol import AgentContext, AgentDecision, Event, StateView
from server.storage import knowledge
from server.storage.sqlite import response
from server.world.commands import WorldError
from server.world.items import living_actor, require_near
from server.world.tasks import apply_intent, event, reachable


SCHEMA = """
CREATE TABLE IF NOT EXISTS npc_profiles (
    world_id TEXT NOT NULL, npc_id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, npc_id)
);
CREATE TABLE IF NOT EXISTS decisions (
    world_id TEXT NOT NULL, id TEXT NOT NULL, npc_id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, id)
);
CREATE TABLE IF NOT EXISTS agent_requests (
    scope TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    token TEXT NOT NULL, started_at REAL NOT NULL, PRIMARY KEY(scope, id)
);
CREATE TABLE IF NOT EXISTS npc_dialogue_turns (
    world_id TEXT NOT NULL, npc_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, npc_id, id)
);
"""


class AgentGateway:
    def __init__(self, dialogue=None, plan=None, timeout_s=8, integration_model=None):
        self.integration_model = integration_model
        self.dialogue_provider = dialogue
        self.plan_provider = plan
        self.timeout_s = timeout_s
        if not 0 < timeout_s <= 65:
            raise ValueError("Agent timeout must be greater than zero and at most 65 seconds")
        self.semaphore = asyncio.Semaphore(2)
        self.last_mode = "fallback"

    async def call(self, kind, context, argument):
        provider = getattr(self, kind + "_provider")
        if provider is None:
            try:
                provider = getattr(importlib.import_module("server.agents.service"), kind)
            except (ImportError, AttributeError):
                if self.integration_model is None:
                    self.last_mode = "fallback"
                    return AgentDecision(reply="当前模型未接入，我会暂时等待。", intent={"action": "WAIT"}), "fallback"
                provider = getattr(self.integration_model, 'npc_' + kind)
        if len(context.model_dump_json().encode('utf-8')) > 96 * 1024:
            self.last_mode = "fallback"
            return AgentDecision(reply="当前信息超过处理预算，我会暂时等待。", intent={"action": "WAIT"}), "fallback"
        async def invoke():
            async with self.semaphore:
                raw = await provider(context.model_copy(deep=True), argument)
                return AgentDecision.model_validate(raw.model_dump() if isinstance(raw, AgentDecision) else raw)
        try:
            decision = await asyncio.wait_for(invoke(), timeout=self.timeout_s)
            self.last_mode = "live"
            return decision, "live"
        except Exception:
            self.last_mode = "fallback"
            return AgentDecision(reply="暂时无法作出新决定，我会等待。", intent={"action": "WAIT"}), "fallback"


def profile(connection, world_id, npc_id):
    row = connection.execute("SELECT body FROM npc_profiles WHERE world_id=? AND npc_id=?",
                             (world_id, npc_id)).fetchone()
    return json.loads(row[0]) if row else {"policy": {"caution": .5}, "version": 0, "history": [], "goals": []}


def build_context(connection, state, npc_id, extra_events=(), trigger_ids=()):
    npc = living_actor(state, npc_id)
    if npc.kind != "npc":
        raise WorldError("NPC_NOT_FOUND", "该角色不是 NPC。", 404)
    stored = profile(connection, state.world_id, npc_id)
    region_row = connection.execute("SELECT region FROM worlds WHERE id=?", (state.world_id,)).fetchone()
    region = json.loads(region_row[0]) if region_row else {}
    templates = region.get("npc_spawns", [])
    template = next((value for value in templates if value.get("appearance_key") == npc.appearance_key), {})
    recent_dialogue = [json.loads(row[0]) for row in connection.execute(
        "SELECT body FROM npc_dialogue_turns WHERE world_id=? AND npc_id=? ORDER BY rowid DESC LIMIT 8",
        (state.world_id, npc_id))][::-1]
    selected_memories, sources = [], set()
    for memory in reversed(knowledge.memories(connection, state.world_id, npc_id, limit=12)):
        candidate = sources | set(memory['source_event_ids'])
        if len(candidate) <= 24:
            sources = candidate
            selected_memories.append(memory)
    selected_memories.reverse()
    known = knowledge.planning_events(connection, state.world_id, npc_id, sources | set(trigger_ids))
    entities = [value.model_dump(mode="json") for value in [*state.actors, *state.sites]
                if value.region_id == npc.region_id and math.hypot(
                    value.tile.x - npc.tile.x, value.tile.y - npc.tile.y) <= 6]
    visible_ids = {value['id'] for value in entities}
    entities.extend(org.model_dump(mode='json') for org in state.organizations
                    if org.id in npc.org_ids or org.representative_id in visible_ids)
    invitations = {row[0] for row in connection.execute("""SELECT json_extract(e.body, '$.facts.org_id')
        FROM migration_sources m JOIN events e ON e.world_id=m.world_id AND e.id=m.event_id
        WHERE m.world_id=? AND m.npc_id=? AND json_extract(e.body, '$.type')='resource_need_created'""",
        (state.world_id, npc_id))}
    for row in connection.execute('SELECT body FROM resource_needs WHERE world_id=?', (state.world_id,)):
        demand = json.loads(row[0])
        if demand['status'] == 'open' and (any(knowledge.knows_event(connection, state.world_id, npc_id, source) for source in demand['source_event_ids']) or demand['org_id'] in invitations):
            entities.append({'id': 'need:' + demand['org_id'], 'kind': 'resource_need', **demand})
    for row in connection.execute('SELECT body FROM offers WHERE world_id=?', (state.world_id,)):
        value = json.loads(row[0])
        if npc_id in (value['actor_id'], value['target_id']) and value['status'] == 'pending' and value['expires_tick'] > state.tick:
            entities.append(value)
    # B only selects actions with C-provided parameters. Offer actual reachable
    # local destinations rather than asking B to invent coordinates or IDs.
    candidates = []
    if region.get('reactive_npcs') and not npc.task_id:
        for target in [*state.actors, *state.sites]:
            if target.id == npc.id or target.id not in visible_ids or not getattr(target, 'alive', True):
                continue
            if not reachable(region, npc.tile, target.tile):
                continue
            distance = math.hypot(target.tile.x-npc.tile.x, target.tile.y-npc.tile.y)
            if distance > .75:
                candidates.append({'action':'MOVE','target_id':target.id,'params':{},
                    'description':'走到身边停下；实际到达后才能报告完成。'})
            if getattr(target, 'remaining', 0) > 0:
                candidates.append({'action':'GATHER','target_id':target.id,'params':{},
                    'description':'走到这处资源点采集。'})
    if region.get('reactive_npcs'):
        # Keep parameter-free social actions available alongside movement.
        for known_entity in entities:
            if known_entity.get('target_id') == npc.id and known_entity.get('status') == 'pending':
                candidates.append({'action':'RESPOND_PROPOSAL','target_id':known_entity['id'],'params':{},
                    'description':'接受这个已经送达本人的提议；交易仍由世界校验余额、距离和归属。'})
        for org_id in npc.org_ids:
            if org_id in {value['id'] for value in entities}:
                candidates.append({'action':'LEAVE_ORG','target_id':org_id,'params':{},
                    'description':'退出自己所属的组织。'})
    return AgentContext(npc_id=npc.id, world_version=state.world_version,
        identity={"id": npc.id, "name": npc.name, "org_ids": npc.org_ids,
                  "region_id": npc.region_id, "tile": npc.tile.model_dump(), "hp": npc.hp,
                  "alive": npc.alive, "role": template.get("role", "旅人"),
                  "home_tile": template.get("tile"), "recent_dialogue": recent_dialogue,
                  "action_candidates": candidates,
                  "residence": template.get("place", "这片土地"),
                  "conduct": "在自己的工作地点附近活动。除非玩家明确请求、采集或自卫，不要跟随玩家前往出生点。"},
        goals=stored["goals"] or template.get("goals", []), own_inventory=[item for item in state.items if item.owner_id == npc.id],
        known_entities=entities, known_events=[*known, *extra_events], memories=selected_memories,
        allowed_actions=["WAIT", "MOVE", "GATHER", "TRANSFER", "SHARE_INFO", 'PROPOSE_RELATION',
                         'RESPOND_PROPOSAL', 'CRAFT', 'JOIN_ORG', 'LEAVE_ORG'],
        policy=stored["policy"], policy_version=stored["version"])


class AgentRuntime:
    def __init__(self, store, gateway):
        self.store, self.gateway = store, gateway
        with store.connection() as connection:
            connection.executescript(SCHEMA)

    def reserve(self, connection, scope, body):
        cached = self.store.cached(connection, scope, body)
        if cached is not None:
            return cached, None
        serialized = body.model_dump_json()
        previous = connection.execute("SELECT * FROM agent_requests WHERE scope=? AND id=?",
                                      (scope, body.request_id)).fetchone()
        if previous:
            if previous["body"] != serialized:
                raise WorldError("REQUEST_ID_REUSED", "同一请求 ID 携带不同内容。", 409)
            if time.time() - previous["started_at"] < max(30, self.gateway.timeout_s + 5):
                raise WorldError("REQUEST_IN_PROGRESS", "该请求仍在处理，请保留原 ID 稍后重试。", 409)
        token = uuid4().hex
        connection.execute("INSERT OR REPLACE INTO agent_requests VALUES (?, ?, ?, ?, ?)",
                           (scope, body.request_id, serialized, token, time.time()))
        return None, token

    def release(self, scope, request_id, token):
        with self.store.connection(write=True) as connection:
            connection.execute("DELETE FROM agent_requests WHERE scope=? AND id=? AND token=?",
                               (scope, request_id, token))

    def ensure_current(self, connection, world_id, body, scope, token):
        active = connection.execute("SELECT token FROM agent_requests WHERE scope=? AND id=?",
                                    (scope, body.request_id)).fetchone()
        if active is None or active[0] != token:
            raise WorldError("REQUEST_EXPIRED", "请求已被更新的执行替代。", 409)
        row = self.store.world_row(connection, world_id)
        state = StateView.model_validate_json(row["state"])
        if state.world_version != body.expected_world_version:
            raise WorldError("VERSION_CONFLICT", "模型处理期间世界已改变，请刷新状态。", 409)
        return state, json.loads(row["region"])

    @staticmethod
    def check_dialogue(state, npc_id):
        player, npc = living_actor(state, state.player_id), living_actor(state, npc_id)
        if npc.kind != "npc":
            raise WorldError("NPC_NOT_FOUND", "目标不是 NPC。", 404)
        require_near(player, npc.region_id, npc.tile)
        if player.behavior == "attacking" or npc.behavior == "attacking":
            raise WorldError("PRECONDITION_FAILED", "战斗中无法对话。")

    def apply_decision(self, connection, state, context, decision, mode, region, seq, trigger_ids=()):
        decision_id = "decision_" + uuid4().hex
        accepted = event(state, "decision_accepted", seq, context.npc_id, None,
                         {"decision_id": decision_id, "mode": mode}, [], [context.npc_id])
        accepted.caused_by = list(dict.fromkeys(source for memory in context.memories
            if memory["id"] in decision.evidence_memory_ids for source in memory["source_event_ids"]))
        accepted.caused_by = list(dict.fromkeys([*accepted.caused_by, *trigger_ids]))
        candidate = state.model_copy(deep=True)
        connection.execute("SAVEPOINT agent_decision")
        try:
            living_actor(candidate, context.npc_id)
            available_memories = {memory["id"] for memory in context.memories}
            if not set(decision.evidence_memory_ids) <= available_memories:
                raise WorldError("UNKNOWN_EVIDENCE", "决策引用了不可检索的记忆。")
            known_ids = {value.id for value in context.known_events}
            if any(not set(proposal.source_event_ids) <= known_ids for proposal in decision.memory_proposals):
                raise WorldError("UNKNOWN_EVIDENCE", "记忆来源超出本次上下文。")
            stored = profile(connection, state.world_id, context.npc_id)
            for key, value in decision.policy_patch.items():
                if (key not in stored["policy"] or not math.isfinite(value) or not 0 <= value <= 1
                        or abs(value - stored["policy"][key]) > .25):
                    raise WorldError("INVALID_POLICY", "策略修改超出可用参数或幅度。")
            if decision.policy_patch and not decision.evidence_memory_ids:
                raise WorldError("UNKNOWN_EVIDENCE", "策略修改需要本人可检索的依据。")
            knowledge.save_memory_proposals(connection, state.world_id, context.npc_id, decision.memory_proposals)
            if decision.policy_patch:
                previous = dict(stored["policy"])
                stored["policy"].update(decision.policy_patch)
                stored["version"] += 1
                stored["history"].append({"version": stored["version"], "old": previous,
                    "new": dict(stored["policy"]), "evidence_memory_ids": decision.evidence_memory_ids})
                connection.execute("INSERT OR REPLACE INTO npc_profiles VALUES (?, ?, ?)",
                                   (state.world_id, context.npc_id, json.dumps(stored)))
            events, task_ids = apply_intent(connection, candidate, context, decision.intent,
                                           region, seq + 1, accepted.id)
            connection.execute("RELEASE agent_decision")
            intent_status = "scheduled" if task_ids else "none"
            events = [accepted, *events]
            rejection = None
        except (WorldError, ValueError, TypeError) as exc:
            connection.execute("ROLLBACK TO agent_decision")
            connection.execute("RELEASE agent_decision")
            candidate, task_ids, intent_status = state, [], "rejected"
            rejection = getattr(exc, 'code', 'INVALID_INTENT')
            events = [event(state, "decision_rejected", seq, context.npc_id, None,
                            {"decision_id": decision_id, "reason": rejection}, [], [context.npc_id])]
        record = {"id": decision_id, "npc_id": context.npc_id, "mode": mode,
                  "decision": decision.model_dump(mode="json"), "intent_status": intent_status,
                  "rejection_code": rejection, "task_ids": task_ids,
                  "result_event_ids": [value.id for value in events]}
        connection.execute("INSERT INTO decisions VALUES (?, ?, ?, ?)",
                           (state.world_id, decision_id, context.npc_id, json.dumps(record, ensure_ascii=False)))
        return candidate, events, task_ids, intent_status

    async def dialogue(self, world_id, body):
        scope = world_id + "/dialogue"
        with self.store.connection(write=True) as connection:
            cached, token = self.reserve(connection, scope, body)
            if cached is not None:
                return cached
            state, _ = self.ensure_current(connection, world_id, body, scope, token)
            self.store.require_ordinary(connection, world_id)
            self.check_dialogue(state, body.npc_id)
            latest = connection.execute("SELECT MAX(started_at + cooldown_s) FROM attacks WHERE world_id=? AND attacker_id IN (?, ?)",
                (world_id, body.npc_id, state.player_id)).fetchone()[0]
            if latest is not None and self.store.clock() < latest:
                raise WorldError("PRECONDITION_FAILED", "当前攻击尚未结束。")
            seq = connection.execute("SELECT MAX(seq) FROM events WHERE world_id=?", (world_id,)).fetchone()[0] + 1
            speech = event(state, "speech", seq, state.player_id, body.npc_id,
                           {"text": body.text, "source_type": "report"}, [], [state.player_id, body.npc_id])
            context = build_context(connection, state, body.npc_id, [speech])
        try:
            decision, mode = await self.gateway.call("dialogue", context, body.text)
            with self.store.connection(write=True) as connection:
                state, region = self.ensure_current(connection, world_id, body, scope, token)
                self.store.require_ordinary(connection, world_id)
                self.check_dialogue(state, body.npc_id)
                self.store.append_event(connection, world_id, speech)
                state, events, task_ids, intent_status = self.apply_decision(
                    connection, state, context, decision, mode, region, seq + 1)
                reply_event = event(state, "npc_speech", seq + 1 + len(events), body.npc_id, state.player_id,
                    {"text": decision.reply, "mode": mode, "source_type": "report"}, [speech.id],
                    [body.npc_id, state.player_id])
                events.append(reply_event)
                turn = {"player": body.text, "npc": decision.reply, "mode": mode,
                        "source_event_ids": [speech.id, reply_event.id]}
                connection.execute("INSERT INTO npc_dialogue_turns VALUES (?, ?, ?, ?)",
                    (world_id, body.npc_id, body.request_id, json.dumps(turn, ensure_ascii=False)))
                state.world_version += 1
                state = StateView.model_validate(state.model_dump())
                connection.execute("UPDATE worlds SET state=? WHERE id=?", (state.model_dump_json(), world_id))
                for value in events:
                    self.store.append_event(connection, world_id, value)
                result = response(body.request_id, state, {"reply": decision.reply, "mode": mode, "npc_id":body.npc_id,
                    "intent_status": intent_status, "task_ids": task_ids,
                    "events": [value.model_dump(mode="json") for value in [speech, *events]],
                    "state": state.model_dump(mode="json")})
                self.store.remember(connection, scope, body, result)
                return result
        finally:
            self.release(scope, body.request_id, token)
