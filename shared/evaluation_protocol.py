"""Evaluation extension DTOs. These types are not a learning implementation."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from shared.protocol import DTO, RequestBase, StateView

TransportStrategy = Literal["direct", "escort"]
EvaluationStatus = Literal[
    "ready", "first_running", "learning", "ready_for_second",
    "second_running", "complete", "rolled_back", "rollback_running", "failed"
]
RunKind = Literal["first", "second", "rollback_check"]

class LearnedMemory(DTO):
    id: str
    statement: str = Field(min_length=1, max_length=500)
    source_run_id: str
    source_event_ids: list[str] = Field(min_length=1)
    profile_version: int = Field(ge=1)

class LearningProfile(DTO):
    profile_id: str
    learner_id: str
    version: int = Field(ge=0)
    context_key: str
    alpha: float = Field(gt=0, le=1)
    values: dict[str, float]
    memories: list[LearnedMemory] = Field(default_factory=list)
    retrieval_epoch: int = Field(ge=0)

    @model_validator(mode="after")
    def check_values(self):
        if set(self.values) != {"direct", "escort"}:
            raise ValueError("Transport values must contain exactly direct and escort.")
        if any(not (-1 <= value <= 1) for value in self.values.values()):
            raise ValueError("Transport values must lie between -1 and 1.")
        if any(memory.profile_version > self.version for memory in self.memories):
            raise ValueError("Future memories cannot be retrieved by this profile.")
        return self

class TransportContext(DTO):
    learner_id: str
    context_key: str
    available_strategies: list[TransportStrategy] = Field(min_length=1)
    own_gold: int = Field(ge=0)
    escort_cost: int = Field(ge=0)
    guard_id: str | None = None
    known_event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_escort(self):
        if "escort" in self.available_strategies:
            if self.guard_id is None or self.own_gold < self.escort_cost:
                raise ValueError("Escort requires an available guard and enough gold.")
        return self

class TransportChoice(DTO):
    strategy: TransportStrategy
    profile_version: int = Field(ge=0)
    evidence_memory_ids: list[str] = Field(default_factory=list)
    reason_summary: str = Field(max_length=300)

class RunMetrics(DTO):
    cargo_initial: int = Field(gt=0)
    cargo_delivered: int = Field(ge=0)
    gold_initial: int = Field(gt=0)
    gold_spent: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    merchant_survived: bool
    task_success: bool
    delivered_ratio: float = Field(ge=0, le=1)
    reward: float = Field(ge=-0.1, le=1)

    @model_validator(mode="after")
    def check_calculated_metrics(self):
        if self.cargo_delivered > self.cargo_initial or self.gold_spent > self.gold_initial:
            raise ValueError("Delivery and spending cannot exceed initial budgets.")
        ratio = self.cargo_delivered / self.cargo_initial
        reward = ratio - 0.1 * self.gold_spent / self.gold_initial
        if abs(self.delivered_ratio - ratio) > 1e-8:
            raise ValueError("Delivery ratio must agree with real cargo counts.")
        if abs(self.reward - reward) > 1e-8:
            raise ValueError("Reward must agree with the frozen scoring formula.")
        if not self.merchant_survived and self.task_success:
            raise ValueError("A dead merchant cannot satisfy this scenario.")
        return self

class TransportOutcome(DTO):
    run_id: str
    learner_id: str
    context_key: str
    profile_version: int = Field(ge=0)
    strategy: TransportStrategy
    metrics: RunMetrics
    source_event_ids: list[str] = Field(min_length=1)

class ValueChange(DTO):
    old: float = Field(ge=-1, le=1)
    new: float = Field(ge=-1, le=1)

class LearningUpdate(DTO):
    source_run_id: str
    from_version: int = Field(ge=0)
    to_version: int = Field(ge=1)
    changed_values: dict[str, ValueChange]
    updated_profile: LearningProfile
    source_event_ids: list[str] = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def check_versions(self):
        if self.to_version != self.from_version + 1:
            raise ValueError("Learning creates exactly one new version.")
        if self.updated_profile.version != self.to_version:
            raise ValueError("Profile version must match the learning update.")
        if len(self.changed_values) != 1 or not set(self.changed_values) <= {"direct", "escort"}:
            raise ValueError("One observed transport action is updated at a time.")
        for key, change in self.changed_values.items():
            if abs(self.updated_profile.values[key] - change.new) > 1e-8:
                raise ValueError("Changed value must match the updated profile.")
        return self

class EvaluationCreateRequest(RequestBase):
    scenario_id: Literal["transport_v1"] = "transport_v1"
    seed: int = Field(ge=0, le=2147483647)

class EvaluationRunRequest(RequestBase):
    expected_evaluation_version: int = Field(ge=0)
    kind: RunKind

class EvaluationRollbackRequest(RequestBase):
    expected_evaluation_version: int = Field(ge=0)
    target: Literal["baseline"] = "baseline"

class RunView(DTO):
    run_id: str
    kind: RunKind
    world_id: str
    profile_version: int = Field(ge=0)
    status: Literal["running", "finished", "failed", "cancelled"]
    mode: Literal["live", "fallback", "mock"]
    measured: bool
    strategy: TransportStrategy | None = None
    metrics: RunMetrics | None = None
    source_event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_evidence(self):
        if self.mode == "mock" and self.measured:
            raise ValueError("MOCK cannot be a measured run.")
        if not self.measured and self.metrics is not None:
            raise ValueError("Unmeasured runs must not contain fabricated metrics.")
        if self.measured and (self.metrics is None or not self.source_event_ids):
            raise ValueError("Measured runs require metrics and source events.")
        return self

class EvaluationSession(DTO):
    evaluation_id: str
    evaluation_version: int = Field(ge=0)
    scenario_id: Literal["transport_v1"] = "transport_v1"
    seed: int
    scenario_hash: str
    snapshot_id: str
    learner_id: str
    baseline_profile_version: int = Field(ge=0)
    active_profile_version: int = Field(ge=0)
    status: EvaluationStatus
    active_world_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    mode: Literal["live", "fallback", "mock"]

class EvaluationStateData(DTO):
    session: EvaluationSession
    run: RunView | None = None
    state: StateView | None = None

class EvaluationReportData(DTO):
    session: EvaluationSession
    runs: list[RunView]
    learning_update: LearningUpdate | None = None
    comparable: bool
    improvement: Literal["not_measured", "improved", "unchanged", "worse", "incomparable"]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_comparison(self):
        if self.session.mode == "mock" and (
            self.comparable or self.improvement != "not_measured" or self.learning_update is not None
        ):
            raise ValueError("MOCK cannot claim learning or improvement.")
        if self.improvement in {"improved", "unchanged", "worse"}:
            pair = {run.kind: run for run in self.runs
                    if run.kind in ("first", "second") and run.measured}
            if not self.comparable or set(pair) != {"first", "second"}:
                raise ValueError("Comparison requires two comparable measured runs.")
        return self
