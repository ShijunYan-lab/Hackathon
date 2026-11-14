import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
from uuid import uuid4

from fastapi.testclient import TestClient

from server.main import create_app
from shared.protocol import AgentDecision


def prepare(client):
    state = client.post("/v1/worlds", json={"request_id": uuid4().hex, "seed": 42,
                                          "player_name": "Test"}).json()["data"]["state"]
    path = f"/v1/worlds/{state['world_id']}"
    npc = state["actors"][1]
    body = {"request_id": uuid4().hex, "expected_world_version": 0, "kind": "CHECKPOINT",
            "payload": {"region_id": state["current_region_id"], "positions": [
                {"actor_id": npc["id"], "tile": state["actors"][0]["tile"]}]}}
    state = client.post(path + "/commands", json=body).json()["data"]["state"]
    dialogue = {"request_id": uuid4().hex, "expected_world_version": state["world_version"],
                "npc_id": npc["id"], "text": "请去采一份草药"}
    return path, state, dialogue


async def gather_provider(context, text):
    site = next(entity for entity in context.known_entities if entity.get("kind") == "herb")
    return AgentDecision(reply="我去看看。", intent={"action": "GATHER", "target_id": site["id"]},
        memory_proposals=[{"statement": "旅人请求采集", "source_type": "report", "confidence": .6,
                           "status": "unverified", "source_event_ids": [context.known_events[-1].id]}])


def test_dialogue_gather_and_single_completion(tmp_path):
    db = tmp_path / "world.sqlite3"
    with TestClient(create_app(db, dialogue_provider=gather_provider, allow_debug=True)) as client:
        path, before, request = prepare(client)
        response = client.post(path + "/dialogue", json=request)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["intent_status"] == "scheduled"
        assert len(data["state"]["items"]) == len(before["items"])
        assert client.post(path + "/dialogue", json=request).json() == response.json()
        task = data["state"]["tasks"][0]
        report = {"request_id": uuid4().hex, "expected_world_version": data["state"]["world_version"],
                  "kind": "TASK_REPORT", "payload": {"task_id": task["id"], "actor_id": task["actor_id"],
                  "status": "succeeded", "region_id": task["target_region_id"], "tile": {"x": 1, "y": 1}}}
        assert client.post(path + "/commands", json=report).status_code == 400
        report["payload"]["tile"] = task["target_tile"]
        completed = client.post(path + "/commands", json=report).json()
        assert completed["ok"]
        state = completed["data"]["state"]
        assert state["sites"][0]["remaining"] == before["sites"][0]["remaining"] - 1
        assert len(state["items"]) == len(before["items"]) + 1
        assert client.post(path + "/commands", json=report).json() == completed
        report.update(request_id=uuid4().hex, expected_world_version=state["world_version"])
        duplicate = client.post(path + "/commands", json=report).json()
        assert duplicate["data"]["command_result"]["applied"] is False
        assert duplicate["world_version"] == state["world_version"]
        debug = client.get(path + f"/agents/{request['npc_id']}/debug").json()["data"]
        assert debug["decision_history"][0]["intent_status"] == "scheduled"
    with TestClient(create_app(db)) as restarted:
        assert restarted.get(path + "/state").json()["data"]["state"] == state


def test_bad_memory_rejects_whole_decision(tmp_path):
    async def invalid(context, text):
        result = await gather_provider(context, text)
        result.memory_proposals[0].source_event_ids = ["evt_unknown"]
        return result
    with TestClient(create_app(tmp_path / "world.sqlite3", dialogue_provider=invalid)) as client:
        path, state, body = prepare(client)
        data = client.post(path + "/dialogue", json=body).json()["data"]
        assert data["intent_status"] == "rejected"
        assert data["state"]["tasks"] == []
        assert data["state"]["items"] == state["items"]


def test_provider_failure_and_timeout_are_fallback(tmp_path):
    async def slow(context, text):
        await asyncio.sleep(1)
    with TestClient(create_app(tmp_path / "world.sqlite3", dialogue_provider=slow,
                              agent_timeout_s=.01)) as client:
        path, _, body = prepare(client)
        data = client.post(path + "/dialogue", json=body).json()["data"]
        assert data["mode"] == "fallback" and data["task_ids"] == []


def test_in_flight_dedup_and_concurrent_death(tmp_path):
    entered, release = threading.Event(), threading.Event()
    calls = []
    async def waiting(context, text):
        calls.append(context)
        entered.set()
        while not release.is_set():
            await asyncio.sleep(.01)
        return await gather_provider(context, text)
    app = create_app(tmp_path / "world.sqlite3", dialogue_provider=waiting)
    with TestClient(app) as client:
        path, state, body = prepare(client)
        model = app.state.store.state(state["world_id"])
        model.actors[1].hp = 1
        with app.state.store.connection(write=True) as connection:
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (model.model_dump_json(), model.world_id))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(client.post, path + "/dialogue", json=body)
            try:
                assert entered.wait(3)
                assert client.post(path + "/dialogue", json=body).json()["error"]["code"] == "REQUEST_IN_PROGRESS"
                hit = {"request_id": uuid4().hex, "expected_world_version": state["world_version"], "kind": "HIT",
                       "payload": {"attack_id": uuid4().hex, "attacker_id": state["player_id"],
                       "target_id": body["npc_id"], "weapon_id": state["actors"][0]["equipped_item_id"],
                       "region_id": state["current_region_id"], "attacker_tile": {"x": 8.5, "y": 8.5},
                       "target_tile": {"x": 9.5, "y": 8.5}}}
                assert client.post(path + "/commands", json=hit).status_code == 200
            finally:
                release.set()
            assert future.result().json()["error"]["code"] == "VERSION_CONFLICT"
        final = client.get(path + "/state").json()["data"]["state"]
        assert not final["actors"][1]["alive"] and final["tasks"] == []
        assert len(calls) == 1
