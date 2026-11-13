import json

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from server.storage import knowledge
from server.world.commands import WorldError
from shared.protocol import Event, MemoryProposal


def test_private_world_history_sources_and_restart(tmp_path):
    path = tmp_path / "world.sqlite3"
    app = create_app(path, allow_debug=True)
    with TestClient(app) as client:
        state = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                              "player_name": "Test"}).json()["data"]["state"]
        world_id = state["world_id"]
        npc, outsider = state["actors"][1:3]
        event = Event(id="evt_private", event_seq=2, tick=0, type="speech", actor_id=npc["id"],
                      target_id=outsider["id"], facts={"text": "这是一个未经证实的传闻"},
                      caused_by=[], witness_ids=[npc["id"]])
        with app.state.store.connection(write=True) as connection:
            app.state.store.append_event(connection, world_id, event)
            proposal = MemoryProposal(statement="听到传闻", source_type="report",
                                      source_event_ids=[event.id], confidence=.4, status="unverified")
            knowledge.save_memory_proposals(connection, world_id, npc["id"], [proposal, proposal])
            with pytest.raises(WorldError):
                knowledge.save_memory_proposals(connection, world_id, outsider["id"], [proposal])
        route = f"/v1/worlds/{world_id}"
        public = client.get(route + "/story").json()["data"]
        assert len(public["memories"]) == 1
        debug = client.get(route + "/story?view=debug").json()["data"]
        assert len(debug["memories"]) == 2
        observed = client.get(route + f"/agents/{npc['id']}/debug").json()["data"]
        assert observed["known_event_ids"] == [event.id]
        assert len(observed["memories"]) == 2
        assert client.get(route + f"/agents/{outsider['id']}/debug").json()["data"]["memories"] == []
    with TestClient(create_app(path, allow_debug=True)) as restarted:
        assert restarted.get(route + "/story?view=debug").json()["data"] == debug
        assert restarted.get(route + f"/agents/{npc['id']}/debug").json()["data"] == observed
    with TestClient(create_app(path)) as restricted:
        assert restricted.get(route + "/story?view=debug").status_code == 403


def test_story_lifecycle_and_invalid_cause(tmp_path):
    app = create_app(tmp_path / "world.sqlite3", allow_debug=True)
    with TestClient(app) as client:
        state = client.post("/v1/worlds", json={"request_id": "new", "seed": 42,
                                              "player_name": "Test"}).json()["data"]["state"]
        store, world_id = app.state.store, state["world_id"]
        for seq, kind, cause in [(2, "task_scheduled", []), (3, "task_succeeded", ["evt_2"])]:
            event = Event(id=f"evt_{seq}", event_seq=seq, tick=0, type=kind,
                          facts={"task_id": "task_test"}, caused_by=cause, witness_ids=[state["player_id"]])
            with store.connection(write=True) as connection:
                store.append_event(connection, world_id, event)
        data = client.get(f"/v1/worlds/{world_id}/story").json()["data"]
        assert data["story_threads"][0]["status"] == "resolved"
        assert data["story_threads"][0]["source_event_ids"] == ["evt_2", "evt_3"]
        with pytest.raises(WorldError), store.connection(write=True) as connection:
            store.append_event(connection, world_id, Event(id="invalid", event_seq=4, tick=0,
                type="test", facts={}, caused_by=["foreign_event"], witness_ids=[]))
        assert client.get(f"/v1/worlds/{world_id}/story").json()["data"] == data
