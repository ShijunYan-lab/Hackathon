"""DTO/fixture tests only. These do NOT claim a working learning implementation."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from pydantic import ValidationError
from shared.protocol import Envelope
from shared.evaluation_protocol import (
    EvaluationCreateRequest, EvaluationRunRequest, EvaluationRollbackRequest,
    EvaluationStateData, EvaluationReportData, LearningProfile, RunMetrics,
    RunView, TransportContext, LearningUpdate,
)
from tools.check_evaluation_contracts import EXAMPLES

ROOT = Path(__file__).resolve().parents[1]

def fixture(name):
    return json.loads((ROOT / "examples/evaluation" / name).read_text(encoding="utf-8"))

@pytest.mark.parametrize("name", list(EXAMPLES))
def test_evaluation_fixture_matches_contract(name):
    EXAMPLES[name].model_validate(fixture(name))

def test_profile_cannot_retrieve_future_memory():
    data = fixture("profile_initial.json")
    data["memories"] = [{
        "id": "mem_future", "statement": "Test future memory",
        "source_run_id": "run_test", "source_event_ids": ["evt_test"], "profile_version": 1
    }]
    with pytest.raises(ValidationError):
        LearningProfile.model_validate(data)

def test_profile_requires_exact_transport_actions():
    data = fixture("profile_initial.json")
    data["values"]["invent_victory"] = 1
    with pytest.raises(ValidationError):
        LearningProfile.model_validate(data)

def test_context_cannot_offer_unavailable_escort():
    with pytest.raises(ValidationError):
        TransportContext.model_validate({
            "learner_id":"npc_test", "context_key":"greenwood_delivery",
            "available_strategies":["direct","escort"], "own_gold":1,
            "escort_cost":5, "guard_id":"npc_guard", "known_event_ids":[]
        })

def metrics():
    # Synthetic unit-test input, not measured gameplay.
    return dict(cargo_initial=10, cargo_delivered=4, gold_initial=20, gold_spent=0,
                duration_ms=100, merchant_survived=True, task_success=False,
                delivered_ratio=.4, reward=.4)

def test_metrics_must_agree_with_raw_counts():
    data = metrics()
    data["delivered_ratio"] = .9
    with pytest.raises(ValidationError):
        RunMetrics.model_validate(data)

def test_reward_includes_cost():
    data = metrics()
    data.update(gold_spent=10, reward=.35)
    assert RunMetrics.model_validate(data).reward == .35

def test_mock_cannot_claim_a_measurement():
    with pytest.raises(ValidationError):
        RunView.model_validate({
            "run_id":"test", "kind":"first","world_id":"test","profile_version":0,
            "status":"finished","mode":"mock","measured":True,
            "strategy":"direct","metrics":metrics(),"source_event_ids":["evt_test"]
        })

def test_unmeasured_run_cannot_contain_scores():
    with pytest.raises(ValidationError):
        RunView.model_validate({
            "run_id":"test", "kind":"first","world_id":"test","profile_version":0,
            "status":"finished","mode":"fallback","measured":False,
            "metrics":metrics(),"source_event_ids":[]
        })

def test_report_cannot_claim_improvement_without_two_runs():
    data = fixture("report_response.json")["data"]
    data["session"]["mode"] = "fallback"
    data["comparable"] = True
    data["improvement"] = "improved"
    with pytest.raises(ValidationError):
        EvaluationReportData.model_validate(data)

def test_mock_report_contains_no_fake_learning():
    report = Envelope[EvaluationReportData].model_validate(fixture("report_response.json"))
    assert report.data.learning_update is None
    assert report.data.improvement == "not_measured"
    assert report.data.comparable is False

def test_run_request_cannot_contain_manual_policy_overrides():
    data = fixture("run_request.json")
    data["q_values"] = {"direct":0, "escort":1}
    with pytest.raises(ValidationError):
        EvaluationRunRequest.model_validate(data)

def test_rollback_cannot_set_arbitrary_parameters():
    data = fixture("rollback_request.json")
    data["alpha"] = 1
    with pytest.raises(ValidationError):
        EvaluationRollbackRequest.model_validate(data)

def test_learning_update_increments_one_version():
    profile = fixture("profile_initial.json")
    profile["version"] = 1
    profile["values"]["direct"] = .28
    update = dict(
        source_run_id="run_test", from_version=0, to_version=1,
        changed_values={"direct":{"old":.6, "new":.28}},
        updated_profile=profile, source_event_ids=["evt_test"],
        explanation="Synthetic unit-test update, not a gameplay result."
    )
    assert LearningUpdate.model_validate(update).to_version == 1
    bad = deepcopy(update)
    bad["to_version"] = 3
    with pytest.raises(ValidationError):
        LearningUpdate.model_validate(bad)
