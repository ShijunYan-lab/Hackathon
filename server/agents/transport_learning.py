from hashlib import sha256

from shared.evaluation_protocol import (
    LearnedMemory, LearningProfile, LearningUpdate, TransportChoice,
    TransportContext, TransportOutcome, ValueChange,
)


def choose_transport(context: TransportContext, profile: LearningProfile) -> TransportChoice:
    if (context.learner_id, context.context_key) != (profile.learner_id, profile.context_key):
        raise ValueError("运输情境与学习档案不匹配")
    strategy = max(context.available_strategies, key=lambda action: (profile.values[action], action == "direct"))
    visible = set(context.known_event_ids)
    return TransportChoice(
        strategy=strategy,
        profile_version=profile.version,
        evidence_memory_ids=[
            memory.id for memory in profile.memories[-4:]
            if set(memory.source_event_ids) <= visible
        ],
        reason_summary=f"在合法运输策略中选择 {strategy}（Q={profile.values[strategy]:.3f}）。",
    )


def learn_transport(profile: LearningProfile, outcome: TransportOutcome) -> LearningUpdate:
    if any(memory.source_run_id == outcome.run_id for memory in profile.memories):
        raise ValueError("该运输结果已用于学习")
    if (outcome.learner_id, outcome.context_key, outcome.profile_version) != (
        profile.learner_id, profile.context_key, profile.version
    ):
        raise ValueError("运输结果与学习者、情境或策略版本不匹配")
    strategy = outcome.strategy
    old = profile.values[strategy]
    reward = outcome.metrics.reward
    new = old + profile.alpha * (reward - old)
    version = profile.version + 1
    evidence = list(dict.fromkeys(outcome.source_event_ids))
    memory = LearnedMemory(
        id="mem_transport_" + sha256(outcome.run_id.encode()).hexdigest(),
        statement=f"执行 {strategy}，实际交付率 {outcome.metrics.delivered_ratio:.1%}，奖励 {reward:.3f}。",
        source_run_id=outcome.run_id,
        source_event_ids=evidence,
        profile_version=version,
    )
    updated = LearningProfile.model_validate({
        **profile.model_dump(),
        "version": version,
        "retrieval_epoch": profile.retrieval_epoch + 1,
        "values": {**profile.values, strategy: new},
        "memories": [*profile.memories, memory],
    })
    return LearningUpdate(
        source_run_id=outcome.run_id, from_version=profile.version, to_version=version,
        changed_values={strategy: ValueChange(old=old, new=new)}, updated_profile=updated,
        source_event_ids=evidence,
        explanation=f"根据 {strategy} 的实际奖励 {reward:.3f}，Q 从 {old:.3f} 更新至 {new:.3f}。",
    )
