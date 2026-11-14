"""Run one worker with python -m uvicorn server.main:app --port 8765."""
from __future__ import annotations

import json
import os
import sqlite3
import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from shared.protocol import AdvanceRequest, CommandRequest, DialogueRequest, Envelope, NewWorldRequest, SaveRequest, LoadRequest
from server.storage.snapshots import Snapshots
from server.evaluation.scenario import TransportScenario
from server.evaluation.service import Evaluations
from shared.evaluation_protocol import EvaluationCreateRequest, EvaluationRunRequest
from server.storage.sqlite import WorldStore, response
from server.world.commands import WorldError
from server.world.combat import CombatRules
from server.world.agent_runtime import AgentGateway, AgentRuntime
from server.world.advance import WorldTurns
from server.world.director import DirectorConfig

ROOT = Path(__file__).resolve().parents[1]


def create_app(db_path: str | Path | None = None, regions_path: str | Path | None = None,
               region_id: str | None = None, allow_debug: bool | None = None,
               combat_rules: CombatRules | None = None, clock=None,
               dialogue_provider=None, plan_provider=None, agent_timeout_s=8,
               director_provider=None, director_config=None, transport_scenario=None,
               choose_provider=None) -> FastAPI:
    if allow_debug is None:
        allow_debug = os.environ.get("ALLOW_DEBUG", "false").lower() == "true"
    @asynccontextmanager
    async def lifespan(app):
        document = json.loads(Path(regions_path or ROOT / "shared/regions.json").read_text(encoding="utf-8"))
        selected_id = region_id or os.environ.get("WORLD_REGION_ID", "market")
        region = next((item for item in document["regions"] if item["id"] == selected_id), None)
        if region is None:
            raise ValueError("Configured WORLD_REGION_ID is absent from the map description")
        app.state.region = region
        app.state.map_fixture = document.get("fixture_only", False)
        rules_path = os.environ.get("COMBAT_RULES_PATH", str(ROOT / "server/world/combat_rules.json"))
        rules = combat_rules or CombatRules.from_file(rules_path)
        app.state.store = WorldStore(db_path or os.environ.get("WORLD_DB_PATH", str(ROOT / "runtime/worlds.sqlite3")),
                                     combat_rules=rules, clock=clock)
        app.state.agents = AgentRuntime(app.state.store, AgentGateway(dialogue_provider, plan_provider,
                                                                    timeout_s=agent_timeout_s))
        config = director_config or DirectorConfig.from_file(os.environ.get(
            "DIRECTOR_CONFIG_PATH", str(ROOT / "server/world/director_config.json")))
        app.state.turns = WorldTurns(app.state.agents, config, director_provider)
        app.state.snapshots = Snapshots(app.state.store)
        app.state.evaluations = Evaluations(app.state.store, app.state.snapshots, app.state.turns,
            transport_scenario or TransportScenario(), region, choose_provider)
        async def maintenance():
            while True:
                app.state.evaluations.expire()
                await asyncio.sleep(.25)
        worker = asyncio.create_task(maintenance())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    app = FastAPI(title="未定之境 · C 世界后端", version="v1", lifespan=lifespan,
                  description="步骤 01—08：世界、战斗、物品、记忆、NPC 任务与世界导演。未接模型时使用 fallback。")

    async def error(request, code, message, status):
        request_id = "unknown"
        try:
            body = await request.json()
            if isinstance(body, dict) and isinstance(body.get("request_id"), str):
                request_id = body["request_id"]
        except (ValueError, UnicodeDecodeError):
            pass
        world_id = request.path_params.get("world_id")
        content = Envelope[dict](request_id=request_id, ok=False, world_id=world_id,
            error={"code": code, "message": message,
                   "retryable": code in {"VERSION_CONFLICT", "BACKEND_UNAVAILABLE"}})
        return JSONResponse(status_code=status, content=content.model_dump(mode="json"))

    @app.exception_handler(WorldError)
    async def world_error(request: Request, exc: WorldError):
        return await error(request, exc.code, str(exc), exc.status)

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc: sqlite3.OperationalError):
        return await error(request, "BACKEND_UNAVAILABLE", "世界存储暂时不可用，请稍后重试。", 503)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return await error(request, "INVALID_SCHEMA", "请求格式不符合 v1 协议。", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return await error(request, "HTTP_ERROR", "接口不存在或请求方法不支持。", exc.status_code)

    @app.get("/health")
    def health():
        modes = {"npc": app.state.agents.gateway.last_mode, "director": app.state.turns.last_mode}
        mode = "live" if "live" in modes.values() else "fallback"
        return Envelope[dict](request_id="health", ok=True, data={
            "status": "ok", "mode": mode, "component_modes": modes, "api_version": "v1",
            "capabilities": ["persistent_worlds", "checkpoint", "events", "hit", "death_cleanup",
                             "pickup", "equip", "give", "story", "dialogue", "task_report", "advance", "director"],
            "model_connected": mode == "live", "map_fixture": app.state.map_fixture,
        })

    @app.post("/v1/worlds")
    def new_world(body: NewWorldRequest):
        return app.state.store.create(body, app.state.region)

    @app.get("/v1/worlds/{world_id}/state")
    def state(world_id: str):
        current = app.state.store.state(world_id)
        return response("state", current, {"state": current.model_dump(mode="json")})

    @app.post("/v1/worlds/{world_id}/commands")
    def commands(world_id: str, body: CommandRequest):
        return app.state.store.command(world_id, body)

    @app.post('/v1/worlds/{world_id}/saves')
    def save(world_id: str, body: SaveRequest):
        return app.state.snapshots.save(world_id, body)

    @app.post('/v1/saves/{save_id}/load')
    def load(save_id: str, body: LoadRequest):
        return app.state.snapshots.load(save_id, body)

    @app.post('/v1/evaluations')
    def evaluation_create(body: EvaluationCreateRequest):
        return app.state.evaluations.create(body)

    @app.post('/v1/evaluations/{evaluation_id}/runs', status_code=202)
    async def evaluation_run(evaluation_id: str, body: EvaluationRunRequest):
        return await app.state.evaluations.start(evaluation_id, body)

    @app.get('/v1/evaluations/{evaluation_id}')
    def evaluation_get(evaluation_id: str):
        return app.state.evaluations.get(evaluation_id)

    @app.get('/v1/evaluations/{evaluation_id}/report')
    def evaluation_report(evaluation_id: str):
        return app.state.evaluations.report(evaluation_id)

    @app.post("/v1/worlds/{world_id}/dialogue")
    async def dialogue(world_id: str, body: DialogueRequest):
        return await app.state.agents.dialogue(world_id, body)

    @app.post("/v1/worlds/{world_id}/advance")
    async def advance(world_id: str, body: AdvanceRequest):
        return await app.state.turns.advance(world_id, body)

    @app.get("/v1/worlds/{world_id}/director/debug")
    def director_debug(world_id: str):
        if not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.turns.debug(world_id)

    @app.get("/v1/worlds/{world_id}/events")
    def events(world_id: str, after_seq: int = Query(default=0, ge=0),
               limit: int = Query(default=50, ge=1, le=100), view: Literal["player", "debug"] = "player"):
        if view == "debug" and not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.store.events(world_id, after_seq, limit, view == "debug")

    @app.get("/v1/worlds/{world_id}/story")
    def story(world_id: str, view: Literal["player", "debug"] = "player"):
        if view == "debug" and not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.store.story(world_id, debug=view == "debug")

    @app.get("/v1/worlds/{world_id}/agents/{npc_id}/debug")
    def agent_debug(world_id: str, npc_id: str):
        if not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.store.agent_debug(world_id, npc_id)

    return app


app = create_app()
