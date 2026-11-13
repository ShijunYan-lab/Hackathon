"""C owns regenerating this schema after an approved contract change."""
from pathlib import Path
from typing import Union
import json
from pydantic import TypeAdapter
from shared.evaluation_protocol import (
    EvaluationCreateRequest, EvaluationRunRequest, EvaluationRollbackRequest,
    EvaluationStateData, EvaluationReportData, LearningProfile, TransportContext,
    TransportChoice, TransportOutcome, LearningUpdate,
)
ALL_TYPES = Union[
    EvaluationCreateRequest, EvaluationRunRequest, EvaluationRollbackRequest,
    EvaluationStateData, EvaluationReportData, LearningProfile, TransportContext,
    TransportChoice, TransportOutcome, LearningUpdate,
]

if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "shared/evaluation_protocol.schema.json"
    path.write_text(json.dumps(TypeAdapter(ALL_TYPES).json_schema(), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print("Wrote", path.name)
