"""HTTP combat tests. Fixture-only state edits prepare otherwise unavailable tasks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from functools import partial
from pathlib import Path
from server.main import create_app as server_create_app
create_app = partial(server_create_app, regions_path=Path(__file__).parent / "fixtures/regions.json")
from server.world.combat import CombatRules
from shared.protocol import Event, ItemState, StateView, Task


@pytest.fixture
def arena(tmp_path):
    clock = [1000.0]
    path = tmp_path / "world.sqlite3"
    app = create_app(path, clock=lambda: clock[0])
    with TestClient(app) as client:
        created = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                                 "player_name": "Test"}).json()
        world_id = created["world_id"]
        yield client, app, world_id, clock, path


def current(arena):
    client, _, world_id, _, _ = arena
    return client.get(f"/v1/worlds/{world_id}/state").json()["data"]["state"]


def hit_request(state, target=None, attacker=None, attack_id=None):
    attacker = attacker or state["actors"][0]
    target = target or state["actors"][1]
    return {"request_id": uuid4().hex, "expected_world_version": state["world_version"], "kind": "HIT",
            "payload": {"attack_id": attack_id or uuid4().hex, "attacker_id": attacker["id"],
                        "target_id": target["id"], "weapon_id": attacker["equipped_item_id"],
                        "region_id": state["current_region_id"],
                        "attacker_tile": {"x": 8.5, "y": 8.5}, "target_tile": {"x": 9.5, "y": 8.5}}}


def post(arena, body):
    return arena[0].post(f"/v1/worlds/{arena[2]}/commands", json=body)


def seed_test_state(arena, modify):
    store = arena[1].state.store
    state = store.state(arena[2])
    modify(state)
    StateView.model_validate(state.model_dump())
    with store.connection(write=True) as connection:
        connection.execute("UPDATE worlds SET state=? WHERE id=?", (state.model_dump_json(), state.world_id))


def test_damage_and_request_and_attack_deduplication(arena):
    before = current(arena)
    body = hit_request(before)
    result = post(arena, body)
    assert result.status_code == 200
    data = result.json()["data"]
    damage = max(1, before["items"][0]["stats"]["damage"] - before["actors"][1]["armor"])
    assert data["state"]["actors"][1]["hp"] == before["actors"][1]["hp"] - damage
    assert post(arena, body).json() == result.json()
    body["request_id"] = uuid4().hex
    duplicate = post(arena, body).json()
    assert duplicate["data"]["command_result"]["applied"] is False
    assert duplicate["world_version"] == 1
    assert duplicate["data"]["events"] == []
    assert current(arena) == data["state"]


def test_same_swing_multiple_targets_and_next_swing_cooldown(arena):
    state = current(arena)
    first = hit_request(state, attack_id="swing")
    assert post(arena, first).status_code == 200
    state = current(arena)
    second = hit_request(state, target=state["actors"][2], attack_id="swing")
    assert post(arena, second).status_code == 200
    next_swing = hit_request(current(arena))
    assert post(arena, next_swing).json()["error"]["code"] == "ATTACK_COOLDOWN"
    arena[3][0] += .5
    assert post(arena, next_swing).status_code == 200
    state = current(arena)
    stale_swing = hit_request(state, target=state["actors"][3], attack_id="swing")
    assert post(arena, stale_swing).json()["error"]["code"] == "ATTACK_EXPIRED"


def test_expired_swing_and_reused_identity(arena):
    first = hit_request(current(arena), attack_id="swing")
    assert post(arena, first).status_code == 200
    state = current(arena)
    reused = hit_request(state, attacker=state["actors"][2], attack_id="swing")
    assert post(arena, reused).json()["error"]["code"] == "ATTACK_ID_REUSED"
    arena[3][0] += 1
    expired = hit_request(state, target=state["actors"][2], attack_id="swing")
    assert post(arena, expired).json()["error"]["code"] == "ATTACK_EXPIRED"


@pytest.mark.parametrize("mutation,code", [
    ({"target_id": "missing"}, "ACTOR_NOT_FOUND"),
    ({"weapon_id": "missing"}, "ITEM_NOT_OWNED"),
    ({"region_id": "moonwood"}, "OUT_OF_RANGE"),
    ({"target_tile": {"x": 15, "y": 15}}, "OUT_OF_RANGE"),
    ({"attacker_tile": {"x": 99, "y": 99}, "target_tile": {"x": 99, "y": 99}}, "OUT_OF_RANGE"),
    ({"attack_id": " "}, "PRECONDITION_FAILED"),
])
def test_invalid_hits_do_not_write(arena, mutation, code):
    state = current(arena)
    body = hit_request(state)
    body["payload"].update(mutation)
    assert post(arena, body).json()["error"]["code"] == code
    assert current(arena) == state
    assert arena[1].state.store.events(arena[2], 0, 100, True)["data"]["events"][0]["type"] == "world_created"


def test_wrong_owner_equipment_self_hit_and_extra_damage(arena):
    state = current(arena)
    body = hit_request(state)
    body["payload"]["weapon_id"] = state["actors"][1]["equipped_item_id"]
    assert post(arena, body).json()["error"]["code"] == "ITEM_NOT_OWNED"
    body = hit_request(state, target=state["actors"][0])
    assert post(arena, body).json()["error"]["code"] == "PRECONDITION_FAILED"
    body = hit_request(state)
    body["payload"]["damage"] = 999
    assert post(arena, body).status_code == 422
    seed_test_state(arena, lambda value: setattr(value.actors[0], "equipped_item_id", None))
    body = hit_request(state)
    assert post(arena, body).json()["error"]["code"] == "PRECONDITION_FAILED"


def test_minimum_damage_and_causal_cleanup(arena):
    def prepare(state):
        state.actors[1].hp = 1
        state.actors[1].armor = 100
        state.tasks = [Task(id="task_a", actor_id=state.actors[1].id, kind="MOVE", status="running",
                            started_tick=0, source_event_ids=[]),
                       Task(id="task_b", actor_id=state.actors[2].id, target_id=state.actors[1].id,
                            kind="ESCORT", status="pending", started_tick=0, source_event_ids=[])]
        state.actors[1].task_id = "task_a"
        state.actors[2].task_id = "task_b"
        state.actors[2].behavior = "moving"
    seed_test_state(arena, prepare)
    before = current(arena)
    target_id = before["actors"][1]["id"]
    weapon_id = before["actors"][1]["equipped_item_id"]
    result = post(arena, hit_request(before)).json()
    state = result["data"]["state"]
    dead = state["actors"][1]
    assert dead["hp"] == 0 and dead["alive"] is False and dead["behavior"] == "dead"
    assert dead["org_ids"] == [] and dead["equipped_item_id"] is None
    assert all(task["status"] == "cancelled" for task in state["tasks"])
    assert state["actors"][2]["task_id"] is None and state["actors"][2]["behavior"] == "idle"
    dropped = next(item for item in state["items"] if item["id"] == weapon_id)
    assert dropped["owner_id"] is None and dropped["tile"] == dead["tile"]
    assert len(state["items"]) == len(before["items"])
    org = state["organizations"][0]
    assert target_id not in org["member_ids"] and org["representative_id"] in org["member_ids"]
    events = result["data"]["events"]
    assert events[0]["facts"]["damage"] == 1
    known_ids = set()
    for event in events:
        Event.model_validate(event)
        assert set(event["caused_by"]) <= known_ids
        known_ids.add(event["id"])
    assert post(arena, hit_request(state)).json()["error"]["code"] == "NPC_DEAD"
    attacker_body = hit_request(state, attacker=before["actors"][1], target=state["actors"][0])
    assert post(arena, attacker_body).json()["error"]["code"] == "NPC_DEAD"
    checkpoint = {"request_id": uuid4().hex, "expected_world_version": state["world_version"],
                  "kind": "CHECKPOINT", "payload": {"region_id": state["current_region_id"],
                  "positions": [{"actor_id": target_id, "tile": {"x": 10, "y": 10}}]}}
    assert post(arena, checkpoint).json()["error"]["code"] == "NPC_DEAD"


def test_last_member_death_and_witness_radius(arena):
    def prepare(state):
        target = state.actors[1]
        target.hp = 1
        state.organizations[0].member_ids = [target.id]
        for actor in state.actors[2:]:
            actor.tile.x = 40
            actor.tile.y = 25
            actor.org_ids = []
    seed_test_state(arena, prepare)
    data = post(arena, hit_request(current(arena))).json()["data"]
    assert data["state"]["organizations"][0]["status"] == "inactive"
    assert data["state"]["organizations"][0]["representative_id"] is None
    assert set(data["events"][0]["witness_ids"]) == {actor["id"] for actor in data["state"]["actors"][:2]}


def test_player_recovers_and_material_loss_is_deterministic(arena):
    def prepare(state):
        state.actors[0].hp = 1
        for index in range(3):
            state.items.append(ItemState(id=f"material_{index}", name="材料", base_type="material",
                quality="common", material_id="iron", stats={"damage": 0, "cooldown_s": 1, "armor": 0},
                owner_id=state.player_id))
    seed_test_state(arena, prepare)
    state = current(arena)
    body = hit_request(state, attacker=state["actors"][1], target=state["actors"][0])
    data = post(arena, body).json()["data"]
    player = data["state"]["actors"][0]
    assert player["alive"] and player["hp"] == player["max_hp"]
    assert player["tile"] == {"x": 8.5, "y": 8.5}
    assert player["equipped_item_id"] == state["actors"][0]["equipped_item_id"]
    assert len([item for item in data["state"]["items"] if item["owner_id"] is None]) == 2
    assert "player_recovered" in [event["type"] for event in data["events"]]
    body["request_id"] = uuid4().hex
    assert post(arena, body).json()["data"]["command_result"]["applied"] is False


def test_atomic_rollback_after_event_write_failure(arena, monkeypatch):
    state = current(arena)
    original = arena[1].state.store.append_event
    def fail(*args):
        raise RuntimeError("synthetic storage failure")
    monkeypatch.setattr(arena[1].state.store, "append_event", fail)
    body = hit_request(state)
    with pytest.raises(RuntimeError):
        post(arena, body)
    assert current(arena) == state
    monkeypatch.setattr(arena[1].state.store, "append_event", original)
    assert post(arena, body).status_code == 200


def test_parallel_duplicate_attack_and_restart(arena):
    body = hit_request(current(arena))
    bodies = [dict(deepcopy(body), request_id=uuid4().hex) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda value: post(arena, value).json(), bodies))
    assert sum(result["data"]["command_result"]["applied"] for result in results) == 1
    with TestClient(create_app(arena[4], clock=lambda: arena[3][0])) as restarted:
        body["request_id"] = uuid4().hex
        result = restarted.post(f"/v1/worlds/{arena[2]}/commands", json=body).json()
        assert result["world_version"] == 1
        assert result["data"]["command_result"]["applied"] is False
        fresh = hit_request(current(arena))
        assert restarted.post(f"/v1/worlds/{arena[2]}/commands", json=fresh).json()["error"]["code"] == "ATTACK_COOLDOWN"


def test_world_rule_snapshot_survives_restart(arena):
    with TestClient(create_app(arena[4], combat_rules=CombatRules(melee_range_tiles=.5))) as restarted:
        body = hit_request(current(arena))
        assert restarted.post(f"/v1/worlds/{arena[2]}/commands", json=body).status_code == 200


def test_death_and_original_drop_persist_on_restart(arena):
    seed_test_state(arena, lambda state: setattr(state.actors[1], "hp", 1))
    body = hit_request(current(arena))
    original = post(arena, body).json()
    with TestClient(create_app(arena[4])) as restarted:
        path = f"/v1/worlds/{arena[2]}"
        state = restarted.get(path + "/state").json()["data"]["state"]
        assert state == original["data"]["state"]
        assert state["actors"][1]["alive"] is False
        assert restarted.post(path + "/commands", json=body).json() == original
        assert sum(item["owner_id"] is None for item in state["items"]) == 1


def test_old_world_without_rule_snapshot_is_supported(arena):
    store = arena[1].state.store
    with store.connection(write=True) as connection:
        connection.execute("DELETE FROM world_combat_rules WHERE world_id=?", (arena[2],))
    body = hit_request(current(arena))
    assert post(arena, body).status_code == 200
    with store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM world_combat_rules WHERE world_id=?",
                                  (arena[2],)).fetchone()[0] == 1


def test_hit_into_blocked_tile_fails_atomically(arena):
    import json
    store = arena[1].state.store
    with store.connection(write=True) as connection:
        row = store.world_row(connection, arena[2])
        region = json.loads(row["region"])
        region["blocked_tiles"] = [[9, 8]]
        connection.execute("UPDATE worlds SET region=? WHERE id=?", (json.dumps(region), arena[2]))
    state = current(arena)
    assert post(arena, hit_request(state)).json()["error"]["code"] == "OUT_OF_RANGE"
    assert current(arena) == state
