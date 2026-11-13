"""MOCK-only API for UI integration. NO LLM, combat, economy or persistent save."""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from shared.protocol import (NewWorldRequest, CommandRequest, DialogueRequest,
    AdvanceRequest, SaveRequest, LoadRequest, StateView, Envelope)

app = FastAPI(title="Unwritten Realm - MOCK ONLY", version="v1")
WORLDS: dict[str, dict] = {}
SAVES: dict[str, dict] = {}
CACHE: dict[tuple, tuple] = {}

def result(request_id, world_id=None, data=None):
    v = WORLDS.get(world_id, {}).get("world_version")
    return Envelope[dict](request_id=request_id, ok=True, world_id=world_id,
        world_version=v, data=data or {}).model_dump(mode="json")

def failure(code, message, status, request_id="unknown", world_id=None):
    content = Envelope[dict](request_id=request_id, ok=False,
        world_id=world_id, world_version=WORLDS.get(world_id, {}).get("world_version"),
        error={"code": code, "message": message,
               "retryable": code == "VERSION_CONFLICT"}).model_dump(mode="json")
    return JSONResponse(status_code=status, content=content)

@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    body = exc.body if isinstance(exc.body, dict) else {}
    return failure("INVALID_SCHEMA", "Request does not match protocol v1.", 422,
                   body.get("request_id", "unknown"))

def prepare(path, body, world_id=None):
    key = (path, body.request_id)
    value = body.model_dump(mode="json")
    if key in CACHE:
        previous, response = CACHE[key]
        if previous != value:
            return key, failure("REQUEST_ID_REUSED", "Same request ID with different content.",
                                409, body.request_id, world_id)
        return key, deepcopy(response)
    if world_id is not None:
        if world_id not in WORLDS:
            return key, failure("WORLD_NOT_FOUND", "World does not exist.",
                                404, body.request_id, world_id)
        if body.expected_world_version != WORLDS[world_id]["world_version"]:
            return key, failure("VERSION_CONFLICT", "Refresh world state first.",
                                409, body.request_id, world_id)
    return key, None

def finish(key, body, response):
    CACHE[key] = (body.model_dump(mode="json"), deepcopy(response))
    return response

def initial_state(world_id, seed, player_name):
    return StateView.model_validate({
        "world_id": world_id, "seed": seed, "tick": 0, "world_version": 0,
        "player_id": "player_01", "current_region_id": "market",
        "actors": [
            {"id": "player_01", "kind": "player", "name": player_name,
             "alive": True, "hp": 80, "max_hp": 80, "armor": 0,
             "region_id": "market", "tile": {"x": 8.5, "y": 8.5},
             "appearance_key": "traveler", "equipped_item_id": "item_01"},
            {"id": "npc_02", "kind": "npc", "name": "MOCK merchant",
             "alive": True, "hp": 45, "max_hp": 45, "armor": 0,
             "region_id": "market", "tile": {"x": 9.5, "y": 8.5},
             "appearance_key": "merchant", "org_ids": ["org_01"]}],
        "items": [{"id": "item_01", "name": "MOCK iron sword", "base_type": "sword",
             "quality": "common", "material_id": "iron", "affixes": [],
             "stats": {"damage": 6, "cooldown_s": 0.5, "armor": 0},
             "owner_id": "player_01", "origin_event_ids": ["evt_init"]}],
        "organizations": [{"id": "org_01", "name": "MOCK traders",
             "function_tags": ["trade"], "member_ids": ["npc_02"],
             "representative_id": "npc_02", "resources": {"coin": 10}}],
        "relations": [], "tasks": [],
        "sites": [{"id": "site_herb", "kind": "herb", "region_id": "greenwood",
                   "tile": {"x": 12.5, "y": 12.5}, "remaining": 5}],
    }).model_dump(mode="json")

@app.get("/health")
async def health():
    return result("health", data={"status": "ok", "mode": "mock", "api_version": "v1"})

@app.post("/v1/worlds")
async def new_world(body: NewWorldRequest):
    key, cached = prepare("new", body)
    if cached is not None: return cached
    world_id = "world_" + uuid4().hex[:12]
    WORLDS[world_id] = initial_state(world_id, body.seed, body.player_name)
    return finish(key, body, result(body.request_id, world_id,
                                   {"state": deepcopy(WORLDS[world_id])}))

