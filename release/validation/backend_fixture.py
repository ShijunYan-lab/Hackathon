"""Isolated Godot HTTP QA server. Deterministic providers are TEST DOUBLES only."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import uvicorn
from server.main import create_app
from server.world.director import DirectorConfig
from server.evaluation.scenario import TransportScenario
from shared.protocol import Tile, AgentDecision

async def dialogue(context, text):
    if text == "QA_MOVE":
        target = next(value for value in context.known_entities if value.get("id") != context.npc_id and value.get("kind") == "player")
        return AgentDecision(reply="QA test double: moving to your recorded position.", intent={"action":"MOVE", "target_id":target["id"]})
    raise RuntimeError("QA intentionally exercises honest fallback")

async def plan(context, reason):
    return AgentDecision(reply="QA wait", intent={"action":"WAIT"})

app = create_app(db_path=ROOT / "runtime/qa-overworld-20261114.sqlite3",
    regions_path=ROOT / "game/maps/backend_world.json", region_id="overworld",
    dialogue_provider=dialogue, plan_provider=plan,
    director_config=DirectorConfig(enabled=False),
    transport_scenario=TransportScenario(start=Tile(x=120.5,y=143.5),destination=Tile(x=140.5,y=143.5),threat=Tile(x=130.5,y=143.5)))
if __name__ == "__main__": uvicorn.run(app,host="127.0.0.1",port=8766,log_level="warning")
