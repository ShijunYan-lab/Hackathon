"""Validate bundled JSON examples against protocol DTOs."""
import json
from pathlib import Path
from shared.protocol import NewWorldRequest, DialogueRequest, CommandRequest, AdvanceRequest, AgentDecision, Envelope, StateView
ROOT = Path(__file__).resolve().parents[1]
models = {"new_world_request": NewWorldRequest, "dialogue_request": DialogueRequest,
          "hit_request": CommandRequest, "advance_request": AdvanceRequest,
          "agent_decision": AgentDecision, "state_response": Envelope[dict], "dialogue_response": Envelope[dict],
          "advance_response": Envelope[dict], "error_response": Envelope[dict]}
for name, model in models.items():
    data = json.loads((ROOT / "examples" / (name + ".json")).read_text(encoding="utf-8"))
    obj = model.model_validate(data)
    if name.endswith("_response") and obj.ok and "state" in obj.data:
        StateView.model_validate(obj.data["state"])
    print("PASS", name)
print("Format checks only; game-rule and Windows integration checks are still required.")