@app.get("/v1/worlds/{world_id}/state")
async def state(world_id: str):
    if world_id not in WORLDS:
        return failure("WORLD_NOT_FOUND", "World does not exist.", 404, world_id=world_id)
    return result("state", world_id, {"state": deepcopy(WORLDS[world_id])})

@app.post("/v1/worlds/{world_id}/commands")
async def commands(world_id: str, body: CommandRequest):
    key, cached = prepare(world_id + "/commands", body, world_id)
    if cached is not None: return cached
    return finish(key, body, result(body.request_id, world_id, {
        "command_result": {"status": "mock_ack_only", "applied": False},
        "events": [], "state": deepcopy(WORLDS[world_id])}))

@app.post("/v1/worlds/{world_id}/dialogue")
async def dialogue(world_id: str, body: DialogueRequest):
    key, cached = prepare(world_id + "/dialogue", body, world_id)
    if cached is not None: return cached
    if not any(a["id"] == body.npc_id for a in WORLDS[world_id]["actors"]):
        return failure("NPC_NOT_FOUND", "No such fixture NPC.", 404, body.request_id, world_id)
    return finish(key, body, result(body.request_id, world_id, {
        "reply": "[MOCK] Interface test only. No model was called and no action was executed.",
        "mode": "mock", "intent_status": "none", "task_ids": [], "events": [],
        "state": deepcopy(WORLDS[world_id])}))

@app.post("/v1/worlds/{world_id}/advance")
async def advance(world_id: str, body: AdvanceRequest):
    key, cached = prepare(world_id + "/advance", body, world_id)
    if cached is not None: return cached
    return finish(key, body, result(body.request_id, world_id, {
        "tick": WORLDS[world_id]["tick"], "decision_summaries": [],
        "tasks": [], "events": [], "mode": "mock", "applied": False,
        "state": deepcopy(WORLDS[world_id])}))

@app.get("/v1/worlds/{world_id}/events")
async def events(world_id: str, after_seq: int = 0, limit: int = 50, view: str = "player"):
    if world_id not in WORLDS:
        return failure("WORLD_NOT_FOUND", "World does not exist.", 404, world_id=world_id)
    if not (0 <= after_seq and 1 <= limit <= 100 and view in ("player", "debug")):
        return failure("INVALID_SCHEMA", "Invalid pagination.", 422, world_id=world_id)
    fixture = {"id": "evt_init", "event_seq": 1, "tick": 0,
        "type": "mock_world_created", "actor_id": None, "target_id": None,
        "facts": {"mock_only": True}, "caused_by": [], "witness_ids": []}
    rows = [fixture] if after_seq < 1 else []
    return result("events", world_id, {"events": rows,
        "next_after_seq": max(after_seq, 1), "has_more": False})

@app.post("/v1/worlds/{world_id}/saves")
async def save(world_id: str, body: SaveRequest):
    key, cached = prepare(world_id + "/save", body, world_id)
    if cached is not None: return cached
    save_id = "save_" + uuid4().hex[:12]
    SAVES[save_id] = deepcopy(WORLDS[world_id])
    return finish(key, body, result(body.request_id, world_id, {
        "save_id": save_id, "saved_world_version": WORLDS[world_id]["world_version"],
        "mock_warning": "Memory-only fixture. Lost when MOCK server exits."}))

@app.post("/v1/saves/{save_id}/load")
async def load(save_id: str, body: LoadRequest):
    key, cached = prepare("load/" + save_id, body)
    if cached is not None: return cached
    if save_id not in SAVES:
        return failure("SAVE_NOT_FOUND", "MOCK save missing.", 404, body.request_id)
    world_id = "world_" + uuid4().hex[:12]
    WORLDS[world_id] = deepcopy(SAVES[save_id])
    WORLDS[world_id]["world_id"] = world_id
    return finish(key, body, result(body.request_id, world_id, {
        "new_world_id": world_id, "parent_save_id": save_id,
        "state": deepcopy(WORLDS[world_id])}))

@app.get("/v1/worlds/{world_id}/agents/{npc_id}/debug")
async def debug(world_id: str, npc_id: str):
    if world_id not in WORLDS:
        return failure("WORLD_NOT_FOUND", "World does not exist.", 404, world_id=world_id)
    return result("debug", world_id, {"memories": [], "policy_history": [],
        "decision_history": [], "mode": "mock", "mock_warning": "No Agent exists in this stub."})
