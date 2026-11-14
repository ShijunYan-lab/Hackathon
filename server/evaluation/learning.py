"""C validation and explicit rule fallback for B's pure learning proposal."""
import math
from uuid import uuid4

from shared.evaluation_protocol import LearnedMemory, LearningUpdate
from server.world.commands import WorldError


def fallback_update(profile, outcome):
    updated = profile.model_copy(deep=True)
    action = outcome.strategy
    old = profile.values[action]
    new = old + profile.alpha * (outcome.metrics.reward - old)
    updated.values[action] = new
    updated.version += 1
    updated.retrieval_epoch += 1
    statement = (f'本次尝试 {action}，交付 {outcome.metrics.cargo_delivered}/{outcome.metrics.cargo_initial}，'
                 f'费用 {outcome.metrics.gold_spent}，得分 {outcome.metrics.reward:.4f}。其他策略尚未由本轮验证。')
    updated.memories.append(LearnedMemory(id='learned_' + uuid4().hex, statement=statement,
        source_run_id=outcome.run_id, source_event_ids=outcome.source_event_ids, profile_version=updated.version))
    return LearningUpdate(source_run_id=outcome.run_id, from_version=profile.version, to_version=updated.version,
        changed_values={action: {'old': old, 'new': new}}, updated_profile=updated,
        source_event_ids=outcome.source_event_ids, explanation='规则降级：只按实际反馈更新本轮已执行策略的价值。')


def validate_update(profile, outcome, raw):
    update = LearningUpdate.model_validate(raw)
    new = update.updated_profile
    expected = profile.values[outcome.strategy] + profile.alpha * (outcome.metrics.reward - profile.values[outcome.strategy])
    valid = (update.source_run_id == outcome.run_id and update.from_version == profile.version
        and set(update.changed_values) == {outcome.strategy}
        and set(update.source_event_ids) == set(outcome.source_event_ids)
        and new.profile_id == profile.profile_id and new.learner_id == profile.learner_id
        and new.context_key == profile.context_key and new.alpha == profile.alpha
        and new.retrieval_epoch == profile.retrieval_epoch + 1
        and new.memories[:len(profile.memories)] == profile.memories
        and len(new.memories) > len(profile.memories)
        and len({memory.id for memory in new.memories}) == len(new.memories))
    for key, value in new.values.items():
        valid = valid and math.isclose(value, expected if key == outcome.strategy else profile.values[key], abs_tol=1e-9)
    valid = valid and math.isclose(update.changed_values[outcome.strategy].old, profile.values[outcome.strategy], abs_tol=1e-9)
    for memory in new.memories[len(profile.memories):]:
        valid = valid and (memory.source_run_id == outcome.run_id and memory.profile_version == new.version
            and set(memory.source_event_ids) <= set(outcome.source_event_ids))
    if not valid:
        raise WorldError('INVALID_LEARNING_UPDATE', '学习提议改变了未执行策略、冻结字段或来源。')
    return update
