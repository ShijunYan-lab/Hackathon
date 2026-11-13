"""Atomic world state, event ledger and durable request deduplication."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from shared.protocol import CommandRequest, Envelope, Event, NewWorldRequest, StateView
from server.generation.initial_world import initial_world
from server.world.commands import WorldError, apply_checkpoint


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def response(request_id: str, state: StateView, data: dict) -> dict:
    return Envelope[dict](request_id=request_id, ok=True, world_id=state.world_id,
                          world_version=state.world_version, data=data).model_dump(mode="json")


class WorldStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    region TEXT NOT NULL, rng_state TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    world_id TEXT NOT NULL, seq INTEGER NOT NULL,
                    id TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(world_id, seq), UNIQUE(world_id, id)
                );
                CREATE TABLE IF NOT EXISTS requests (
                    scope TEXT NOT NULL, id TEXT NOT NULL,
                    body TEXT NOT NULL, response TEXT NOT NULL,
                    PRIMARY KEY(scope, id)
                );
            """)

    @contextmanager
    def connection(self, write=False):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def cached(connection, scope, body):
        previous = connection.execute(
            "SELECT body, response FROM requests WHERE scope=? AND id=?",
            (scope, body.request_id),
        ).fetchone()
        if previous is None:
            return None
        if previous["body"] != encode(body.model_dump(mode="json")):
            raise WorldError("REQUEST_ID_REUSED", "同一个请求 ID 被用于不同内容。", 409)
        return json.loads(previous["response"])

    @staticmethod
    def remember(connection, scope, body, result):
        connection.execute("INSERT INTO requests VALUES (?, ?, ?, ?)",
                           (scope, body.request_id, encode(body.model_dump(mode="json")), encode(result)))

    @staticmethod
    def world_row(connection, world_id):
        row = connection.execute("SELECT * FROM worlds WHERE id=?", (world_id,)).fetchone()
        if row is None:
            raise WorldError("WORLD_NOT_FOUND", "世界不存在。", 404)
        return row

    @staticmethod
    def append_event(connection, world_id, event):
        connection.execute("INSERT INTO events VALUES (?, ?, ?, ?)",
                           (world_id, event.event_seq, event.id, event.model_dump_json()))

    def create(self, body: NewWorldRequest, region: dict) -> dict:
        with self.connection(write=True) as connection:
            cached = self.cached(connection, "new_world", body)
            if cached is not None:
                return cached
            world_id = "world_" + uuid4().hex
            state, event, rng_state = initial_world(world_id, body.seed, body.player_name, region)
            connection.execute("INSERT INTO worlds VALUES (?, ?, ?, ?)",
                               (world_id, state.model_dump_json(), encode(region), encode(rng_state)))
            self.append_event(connection, world_id, event)
            result = response(body.request_id, state, {"state": state.model_dump(mode="json")})
            self.remember(connection, "new_world", body, result)
            return result

    def state(self, world_id: str) -> StateView:
        with self.connection() as connection:
            return StateView.model_validate_json(self.world_row(connection, world_id)["state"])

    def command(self, world_id: str, body: CommandRequest) -> dict:
        scope = world_id + "/commands"
        with self.connection(write=True) as connection:
            cached = self.cached(connection, scope, body)
            if cached is not None:
                return cached
            row = self.world_row(connection, world_id)
            state = StateView.model_validate_json(row["state"])
            if body.expected_world_version != state.world_version:
                raise WorldError("VERSION_CONFLICT", "世界版本已变化，请刷新状态。", 409)
            if body.kind != "CHECKPOINT":
                raise WorldError("ACTION_NOT_SUPPORTED", "当前节点支持 CHECKPOINT，其他动作待实现。")
            moved_ids = apply_checkpoint(state, body.payload, json.loads(row["region"]))
            state.world_version += 1
            seq = connection.execute("SELECT MAX(seq) FROM events WHERE world_id=?", (world_id,)).fetchone()[0] + 1
            event = Event(id="evt_" + uuid4().hex, event_seq=seq, tick=state.tick,
                          type="positions_checkpointed", actor_id=state.player_id,
                          facts={"actor_ids": moved_ids, "region_id": body.payload["region_id"],
                                 "positions": body.payload["positions"]},
                          caused_by=[], witness_ids=[state.player_id])
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (state.model_dump_json(), world_id))
            self.append_event(connection, world_id, event)
            result = response(body.request_id, state, {
                "command_result": {"status": "applied", "applied": True},
                "events": [event.model_dump(mode="json")], "state": state.model_dump(mode="json"),
            })
            self.remember(connection, scope, body, result)
            return result

    def events(self, world_id: str, after_seq: int, limit: int, debug: bool) -> dict:
        with self.connection() as connection:
            state = StateView.model_validate_json(self.world_row(connection, world_id)["state"])
            rows = connection.execute("SELECT body FROM events WHERE world_id=? AND seq>? ORDER BY seq",
                                      (world_id, after_seq)).fetchall()
            visible = [Event.model_validate_json(row["body"]) for row in rows]
            if not debug:
                visible = [event for event in visible if state.player_id in event.witness_ids]
            page = visible[:limit]
            return response("events", state, {"events": [event.model_dump(mode="json") for event in page],
                "next_after_seq": page[-1].event_seq if page else after_seq, "has_more": len(visible) > limit})
