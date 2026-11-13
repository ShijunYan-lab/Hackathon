"""Atomic world state, event ledger and durable request deduplication."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from shared.protocol import CommandRequest, Envelope, Event, HitPayload, NewWorldRequest, StateView
from server.generation.initial_world import initial_world
from server.world.commands import WorldError, apply_checkpoint
from server.world.combat import CombatRules, settle_hit, validate_hit
from server.world.items import apply_item_command
from server.storage import knowledge


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def response(request_id: str, state: StateView, data: dict) -> dict:
    return Envelope[dict](request_id=request_id, ok=True, world_id=state.world_id,
                          world_version=state.world_version, data=data).model_dump(mode="json")


class WorldStore:
    def __init__(self, path: str | Path, combat_rules: CombatRules | None = None, clock=None):
        self.path = Path(path)
        self.combat_rules = (combat_rules or CombatRules()).model_copy(deep=True)
        self.clock = clock or time.time
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
                CREATE TABLE IF NOT EXISTS world_combat_rules (
                    world_id TEXT PRIMARY KEY, rules TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attacks (
                    world_id TEXT NOT NULL, id TEXT NOT NULL,
                    attacker_id TEXT NOT NULL, weapon_id TEXT NOT NULL,
                    region_id TEXT NOT NULL, started_at REAL NOT NULL,
                    cooldown_s REAL NOT NULL, weapon_damage INTEGER NOT NULL,
                    valid INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(world_id, id)
                );
                CREATE INDEX IF NOT EXISTS attacks_by_actor
                    ON attacks(world_id, attacker_id, started_at);
                CREATE TABLE IF NOT EXISTS attack_hits (
                    world_id TEXT NOT NULL, attack_id TEXT NOT NULL,
                    target_id TEXT NOT NULL, payload TEXT NOT NULL,
                    event_ids TEXT NOT NULL,
                    PRIMARY KEY(world_id, attack_id, target_id)
                );
            """)
            connection.executescript(knowledge.SCHEMA)
        with self.connection(write=True) as connection:
            for row in connection.execute("SELECT world_id, body FROM events ORDER BY world_id, seq").fetchall():
                knowledge.record_event(connection, row[0], Event.model_validate_json(row[1]))

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
        knowledge.record_event(connection, world_id, event)

    def story(self, world_id, debug=False):
        with self.connection() as connection:
            state = StateView.model_validate_json(self.world_row(connection, world_id)["state"])
            return response("story", state, knowledge.story_view(connection, world_id,
                            None if debug else state.player_id))

    def agent_debug(self, world_id, npc_id):
        with self.connection() as connection:
            state = StateView.model_validate_json(self.world_row(connection, world_id)["state"])
            if not any(actor.id == npc_id and actor.kind == "npc" for actor in state.actors):
                raise WorldError("NPC_NOT_FOUND", "NPC 不存在。", 404)
            return response("debug", state, {"memories": knowledge.memories(connection, world_id, npc_id),
                "known_event_ids": [event.id for event in knowledge.known_events(connection, world_id, npc_id)],
                "policy_history": [], "decision_history": []})

    def create(self, body: NewWorldRequest, region: dict) -> dict:
        with self.connection(write=True) as connection:
            cached = self.cached(connection, "new_world", body)
            if cached is not None:
                return cached
            world_id = "world_" + uuid4().hex
            state, event, rng_state = initial_world(world_id, body.seed, body.player_name, region)
            connection.execute("INSERT INTO worlds VALUES (?, ?, ?, ?)",
                               (world_id, state.model_dump_json(), encode(region), encode(rng_state)))
            connection.execute("INSERT INTO world_combat_rules VALUES (?, ?)",
                               (world_id, self.combat_rules.model_dump_json()))
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
            if body.kind == "HIT":
                duplicate = self.duplicate_hit(connection, state, body)
                if duplicate is not None:
                    self.remember(connection, scope, body, duplicate)
                    return duplicate
            if body.expected_world_version != state.world_version:
                raise WorldError("VERSION_CONFLICT", "世界版本已变化，请刷新状态。", 409)
            seq = connection.execute("SELECT MAX(seq) FROM events WHERE world_id=?", (world_id,)).fetchone()[0] + 1
            if body.kind == "CHECKPOINT":
                moved_ids = apply_checkpoint(state, body.payload, json.loads(row["region"]))
                events = [Event(id="evt_" + uuid4().hex, event_seq=seq, tick=state.tick,
                                type="positions_checkpointed", actor_id=state.player_id,
                                facts={"actor_ids": moved_ids, "region_id": body.payload["region_id"],
                                       "positions": body.payload["positions"]},
                                caused_by=[], witness_ids=[state.player_id])]
            elif body.kind == "HIT":
                events = self.apply_hit(connection, state, body, json.loads(row["region"]), seq)
            elif body.kind in ("PICKUP", "EQUIP", "GIVE"):
                events = apply_item_command(state, body.kind, body.payload, seq)
                connection.execute("UPDATE attacks SET valid=0 WHERE world_id=? AND attacker_id=?",
                                   (world_id, body.payload["actor_id"]))
            else:
                raise WorldError("ACTION_NOT_SUPPORTED", "该动作尚未实现。")
            state.world_version += 1
            state = StateView.model_validate(state.model_dump())
            connection.execute("UPDATE worlds SET state=? WHERE id=?", (state.model_dump_json(), world_id))
            for event in events:
                self.append_event(connection, world_id, event)
            result = response(body.request_id, state, {
                "command_result": {"status": "applied", "applied": True},
                "events": [event.model_dump(mode="json") for event in events], "state": state.model_dump(mode="json"),
            })
            self.remember(connection, scope, body, result)
            return result

    @staticmethod
    def duplicate_hit(connection, state, body):
        hit = HitPayload.model_validate(body.payload)
        attack = connection.execute("SELECT * FROM attacks WHERE world_id=? AND id=?",
                                    (state.world_id, hit.attack_id)).fetchone()
        if attack is not None and (attack["attacker_id"], attack["weapon_id"], attack["region_id"]) != (
                hit.attacker_id, hit.weapon_id, hit.region_id):
            raise WorldError("ATTACK_ID_REUSED", "同一次攻击的攻击者、武器和地图必须一致。", 409)
        previous = connection.execute(
            "SELECT payload, event_ids FROM attack_hits WHERE world_id=? AND attack_id=? AND target_id=?",
            (state.world_id, hit.attack_id, hit.target_id),
        ).fetchone()
        if previous is None:
            return None
        if previous["payload"] != encode(hit.model_dump(mode="json")):
            raise WorldError("ATTACK_ID_REUSED", "该次命中的原始位置报告与重报内容不同。", 409)
        return response(body.request_id, state, {
            "command_result": {"status": "already_applied", "applied": False,
                               "source_event_ids": json.loads(previous["event_ids"])},
            "events": [], "state": state.model_dump(mode="json"),
        })

    def apply_hit(self, connection, state, body, region, first_event_seq):
        hit = HitPayload.model_validate(body.payload)
        # Existing worlds acquire a frozen rule snapshot on their first successful hit.
        connection.execute("INSERT OR IGNORE INTO world_combat_rules VALUES (?, ?)",
                           (state.world_id, self.combat_rules.model_dump_json()))
        rules_row = connection.execute("SELECT rules FROM world_combat_rules WHERE world_id=?",
                                       (state.world_id,)).fetchone()
        rules = CombatRules.model_validate_json(rules_row["rules"])
        _, _, weapon = validate_hit(state, hit, region, rules)
        now = self.clock()
        attack = connection.execute("SELECT * FROM attacks WHERE world_id=? AND id=?",
                                    (state.world_id, hit.attack_id)).fetchone()
        latest = connection.execute(
            "SELECT * FROM attacks WHERE world_id=? AND attacker_id=? ORDER BY started_at DESC, rowid DESC LIMIT 1",
            (state.world_id, hit.attacker_id),
        ).fetchone()
        if attack is not None:
            if not attack["valid"] or latest["id"] != hit.attack_id or not (
                    0 <= now - attack["started_at"] < attack["cooldown_s"]):
                raise WorldError("ATTACK_EXPIRED", "该次挥刀已结束，请使用下一次实际攻击的 ID。", 409)
            damage = attack["weapon_damage"]
        else:
            if latest is not None and now - latest["started_at"] < latest["cooldown_s"]:
                raise WorldError("ATTACK_COOLDOWN", "武器冷却尚未结束。")
            damage = weapon.stats.damage
            connection.execute("INSERT INTO attacks VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                               (state.world_id, hit.attack_id, hit.attacker_id, weapon.id, hit.region_id,
                                now, weapon.stats.cooldown_s, damage))
        events, downed = settle_hit(state, hit, region, rules, damage, first_event_seq)
        if downed:
            connection.execute("UPDATE attacks SET valid=0 WHERE world_id=? AND attacker_id=?",
                               (state.world_id, hit.target_id))
        connection.execute("INSERT INTO attack_hits VALUES (?, ?, ?, ?, ?)",
                           (state.world_id, hit.attack_id, hit.target_id,
                            encode(hit.model_dump(mode="json")), encode([event.id for event in events])))
        return events

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
