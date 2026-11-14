"""Validated agent intentions and visible task completion."""
from collections import deque
import json
import math
from uuid import uuid4

from shared.protocol import Event, ItemState, ItemStats, Task, TaskReportPayload
from server.world.commands import WorldError, apply_checkpoint
from server.world.items import apply_item_command, living_actor, require_near


SCHEMA = """
CREATE TABLE IF NOT EXISTS task_effects (
    world_id TEXT NOT NULL, task_id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, task_id)
);
CREATE TABLE IF NOT EXISTS task_reports (
    world_id TEXT NOT NULL, task_id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, task_id)
);
"""


def event(state, kind, seq, actor_id, target_id, facts, sources, witnesses):
    return Event(id="evt_" + uuid4().hex, event_seq=seq, tick=state.tick, type=kind,
                 actor_id=actor_id, target_id=target_id, facts=facts, caused_by=sources,
                 witness_ids=sorted(set(witnesses)))


def reachable(region, start, target):
    start_cell, target_cell = (int(start.x), int(start.y)), (int(target.x), int(target.y))
    blocked = {tuple(cell) for cell in region["blocked_tiles"]}
    pending, visited = deque([start_cell]), {start_cell}
    while pending:
        cell = pending.popleft()
        if cell == target_cell:
            return True
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            candidate = cell[0] + dx, cell[1] + dy
            if (0 <= candidate[0] < region["width_tiles"] and 0 <= candidate[1] < region["height_tiles"]
                    and candidate not in blocked and candidate not in visited):
                visited.add(candidate)
                pending.append(candidate)
    return False


