"""C-facing NPC decisions. The caller owns execution and persistence."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from shared.protocol import AgentContext, AgentDecision, Intent

from . import provider
from .errors import AgentCallFailed
from .memory import retrieve, validate_proposals

_PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "npc_decision.txt").read_text(encoding="utf-8")
_SCHEMA = json.dumps(AgentDecision.model_json_schema(), ensure_ascii=False)


def _dead(context: AgentContext) -> bool:
    hp = context.identity.get("hp")
    return context.identity.get("alive") is False or (isinstance(hp, (int, float)) and hp <= 0)


def safe_fallback(context: AgentContext) -> AgentDecision:
    if _dead(context):
        return AgentDecision(reason_summary="角色已死亡")
    return AgentDecision(
        reply="我现在需要等等，稍后再谈。",
        intent=Intent(action="WAIT") if "WAIT" in context.allowed_actions else None,
        reason_summary="模型不可用，采用安全降级",
    )


def _confirmed_patch(context: AgentContext, outcomes) -> dict[str, float]:
    # Optional C integration convention, never populated by the model or player.
    for event in reversed(outcomes):
        if event.type != "agent_action_outcome" or event.actor_id != context.npc_id:
            continue
        key = event.facts.get("policy_key")
        reward = event.facts.get("reward")
        version = event.facts.get("policy_version")
        if (
            isinstance(key, str) and key in context.policy
            and type(reward) in (int, float) and -1 <= reward <= 1
            and version == context.policy_version
        ):
            old = context.policy[key]
            if -1 <= old <= 1:
                return {key: old + .8 * (reward - old)}
    return {}


def _rank_strategy(context: AgentContext, intent: Intent, candidates, matching) -> Intent:
    # C may group interchangeable executions of the same goal (e.g. two routes).
    if not matching or not matching[0].get("strategy_group"):
        return intent
    group = matching[0]["strategy_group"]
    scored = [
        candidate for candidate in candidates
        if candidate.get("strategy_group") == group
        and isinstance(candidate.get("policy_key"), str)
        and candidate["policy_key"] in context.policy
        and -1 <= context.policy[candidate["policy_key"]] <= 1
    ]
    if not scored:
        return intent
    winner = max(scored, key=lambda candidate: context.policy[candidate["policy_key"]])
    return Intent(action=winner["action"], target_id=winner["target_id"], params=winner["params"])


async def _decide(context: AgentContext, operation: str, event_ids=(), text: str = "") -> AgentDecision:
    if _dead(context):
        raise AgentCallFailed("角色已死亡")
    visible = {event.id: event for event in context.known_events}
    if not set(event_ids) <= visible.keys():
        raise AgentCallFailed("触发事件超出该 NPC 的视野")
    relevant = [visible[event_id] for event_id in dict.fromkeys(event_ids)]
    events = {event.id: event for event in [*context.known_events[-12:], *relevant]}
    memories = retrieve(context, event_ids, text + " " + " ".join(context.goals))
    entities = {entity["id"] for entity in context.known_entities if isinstance(entity.get("id"), str)}
    candidates = []
    for candidate in context.identity.get("action_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        try:
            candidate_intent = Intent.model_validate({
                key: candidate[key] for key in ("action", "params", "target_id") if key in candidate
            })
        except ValueError:
            continue
        if candidate_intent.action in context.allowed_actions and candidate_intent.target_id in entities:
            candidates.append({**candidate, **candidate_intent.model_dump()})
    payload = context.model_dump(
        mode="json", exclude={"known_events", "memories", "world_version"},
    )
    payload.update(
        operation=operation, event_ids=list(event_ids), text=text[:1000], memories=memories,
        known_events=[event.model_dump(mode="json") for event in events.values()],
    )
    payload["identity"].pop("action_candidates", None)
    payload["action_candidates"] = candidates
    messages = [
        {"role": "system", "content": provider.NPC_PERSONA + "\n" + _PROMPT + "\nJSON Schema:\n" + _SCHEMA},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    for attempt in range(2):
        raw, _model = await provider.complete(messages)
        try:
            decision = AgentDecision.model_validate_json(raw)
            if decision.policy_patch:
                raise ValueError("模型不能提交策略数值")
            if not set(decision.evidence_memory_ids) <= {memory["id"] for memory in memories}:
                raise ValueError("引用了不可见记忆")
            intent = decision.intent
            if intent:
                if operation == "reflect" or intent.action not in context.allowed_actions:
                    raise ValueError("当前行动不合法")
                if intent.target_id is not None and intent.target_id not in entities:
                    raise ValueError("行动引用了未知目标")
                if intent.action == "WAIT" and (intent.target_id or intent.params):
                    raise ValueError("WAIT 不需要目标或参数")
                if intent.action in {"MOVE", "GATHER", "TRANSFER", "SHARE_INFO", "ATTACK", "JOIN_ORG",
                                     "LEAVE_ORG", "PROPOSE_RELATION", "RESPOND_PROPOSAL"} and intent.target_id is None:
                    raise ValueError("行动缺少已知目标")
                matching = [
                    candidate for candidate in candidates if candidate.get("action") == intent.action
                    and candidate.get("target_id") == intent.target_id
                    and candidate.get("params", {}) == intent.params
                ]
                if (intent.params or (candidates and intent.action != "WAIT")) and not matching:
                    raise ValueError("行动及参数不在 C 给出的候选项中")
                if operation == "plan":
                    ranked = _rank_strategy(context, intent, candidates, matching)
                    if ranked != intent:
                        decision.intent = ranked
                        decision.reply = ""
                        decision.reason_summary = "在同一目标的合法候选中采用历史策略值较高的行动。"
            decision.memory_proposals = validate_proposals(context, decision.memory_proposals, events)
            if operation == "reflect":
                decision.policy_patch = _confirmed_patch(context, relevant)
            return decision
        except ValueError:
            if attempt == 0:
                messages.append({"role": "user", "content": (
                    "前次输出未通过结构、来源或权限校验。请按原输入重写一个合法 JSON 对象，"
                    "无法确定的 action、记忆和引用可以省略。"
                )})
    raise AgentCallFailed("模型两次返回的决策未通过结构或权限校验")


async def dialogue(context: AgentContext, text: str) -> AgentDecision:
    return await _decide(context, "dialogue", text=text)


async def plan(context: AgentContext, trigger_event_ids: list[str]) -> AgentDecision:
    return await _decide(context, "plan", trigger_event_ids)


async def reflect(context: AgentContext, outcome_event_ids: list[str]) -> AgentDecision:
    return await _decide(context, "reflect", outcome_event_ids)
