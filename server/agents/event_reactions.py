"""Fast, verifiable NPC emergency responses to C-confirmed world events.

The function makes a *proposal*, never executes a world mutation. It is intentionally
small and deterministic: imminent danger must not wait for an LLM round trip.
LLM dialogue/long-term plans still go through service.py. The authoritative world
must supply the event, visible actors and EXACT legal action candidates.
"""
from __future__ import annotations

from typing import Any

from shared.protocol import AgentContext, AgentDecision, Event, Intent, MemoryProposal

from .memory import validate_proposals

# C is responsible for emitting/normalizing the actual event type. Do not treat
# player-provided text or unverified hearsay as a confirmed physical attack.
CONFIRMED_ASSAULT_TYPES = frozenset({
    "hit_confirmed", "attack_confirmed", "damage_taken", "combat_hit", "assault",
})


def _ratio(value: Any, default: float) -> float:
    if type(value) not in (int, float):
        return default
    return max(0.0, min(1.0, float(value)))


def _traits(identity: dict[str, Any]) -> tuple[float, float]:
    """Fallback textual persona values are ONLY defaults; C can give numeric traits."""
    profile = str(identity.get("personality", ""))
    role = str(identity.get("role", ""))
    courage, aggression = 0.5, 0.4
    if any(token in profile for token in ("胆小", "谨慎", "克制", "避险", "退路")):
        courage, aggression = 0.25, 0.2
    elif any(token in profile for token in ("勇敢", "好胜", "冲动", "强硬")):
        courage, aggression = 0.85, 0.8
    elif any(token in profile for token in ("随和", "宽容", "讲理")):
        courage, aggression = 0.45, 0.25
    if role in ("guard", "bandit") and not profile:
        courage, aggression = 0.7, 0.7
    traits = identity.get("traits")
    if isinstance(traits, dict):
        courage = _ratio(traits.get("courage"), courage)
        aggression = _ratio(traits.get("aggression"), aggression)
    return courage, aggression


def legal_candidates(context: AgentContext) -> list[dict[str, Any]]:
    """Normalize C-authorized candidates; preserve metadata used for reactions.

    Targetless actions (such as FLEE) are valid when explicitly authorized by C.
    Other target IDs must be locally known to the NPC. A candidate's parameters
    are copied exactly, not invented or edited by this module.
    """
    entity_ids = {
        entity["id"] for entity in context.known_entities
        if isinstance(entity.get("id"), str)
    }
    result: list[dict[str, Any]] = []
    for raw in context.identity.get("action_candidates") or []:
        if not isinstance(raw, dict):
            continue
        try:
            parsed = Intent.model_validate({
                key: raw[key] for key in ("action", "target_id", "params") if key in raw
            })
        except ValueError:
            continue
        if parsed.action not in context.allowed_actions:
            continue
        if parsed.target_id is not None and parsed.target_id not in entity_ids:
            continue
        if parsed.action == "WAIT" and (parsed.target_id is not None or parsed.params):
            continue
        result.append({**raw, **parsed.model_dump()})
    return result


def _intent(candidate: dict[str, Any] | None) -> Intent | None:
    if candidate is None:
        return None
    return Intent.model_validate({
        key: candidate[key] for key in ("action", "target_id", "params") if key in candidate
    })


def _candidate(candidates: list[dict[str, Any]], action: str, target: str | None = None,
               *, tag: str | None = None) -> dict[str, Any] | None:
    for item in candidates:
        if item["action"] != action:
            continue
        if target is not None and item.get("target_id") != target:
            continue
        if tag is not None and item.get("reaction_role") != tag:
            continue
        return item
    return None


def _latest_direct_assault(context: AgentContext, trigger_event_ids: list[str]) -> Event | None:
    visible = {event.id: event for event in context.known_events}
    for event_id in reversed(trigger_event_ids):
        event = visible.get(event_id)
        if (event is not None and event.type.lower() in CONFIRMED_ASSAULT_TYPES
                and event.target_id == context.npc_id and event.actor_id != context.npc_id):
            return event
    return None


def propose_emergency_reaction(context: AgentContext, trigger_event_ids: list[str]) -> AgentDecision | None:
    """Produce an immediate, personality-sensitive response to a direct assault.

    Only an event about THIS NPC can trigger self-defense. Witnessed attacks on
    other actors and reports of attacks continue to the LLM planning path.
    All actions must be present in C's candidate list, except WAIT when allowed.
    """
    attack = _latest_direct_assault(context, trigger_event_ids)
    if attack is None:
        return None

    candidates = legal_candidates(context)
    courage, aggression = _traits(context.identity)
    hp = context.identity.get("hp")
    max_hp = context.identity.get("max_hp")
    health = (
        _ratio(float(hp) / max_hp, 1.0)
        if type(hp) in (int, float) and type(max_hp) in (int, float) and max_hp > 0
        else 1.0
    )
    attacker = attack.actor_id
    defense = _candidate(candidates, "ATTACK", attacker) if attacker else None
    escape = _candidate(candidates, "FLEE")
    if escape is None:
        escape = _candidate(candidates, "MOVE", tag="escape")
    help_request = _candidate(candidates, "SHARE_INFO", tag="seek_help")
    if help_request is None:
        help_request = _candidate(candidates, "SHARE_INFO", tag="help")
    defensive = courage >= .65 and aggression >= .5 and health >= .5
    urgent = health <= .35

    if urgent:
        chosen = escape or help_request or defense
        response = "我受伤了，得先保住性命！"
    elif defensive:
        chosen = defense or help_request or escape
        response = "你敢动手？我会保护自己！"
    elif courage <= .35:
        chosen = escape or help_request or defense
        response = "别过来！有人能帮帮我吗？"
    else:
        chosen = help_request or escape or defense
        response = "住手！我不想打这一架。"

    action = _intent(chosen)
    if action is None and "WAIT" in context.allowed_actions:
        action = Intent(action="WAIT")

    proposal = MemoryProposal(
        statement=f"我亲身遭遇来自 {attacker or '未知袭击者'} 的攻击，需要重新判断安全与信任。",
        source_type="observation", source_event_ids=[attack.id],
        confidence=1.0, status="supported",
    )
    vetted = validate_proposals(context, [proposal], {attack.id: attack})
    return AgentDecision(
        reply=response,
        intent=action,
        memory_proposals=vetted,
        reason_summary=(
            f"依据直接受袭事件 {attack.id}、当前生命比例 {health:.2f} 及个人勇气 {courage:.2f}"
            "，选择当前授权的应急行动；执行和结算须经 C 审核。"
        )[:160],
    )
