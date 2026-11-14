"""D's continuous-map composition root. Does not modify the standalone C server."""
from pathlib import Path
import argparse
import sys
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server.main import create_app
from server.world.director import DirectorConfig
from server.evaluation.scenario import TransportScenario
from shared.protocol import Tile


def make_app(db_path=None):
    load_dotenv(ROOT / '.env', override=False)
    return create_app(db_path=db_path or ROOT / "runtime/overworld.sqlite3",
        agent_timeout_s=min(65, max(1, float(os.getenv('LLM_TIMEOUT_SECONDS', '30')) * 2 + 3)),
        regions_path=ROOT / "game/maps/backend_world.json", region_id="overworld",
        director_config=DirectorConfig.from_file(ROOT / "game/maps/director_locations.json"),
        transport_scenario=TransportScenario(start=Tile(x=120.5, y=143.5),
            destination=Tile(x=140.5, y=143.5), threat=Tile(x=130.5, y=143.5)))


if __name__ == "__main__":
    if sys.stdout is None or sys.stderr is None:
        (ROOT / "runtime").mkdir(exist_ok=True)
        sys.stdout = sys.stderr = open(ROOT / "runtime/backend.log", "a", encoding="utf-8", buffering=1)
    import uvicorn
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db")
    args = parser.parse_args()
    uvicorn.run(make_app(args.db), host="127.0.0.1", port=args.port, log_level="warning")
