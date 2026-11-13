from copy import deepcopy
from uuid import uuid4
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from shared.protocol import (CommandRequest, AgentDecision, ActorState,
    StateView, ItemState, Envelope)
from tools.mock_api import app

client = TestClient(app)

def new_world():
    body = {"request_id": "req_" + uuid4().hex, "seed": 42, "player_name": "Tester"}
    r = client.post("/v1/worlds", json=body)
    assert r.status_code == 200
    return r.json(), body

def test_health_mock_label():
    assert client.get("/health").json()["data"]["mode"] == "mock"

def test_new_state_valid():
    response, _ = new_world()
    Envelope[dict].model_validate(response)
    StateView.model_validate(response["data"]["state"])

def test_new_request_idempotency():
    first, body = new_world()
    assert client.post("/v1/worlds", json=body).json() == first

def test_request_id_content_mismatch():
    _, body = new_world()
    body["seed"] = 99
    assert client.post("/v1/worlds", json=body).status_code == 409

def test_version_conflict():
    response, _ = new_world()
    r = client.post(f"/v1/worlds/{response['world_id']}/advance", json={
        "request_id": uuid4().hex, "expected_world_version": 99,
        "reason": "debug_step", "trigger_event_ids": []})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "VERSION_CONFLICT"

def test_bad_command_is_wrapped():
    response, _ = new_world()
    r = client.post(f"/v1/worlds/{response['world_id']}/commands", json={
        "request_id": uuid4().hex, "expected_world_version": 0,
        "kind": "CREATE_GOD_WEAPON", "payload": {}})
    assert r.status_code == 422
    Envelope[dict].model_validate(r.json())

def test_hit_requires_fields():
    with pytest.raises(ValidationError):
        CommandRequest.model_validate({"request_id": "x", "expected_world_version": 0,
                                       "kind": "HIT", "payload": {}})

def test_hit_rejects_arbitrary_reward():
    with pytest.raises(ValidationError):
        CommandRequest.model_validate({"request_id": "x", "expected_world_version": 0,
            "kind": "PICKUP", "payload": {"actor_id": "player_01", "item_id": "i", "reward": 999}})

def test_dialogue_marks_mock_and_does_not_run_action():
    response, _ = new_world()
    data = client.post(f"/v1/worlds/{response['world_id']}/dialogue", json={
        "request_id": uuid4().hex, "expected_world_version": 0,
        "npc_id": "npc_02", "text": "Please help me."}).json()["data"]
    assert data["mode"] == "mock" and data["task_ids"] == []

def test_commands_mock_does_not_damage():
    response, _ = new_world()
    data = client.post(f"/v1/worlds/{response['world_id']}/commands", json={
        "request_id": uuid4().hex, "expected_world_version": 0,
        "kind": "EQUIP", "payload": {"actor_id": "player_01", "item_id": "item_01"}}).json()["data"]
    assert data["command_result"]["applied"] is False
    assert data["state"]["world_version"] == 0

def test_save_load_branch():
    response, _ = new_world()
    saved = client.post(f"/v1/worlds/{response['world_id']}/saves", json={
        "request_id": uuid4().hex, "expected_world_version": 0, "label": "test"}).json()["data"]
    loaded = client.post(f"/v1/saves/{saved['save_id']}/load", json={"request_id": uuid4().hex}).json()
    assert loaded["world_id"] != response["world_id"]
    StateView.model_validate(loaded["data"]["state"])

def test_event_pagination():
    response, _ = new_world()
    path = f"/v1/worlds/{response['world_id']}/events"
    assert len(client.get(path).json()["data"]["events"]) == 1
    assert client.get(path + "?after_seq=1").json()["data"]["events"] == []

def test_private_action_cannot_spawn_item():
    with pytest.raises(ValidationError):
        AgentDecision.model_validate({"intent": {"action": "CREATE_ANYTHING"}})

def test_memory_requires_source():
    with pytest.raises(ValidationError):
        AgentDecision.model_validate({"memory_proposals": [{"statement": "test",
            "source_type": "report", "source_event_ids": [], "confidence": .5,
            "status": "unverified"}]})

def test_dead_actor_cannot_have_positive_hp():
    with pytest.raises(ValidationError):
        ActorState.model_validate({"id": "n", "kind": "npc", "name": "N", "alive": False,
            "hp": 10, "max_hp": 40, "armor": 0, "region_id": "market",
            "tile": {"x": 1, "y": 1}, "appearance_key": "n"})

def test_owned_item_cannot_also_be_on_ground():
    with pytest.raises(ValidationError):
        ItemState.model_validate({"id": "i", "name": "I", "base_type": "sword",
            "quality": "common", "material_id": "iron", "stats": {
            "damage": 6, "cooldown_s": .5, "armor": 0}, "owner_id": "p",
            "region_id": "market", "tile": {"x": 1, "y": 1}})