def apply_intent(connection, state, context, intent, region, seq, source_id):
    if intent is None or intent.action == "WAIT":
        return [], []
    if intent.action not in context.allowed_actions:
        raise WorldError("ACTION_NOT_SUPPORTED", "意图超出当前可用动作。")
    actor = living_actor(state, context.npc_id)
    from server.world import economy
    if intent.action in ("OPEN_TRADE", "BARGAIN", "ASK_WORK", "ACCEPT_QUEST", "GUIDE_HOME"):
        from server.world.living_world import apply_dialogue_action
        return apply_dialogue_action(connection, state, context, intent, region, seq, source_id)
    from shared.world_protocol import OfferRequest
    if intent.action == 'CRAFT':
        if set(intent.params) != {'recipe_id'} or intent.target_id not in (None, actor.id):
            raise WorldError('INVALID_INTENT', 'CRAFT 只需要本人的 recipe_id。')
        return economy.craft(connection, state, actor.id, intent.params['recipe_id'], seq, [source_id]), []
    known_ids = {value["id"] for value in context.known_entities}
    if intent.target_id not in known_ids:
        raise WorldError("UNKNOWN_TARGET", "NPC 尚不知道这个行动目标。")
    if intent.action == 'PROPOSE_RELATION':
        if set(intent.params) != {'org_id', 'stance'}:
            raise WorldError('INVALID_INTENT', '合作需要 org_id 和 stance。')
        target = economy.organization(state, intent.target_id)
        proposal = OfferRequest(request_id=source_id, expected_world_version=state.world_version,
            actor_id=actor.id, target_id=target.representative_id, kind='relation',
            org_id=intent.params['org_id'], target_org_id=target.id, stance=intent.params['stance'])
        return economy.offer(connection, state, proposal, seq, [source_id]), []
    if intent.action in ('RESPOND_PROPOSAL', 'JOIN_ORG'):
        if intent.action == 'JOIN_ORG':
            if set(intent.params) != {'offer_id'}:
                raise WorldError('INVALID_INTENT', '入会需要 offer_id。')
            offer_id, org_id = intent.params['offer_id'], intent.target_id
        else:
            if intent.params:
                raise WorldError('INVALID_INTENT', '接受提议不需要额外参数。')
            offer_id, org_id = intent.target_id, None
        return economy.accept(connection, state, actor.id, offer_id, seq, org_id), []
    if intent.action == 'LEAVE_ORG':
        if intent.params:
            raise WorldError('INVALID_INTENT', '退出组织不需要额外参数。')
        return economy.leave(state, actor.id, intent.target_id, seq), []
    if intent.action == "TRANSFER":
        if any(org.id == intent.target_id for org in state.organizations) and set(intent.params) == {'item_id'}:
            return economy.supply(connection, state, actor.id, intent.target_id, [intent.params['item_id']], seq), []
        if set(intent.params) == {'item_id', 'price'}:
            proposal = OfferRequest(request_id=source_id, expected_world_version=state.world_version,
                actor_id=actor.id, target_id=intent.target_id, kind='trade', **intent.params)
            return economy.offer(connection, state, proposal, seq, [source_id]), []
        if set(intent.params) != {"item_id"}:
            raise WorldError("INVALID_INTENT", "TRANSFER 参数需要 item_id。")
        events = apply_item_command(state, "GIVE", {"actor_id": actor.id,
            "target_id": intent.target_id, "item_id": intent.params["item_id"]}, seq)
        events[0].caused_by = [source_id]
        return events, []
    if intent.action == "SHARE_INFO":
        if set(intent.params) != {"memory_id"}:
            raise WorldError("INVALID_INTENT", "SHARE_INFO 参数需要 memory_id。")
        memory = next((value for value in context.memories if value["id"] == intent.params["memory_id"]), None)
        if memory is None:
            raise WorldError("UNKNOWN_EVIDENCE", "只能转述本人可检索的记忆。")
        target = living_actor(state, intent.target_id)
        require_near(actor, target.region_id, target.tile)
        shared = event(state, "info_shared", seq, actor.id, target.id,
                       {"statement": memory["statement"], "source_type": "report",
                        "root_event_ids": memory["source_event_ids"]},
                       [source_id, *memory["source_event_ids"]], [actor.id, target.id])
        return [shared], []
    if intent.action not in ("MOVE", "GATHER"):
        raise WorldError("ACTION_NOT_SUPPORTED", "This action has no enabled executor.")
    if intent.params:
        raise WorldError("INVALID_INTENT", "MOVE/GATHER 使用已有目标 ID，参数应为空。")
    if actor.task_id or any(task.actor_id == actor.id and task.status in ("pending", "running") for task in state.tasks):
        raise WorldError("PRECONDITION_FAILED", "NPC 已有进行中的任务。")
    site = next((site for site in state.sites if site.id == intent.target_id), None)
    target = site or next((value for value in state.actors if value.id == intent.target_id and value.alive), None)
    if target is None or actor.region_id != target.region_id:
        raise WorldError("OUT_OF_RANGE", "目标应位于当前可达地图。")
    if intent.action == "GATHER" and (site is None or site.remaining < 1):
        raise WorldError("PRECONDITION_FAILED", "资源点不存在或已耗尽。")
    if not reachable(region, actor.tile, target.tile):
        raise WorldError("OUT_OF_RANGE", "地图上没有可通行的路径。")
    task = Task(id="task_" + uuid4().hex, actor_id=actor.id, kind="MOVE", target_id=target.id,
                target_region_id=target.region_id, target_tile=target.tile.model_copy(), status="pending",
                started_tick=state.tick, source_event_ids=[source_id])
    state.tasks.append(task)
    actor.task_id = task.id
    actor.behavior = "moving"
    connection.execute("INSERT INTO task_effects VALUES (?, ?, ?)",
                       (state.world_id, task.id, json.dumps({"action": intent.action, "site_id": intent.target_id})))
    scheduled = event(state, "task_scheduled", seq, actor.id, target.id,
                      {"task_id": task.id, "action": intent.action}, [source_id], [actor.id])
    return [scheduled], [task.id]


