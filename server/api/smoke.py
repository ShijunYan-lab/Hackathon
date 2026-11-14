"""Exercise the running local service: python -m server.api.smoke."""
import json
import os
from urllib.request import Request, urlopen
from uuid import uuid4

BASE_URL = os.environ.get('WORLD_API_URL', 'http://127.0.0.1:8765').rstrip('/')


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(BASE_URL + path, data=data,
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
    assert result["ok"], result
    return result


def main():
    health = call("/health")["data"]
    assert "persistent_worlds" in health["capabilities"]
    created = call("/v1/worlds", {"request_id": "demo_" + uuid4().hex,
                   "seed": 20261113, "player_name": "旅人"})
    state = created["data"]["state"]
    path = "/v1/worlds/" + state["world_id"]
    tile = dict(state["actors"][0]["tile"])
    tile["x"] += 1
    command = {"request_id": "demo_" + uuid4().hex, "expected_world_version": state["world_version"],
               "kind": "CHECKPOINT", "payload": {"region_id": state["current_region_id"],
               "positions": [{"actor_id": state["player_id"], "tile": tile}]}}
    moved = call(path + "/commands", command)
    assert call(path + "/commands", command) == moved
    saved = call(path + "/state")["data"]["state"]
    assert saved["actors"][0]["tile"] == tile
    events = call(path + "/events")["data"]["events"]
    assert len(events) == 1
    print(json.dumps({"result": "PASS", "mode": health["mode"], "world_id": state["world_id"],
                      "world_version": saved["world_version"], "event_count": len(events),
                      "state_url": BASE_URL + path + "/state"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
