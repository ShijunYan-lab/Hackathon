"""Validate evaluation examples; this does not run any learning or game logic."""
from pathlib import Path
import json
from shared.protocol import Envelope
from shared.evaluation_protocol import (
    EvaluationCreateRequest, EvaluationRunRequest, EvaluationRollbackRequest,
    EvaluationStateData, EvaluationReportData, LearningProfile,
)
ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = {
    "create_request.json": EvaluationCreateRequest,
    "run_request.json": EvaluationRunRequest,
    "rollback_request.json": EvaluationRollbackRequest,
    "session_response.json": Envelope[EvaluationStateData],
    "report_response.json": Envelope[EvaluationReportData],
    "profile_initial.json": LearningProfile,
}

def check() -> int:
    for name, model in EXAMPLES.items():
        model.model_validate(json.loads((ROOT / "examples/evaluation" / name).read_text(encoding="utf-8")))
        print("OK:", name)
    print(f"{len(EXAMPLES)} evaluation examples validated. No real runs were executed.")
    return len(EXAMPLES)

if __name__ == "__main__":
    check()
