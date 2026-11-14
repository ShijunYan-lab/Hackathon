"""Run HTTP combat checks with synthetic collision reports, without Godot."""
import json
import time
from pathlib import Path
from uuid import uuid4

from server.api.smoke import call


def main():
    health = call("/health")["data"]
    assert "death_cleanup" in health["capabilities"]
    created = call("/v1/worlds", {"request_id": "combat_demo_" + uuid4().hex,
                   "seed": 20261113, "player_name": "战斗接口验证"})
    state = created["data"]["state"]
    path = "/v1/worlds/" + state["world_id"]
    player = state["actors"][0]
    target = state["actors"][1]
    target_id, target_weapon_id = target["id"], target["equipped_item_id"]
    weapon = next(item for item in state["items"] if item["id"] == player["equipped_item_id"])
    hit_count = 0
    while target["alive"]:
        body = {"request_id": uuid4().hex, "expected_world_version": state["world_version"], "kind": "HIT",
                "payload": {"attack_id": uuid4().hex, "attacker_id": player["id"], "target_id": target_id,
                            "weapon_id": weapon["id"], "region_id": state["current_region_id"],
                            "attacker_tile": {"x": 8.5, "y": 8.5}, "target_tile": {"x": 9.5, "y": 8.5}}}
        before_hp = target["hp"]
        result = call(path + "/commands", body)
        assert call(path + "/commands", body) == result
        duplicate_body = dict(body, request_id=uuid4().hex)
        duplicate = call(path + "/commands", duplicate_body)
        assert duplicate["data"]["command_result"]["applied"] is False
        assert duplicate["world_version"] == result["world_version"]
        state = result["data"]["state"]
        target = next(actor for actor in state["actors"] if actor["id"] == target_id)
        hit_count += 1
        print(f"Hit {hit_count}: HP {before_hp} -> {target['hp']}; duplicate ignored")
        if target["alive"]:
            time.sleep(weapon["stats"]["cooldown_s"] + .05)
    dropped = next(item for item in state["items"] if item["id"] == target_weapon_id)
    assert dropped["owner_id"] is None
    assert target["behavior"] == "dead" and target["org_ids"] == []
    assert all(target_id not in org["member_ids"] for org in state["organizations"])
    events = call(path + "/events", None)["data"]["events"]
    assert sum(event["type"] == "actor_died" for event in events) == 1
    assert sum(event["type"] == "hit_applied" for event in events) == hit_count
    report = {"result": "PASS", "execution": "HTTP_SYNTHETIC_COLLISION_REPORTS", "world_id": state["world_id"],
              "target_id": target_id, "hp": target["hp"], "alive": target["alive"],
              "dropped_item_id": target_weapon_id, "hits": hit_count,
              "state_url": "http://127.0.0.1:8765" + path + "/state",
              "events_url": "http://127.0.0.1:8765" + path + "/events"}
    runtime = Path(__file__).resolve().parents[2] / "runtime"
    runtime.mkdir(exist_ok=True)
    (runtime / "combat_demo.json").write_text(json.dumps({"report": report, "last_request": body},
                                                       ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
