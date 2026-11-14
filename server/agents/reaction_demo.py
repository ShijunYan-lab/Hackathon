"""Offline A/B/C handoff smoke demo; simulated C-confirmed events only."""
from __future__ import annotations

from copy import deepcopy

from shared.protocol import AgentContext, Event

from .event_reactions import propose_emergency_reaction
from .social_feedback import assess_social_event


def main() -> None:
    base = AgentContext(
        npc_id="npc_merchant", world_version=3,
        identity={
            "name": "商人艾莉", "hp": 30, "max_hp": 30,
            "action_candidates": [
                {"action": "FLEE", "params": {"reason": "under_attack"}},
                {"action": "ATTACK", "target_id": "player_01", "params": {"weapon_id": "sword_01"}},
                {"action": "SHARE_INFO", "target_id": "guard_01", "params": {"text": "求援"},
                 "reaction_role": "seek_help"},
            ],
        },
        goals=["安全运货"], own_inventory=[],
        known_entities=[{"id": "player_01", "name": "旅人"}, {"id": "guard_01", "name": "守卫"}],
        known_events=[
            Event(id="evt_hit_01", event_seq=1, tick=1, type="hit_confirmed",
                  actor_id="player_01", target_id="npc_merchant", facts={"damage": 6},
                  caused_by=[], witness_ids=["npc_merchant"]),
            Event(id="evt_insult_01", event_seq=2, tick=2, type="social_utterance",
                  actor_id="player_01", target_id="npc_merchant",
                  facts={"speech_act": "insult", "text": "你是个胆小鬼"},
                  caused_by=[], witness_ids=["npc_merchant"]),
        ],
        memories=[], allowed_actions=["WAIT", "FLEE", "ATTACK", "SHARE_INFO"],
        policy={}, policy_version=0,
    )
    print("[离线规则演示] 以下事件均为模拟的 C 已确认事件，不是正式游戏运行结果。")
    for persona in ("谨慎克制", "勇敢好胜", "随和但有原则"):
        npc = deepcopy(base)
        npc.identity["personality"] = persona
        response = propose_emergency_reaction(npc, ["evt_hit_01"])
        social = assess_social_event(npc, "evt_insult_01")
        print(f"角色性格：{persona}")
        print(f"  遭到攻击的行动提案：{response.intent.model_dump() if response.intent else None}")
        print(f"  直接受辱的关系提案：trust {social.trust_delta:+.3f}，"
              f"anger {social.anger_delta:+.3f}，hostility {social.hostility_delta:+.3f}")
        print("  以上均未修改真实 NPC 状态，必须由 C 结算和持久化。")


if __name__ == "__main__":
    main()
