from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app


def test_item_transfer_equipment_and_restart(tmp_path):
    path = tmp_path / "world.sqlite3"
    with TestClient(create_app(path)) as client:
        state = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                              "player_name": "Test"}).json()["data"]["state"]
        route = f"/v1/worlds/{state['world_id']}/commands"
        player, npc = state["actors"][:2]
        def command(kind, payload):
            nonlocal state
            body = {"request_id": uuid4().hex, "expected_world_version": state["world_version"],
                    "kind": kind, "payload": payload}
            result = client.post(route, json=body)
            assert result.status_code == 200, result.text
            state = result.json()["data"]["state"]
            assert client.post(route, json=body).json() == result.json()
        command("CHECKPOINT", {"region_id": player["region_id"], "positions": [
            {"actor_id": npc["id"], "tile": player["tile"]}]})
        item = next(item for item in state["items"] if item["id"] == npc["equipped_item_id"])
        command("GIVE", {"actor_id": npc["id"], "target_id": player["id"], "item_id": item["id"]})
        assert state["actors"][1]["equipped_item_id"] is None
        assert state["actors"][1]["armor"] == 0
        command("EQUIP", {"actor_id": player["id"], "item_id": item["id"]})
        command("EQUIP", {"actor_id": player["id"], "item_id": item["id"]})
        assert state["actors"][0]["armor"] == item["stats"]["armor"]
        assert len({value["id"] for value in state["items"]}) == len(state["items"])
        route_state = f"/v1/worlds/{state['world_id']}/state"
    with TestClient(create_app(path)) as restarted:
        assert restarted.get(route_state).json()["data"]["state"] == state


def test_pickup_race_and_invalid_owner(tmp_path):
    app = create_app(tmp_path / "world.sqlite3")
    with TestClient(app) as client:
        state = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                              "player_name": "Test"}).json()["data"]["state"]
        world_id = state["world_id"]
        store = app.state.store
        model = store.state(world_id)
        # A synthetic ground item isolates pickup from combat's already-tested drop path.
        model.items[0] = model.items[0].model_copy(update={"owner_id": None,
            "region_id": model.current_region_id, "tile": model.actors[0].tile})
        model.actors[0].equipped_item_id = None
        with store.connection(write=True) as connection:
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (model.model_dump_json(), world_id))
        route = f"/v1/worlds/{world_id}/commands"
        body = {"request_id": "pickup", "expected_world_version": 0, "kind": "PICKUP",
                "payload": {"actor_id": model.player_id, "item_id": model.items[0].id}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: client.post(route, json=body).json(), range(2)))
        assert results[0] == results[1]
        body.update(request_id="again", expected_world_version=1)
        assert client.post(route, json=body).json()["error"]["code"] == "ITEM_NOT_ON_GROUND"
        body.update(kind="EQUIP", request_id="steal")
        body["payload"]["actor_id"] = model.actors[1].id
        assert client.post(route, json=body).json()["error"]["code"] == "ITEM_NOT_OWNED"


def test_give_out_of_range_has_no_side_effects(tmp_path):
    with TestClient(create_app(tmp_path / "world.sqlite3")) as client:
        state = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                              "player_name": "Test"}).json()["data"]["state"]
        route = f"/v1/worlds/{state['world_id']}"
        body = {"request_id": "give", "expected_world_version": 0, "kind": "GIVE",
                "payload": {"actor_id": state["player_id"], "target_id": state["actors"][1]["id"],
                            "item_id": state["items"][0]["id"]}}
        assert client.post(route + "/commands", json=body).json()["error"]["code"] == "OUT_OF_RANGE"
        assert client.get(route + "/state").json()["data"]["state"] == state
