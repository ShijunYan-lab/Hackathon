"""Side-effect-free *proposals* for C's NPC emotions and relationships.

Only C-confirmed, personally addressed social events can be assessed. These
values are a simple initial appraisal model, not reliable sentiment analysis.
C remains responsible for event classification, deduplication, persistence,
relationship bounds and notifying the NPC. Do not apply this function twice to
an event, or treat player text as an authoritative speech-act classification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from shared.protocol import AgentContext

from .event_reactions import _traits

# A conversation event may carry an authoritative C-classified speech_act.
SPEECH_ACTS = frozenset({"insult", "threat", "apology", "thanks", "help"})


@dataclass(frozen=True)
class SocialImpact:
    npc_id: str
    source_event_id: str
    other_actor_id: str
    speech_act: str
    trust_delta: float
    anger_delta: float
    fear_delta: float
    hostility_delta: float
    rationale: str

    def as_dict(self) -> dict:
        return asdict(self)


def assess_social_event(context: AgentContext, event_id: str) -> SocialImpact | None:
    """Return a bounded appraisal for an event directly addressed to this NPC.

    Repeated calls are deterministic but NOT idempotent as world mutations. C must
    persist only once per (npc_id, event_id) and clamp the destination attributes.
    """
    event = next((e for e in context.known_events if e.id == event_id), None)
    if event is None or event.target_id != context.npc_id or not event.actor_id:
        return None
    if event.actor_id == context.npc_id:
        return None
    if event.type == "social_utterance":
        kind = event.facts.get("speech_act")
    elif event.type == "help_given":
        kind = "help"
    else:
        # A rumor, attack, unclassified dialogue, or unknown event is not an
        # authoritative social-meaning classification.
        return None
    if kind not in SPEECH_ACTS:
        return None
    courage, aggression = _traits(context.identity)
    if kind == "insult":
        changes = (-.14 - .12 * aggression, .12 + .20 * aggression, .02, .06 + .12 * aggression)
    elif kind == "threat":
        changes = (-.28, .12 * aggression, .20 + .25 * (1 - courage), .18 + .09 * aggression)
    elif kind == "apology":
        changes = (.10, -.14, -.05, -.10)
    elif kind == "thanks":
        changes = (.05, -.02, -.01, -.02)
    else:  # confirmed help_given
        changes = (.20, -.10, -.10, -.15)
    trust, anger, fear, hostility = (round(value, 3) for value in changes)
    return SocialImpact(
        npc_id=context.npc_id,
        source_event_id=event.id,
        other_actor_id=event.actor_id,
        speech_act=kind,
        trust_delta=trust,
        anger_delta=anger,
        fear_delta=fear,
        hostility_delta=hostility,
        rationale="基于可见且直接指向本角色的社会事件，结合角色勇气/攻击倾向提出状态变化；实际变更需 C 确认。",
    )