def apply_task_report(connection, state, payload, region, seq):
    report = TaskReportPayload.model_validate(payload)
    serialized = report.model_dump_json()
    previous = connection.execute("SELECT body FROM task_reports WHERE world_id=? AND task_id=?",
                                  (state.world_id, report.task_id)).fetchone()
    if previous is not None:
        if previous[0] != serialized:
            raise WorldError("TASK_ALREADY_FINISHED", "任务已按另一份报告结算。", 409)
        return []
    task = next((value for value in state.tasks if value.id == report.task_id), None)
    if task is None:
        raise WorldError("TASK_NOT_FOUND", "任务不存在。", 404)
    if task.actor_id != report.actor_id or task.status not in ("pending", "running"):
        raise WorldError("PRECONDITION_FAILED", "任务已失效或报告角色不匹配。")
    actor = living_actor(state, report.actor_id)
    if task.kind not in ("MOVE", "FLEE", "ATTACK"):
        raise WorldError("ACTION_NOT_SUPPORTED", "该任务类型尚未接入结算。")
    if report.status == "failed" and not report.failure_code:
        raise WorldError("PRECONDITION_FAILED", "失败任务需提供原因。")
    if report.status == "succeeded":
        if task.kind == 'ATTACK':
            target = next((value for value in state.actors if value.id == task.target_id), None)
            if target is None or target.alive or report.failure_code:
                raise WorldError('PRECONDITION_FAILED', '目标仍存活，不能报告战斗成功。')
        elif report.failure_code or report.region_id != task.target_region_id or task.target_tile is None or math.hypot(
                report.tile.x - task.target_tile.x, report.tile.y - task.target_tile.y) > .75:
            raise WorldError("OUT_OF_RANGE", "实际位置尚未到达任务目标。")
    apply_checkpoint(state, {"region_id": report.region_id,
        "positions": [{"actor_id": actor.id, "tile": report.tile.model_dump()}]}, region)
    effect_row = connection.execute("SELECT body FROM task_effects WHERE world_id=? AND task_id=?",
                                    (state.world_id, task.id)).fetchone()
    if effect_row is None and task.kind != 'ATTACK':
        raise WorldError("PRECONDITION_FAILED", "任务缺少后端效果定义。")
    effect = json.loads(effect_row[0]) if effect_row else {'action':'SELF_DEFENSE'}
    witnesses = [value.id for value in state.actors if value.alive and value.region_id == actor.region_id
                 and math.hypot(value.tile.x - actor.tile.x, value.tile.y - actor.tile.y) <= 6]
    finished = event(state, "task_" + report.status, seq, actor.id, task.target_id,
                     {"task_id": task.id, "action": effect["action"], "failure_code": report.failure_code}, task.source_event_ids, witnesses)
    events = [finished]
    if report.status == "succeeded" and effect["action"] == "GATHER":
        site = next((value for value in state.sites if value.id == effect["site_id"]), None)
        if site is None or site.remaining < 1:
            raise WorldError("PRECONDITION_FAILED", "到达时资源已耗尽。")
        site.remaining -= 1
        item_id = "item_" + uuid4().hex
        gathered = event(state, "resource_gathered", seq + 1, actor.id, site.id,
                         {"item_id": item_id, "material_id": site.kind, "quantity": 1, "remaining": site.remaining}, [finished.id], witnesses)
        state.items.append(ItemState(id=item_id, name=site.kind, base_type="material", quality="common",
            material_id=site.kind, owner_id=actor.id, origin_event_ids=[gathered.id],
            stats=ItemStats(damage=0, cooldown_s=1, armor=0)))
        events.append(gathered)
    task.status = report.status
    actor.task_id = None
    actor.behavior = "idle"
    if report.status == "succeeded" and effect["action"] in ("COURIER_COLLECT", "COURIER_DELIVER"):
        from server.world.living_world import task_effect
        events.extend(task_effect(connection, state, effect, task, actor, finished, region, seq + len(events)))
    connection.execute("INSERT INTO task_reports VALUES (?, ?, ?)", (state.world_id, task.id, serialized))
    if task.kind == 'ATTACK' and region.get('reactive_npcs'):
        template = next((value for value in region.get('npc_spawns',[]) if value.get('appearance_key')==actor.appearance_key),None)
        from server.world import living_world
        life_data=living_world.read(connection,state.world_id)
        person=(life_data or {}).get('people',{}).get(actor.id,{})
        if person.get('home_tile'):
            template={'tile':person['home_tile']}
        if template:
            from shared.protocol import Tile
            home=Tile.model_validate(template['tile'])
            if math.hypot(home.x-actor.tile.x,home.y-actor.tile.y)>1 and reachable(region,actor.tile,home):
                returning=Task(id='task_'+uuid4().hex,actor_id=actor.id,kind='MOVE',target_region_id=actor.region_id,
                    target_tile=home,status='pending',started_tick=state.tick,source_event_ids=[finished.id])
                state.tasks.append(returning)
                actor.task_id,actor.behavior=returning.id,'moving'
                connection.execute('INSERT INTO task_effects VALUES (?, ?, ?)',
                    (state.world_id,returning.id,json.dumps({'action':'RETURN_HOME'})))
                events.append(event(state,'task_scheduled',seq+len(events),actor.id,None,
                    {'task_id':returning.id,'action':'RETURN_HOME'},[finished.id],witnesses))
    return events
