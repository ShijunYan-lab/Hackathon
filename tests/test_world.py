from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from shared.protocol import Envelope, StateView


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "worlds.sqlite3")) as value:
        yield value


def new_world(client, request_id="new"):
    result = client.post("/v1/worlds", json={"request_id": request_id, "seed": 42, "player_name": "旅人"})
    assert result.status_code == 200
    Envelope[dict].model_validate(result.json())
    return result.json()


def checkpoint(created):
    state = created["data"]["state"]
    return {"request_id": "move", "expected_world_version": state["world_version"],
            "kind": "CHECKPOINT", "payload": {"region_id": state["current_region_id"],
            "positions": [{"actor_id": state["player_id"], "tile": {"x": 9.5, "y": 8.5}}]}}


def test_real_creation_and_seeded_initialization(client):
    first, second = new_world(client), new_world(client, "another")
    a, b = first["data"]["state"], second["data"]["state"]
    StateView.model_validate(a)
    assert a["world_id"] != b["world_id"]
    assert a["actors"] == b["actors"]
    assert 5 <= len([actor for actor in a["actors"] if actor["kind"] == "npc"]) <= 7
    assert client.get("/health").json()["data"]["mode"] == "fallback"


def test_update_restart_and_durable_retry(tmp_path):
    path = tmp_path / "worlds.sqlite3"
    with TestClient(create_app(path)) as first:
        created = new_world(first)
        endpoint = f"/v1/worlds/{created['world_id']}/commands"
        body = checkpoint(created)
        updated = first.post(endpoint, json=body)
        assert updated.status_code == 200
        assert updated.json()["world_version"] == 1
    with TestClient(create_app(path)) as restarted:
        assert new_world(restarted) == created
        assert restarted.post(endpoint, json=body).json() == updated.json()
        state = restarted.get(f"/v1/worlds/{created['world_id']}/state").json()["data"]["state"]
        assert state["actors"][0]["tile"] == {"x": 9.5, "y": 8.5}
        assert state["world_version"] == 1
        events = restarted.get(f"/v1/worlds/{created['world_id']}/events").json()["data"]["events"]
        assert [event["type"] for event in events] == ["world_created", "positions_checkpointed"]


def test_concurrent_duplicate_command_once(client):
    created = new_world(client)
    path = f"/v1/worlds/{created['world_id']}/commands"
    body = checkpoint(created)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(path, json=body).json(), range(4)))
    assert all(result == results[0] for result in results)
    assert results[0]["world_version"] == 1


def test_conflicts_and_atomic_failure(client):
    created = new_world(client)
    path = f"/v1/worlds/{created['world_id']}/commands"
    body = checkpoint(created)
    body["payload"]["positions"].append({"actor_id": "missing", "tile": {"x": 1, "y": 1}})
    assert client.post(path, json=body).status_code == 404
    assert client.get(f"/v1/worlds/{created['world_id']}/state").json()["data"] == created["data"]
    body = checkpoint(created)
    assert client.post(path, json=body).status_code == 200
    body["payload"]["positions"][0]["tile"]["x"] = 10
    assert client.post(path, json=body).json()["error"]["code"] == "REQUEST_ID_REUSED"
    body["request_id"] = "other"
    assert client.post(path, json=body).json()["error"]["code"] == "VERSION_CONFLICT"


@pytest.mark.parametrize("tile", [{"x": -1, "y": 0}, {"x": 48, "y": 0}])
def test_out_of_bounds(client, tile):
    created = new_world(client)
    body = checkpoint(created)
    body["payload"]["positions"][0]["tile"] = tile
    response = client.post(f"/v1/worlds/{created['world_id']}/commands", json=body)
    assert response.status_code in (400, 422)
    Envelope[dict].model_validate(response.json())


def test_errors_and_pagination(client):
    created = new_world(client)
    world_id = created["world_id"]
    assert client.get(f"/v1/worlds/{world_id}/events?after_seq=1").json()["data"]["events"] == []
    assert client.get(f"/v1/worlds/{world_id}/events?view=debug").status_code == 403
    for result in (client.get("/missing"), client.get("/v1/worlds/missing/state"),
                   client.post("/v1/worlds", json={"request_id": "bad"}),
                   client.post("/v1/worlds", content="{", headers={"Content-Type": "application/json"})):
        Envelope[dict].model_validate(result.json())
        assert not result.json()["ok"]
    body = checkpoint(created)
    body.update(kind="CHANGE_REGION", payload={"actor_id": created["data"]["state"]["player_id"], "exit_id": "unused"})
    assert client.post(f"/v1/worlds/{world_id}/commands", json=body).json()["error"]["code"] == "ACTION_NOT_SUPPORTED"
