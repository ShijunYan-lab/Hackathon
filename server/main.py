"""Run one worker with python -m uvicorn server.main:app --port 8765."""
from __future__ import annotations

import json
import os
import sqlite3
import asyncio
import logging
from contextlib import suppress
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from shared.protocol import AdvanceRequest, CommandRequest, DialogueRequest, Envelope, NewWorldRequest, SaveRequest, LoadRequest, StateView
from server.storage.snapshots import Snapshots
from server.evaluation.scenario import TransportScenario
from server.evaluation.service import Evaluations
from shared.evaluation_protocol import EvaluationCreateRequest, EvaluationRunRequest, EvaluationRollbackRequest
from shared.world_protocol import OfferRequest, CraftRequest, SupplyRequest
from server.world.economy import EconomyAPI
from server.storage.sqlite import WorldStore, response
from server.world.commands import WorldError
from server.world.combat import CombatRules
from server.world.agent_runtime import AgentGateway, AgentRuntime
from server.world.advance import WorldTurns
from server.world import chronicle
from server.world.director import DirectorConfig
from server.world.model_gateway import DirectorModel

ROOT = Path(__file__).resolve().parents[1]


def create_app(db_path: str | Path | None = None, regions_path: str | Path | None = None,
               region_id: str | None = None, allow_debug: bool | None = None,
               combat_rules: CombatRules | None = None, clock=None,
               dialogue_provider=None, plan_provider=None, agent_timeout_s=8,
               director_provider=None, director_config=None, transport_scenario=None, chapter_writer=None,
               choose_provider=None, learn_provider=None, evaluation_identity=None) -> FastAPI:
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
        model = DirectorModel.from_environment()
        npc_integration = model if os.environ.get('WORLD_NPC_MODEL_DEMO', '').lower() == 'true' else None
        app.state.agents = AgentRuntime(app.state.store, AgentGateway(dialogue_provider, plan_provider,
                                                                    timeout_s=agent_timeout_s, integration_model=npc_integration))
        config = director_config or DirectorConfig.from_file(os.environ.get(
            "DIRECTOR_CONFIG_PATH", str(ROOT / "server/world/director_config.json")))
        app.state.turns = WorldTurns(app.state.agents, config, director_provider or model,
                                    chapter_writer or (model.write_chapter if model else None))
        app.state.snapshots = Snapshots(app.state.store)
        if region.get('reactive_npcs'):
            from server.world.overworld_upgrade import upgrade
            upgrade(app.state.store, region)
        app.state.economy = EconomyAPI(app.state.store)
        app.state.evaluations = Evaluations(app.state.store, app.state.snapshots, app.state.turns,
            transport_scenario or TransportScenario(), region, choose_provider, learn_provider, evaluation_identity)
        async def maintenance():
            while True:
                try:
                    app.state.evaluations.expire()
                except sqlite3.OperationalError:
                    logging.getLogger(__name__).warning('Evaluation storage busy; expiry will retry.')
                await asyncio.sleep(.25)
        worker = asyncio.create_task(maintenance())
        async def learning_worker():
            while True:
                try:
                    await app.state.evaluations.learn_pending()
                except (sqlite3.OperationalError, WorldError):
                    logging.getLogger(__name__).warning('Learning storage unavailable; pending work will retry.')
                await asyncio.sleep(.1)
        learner = asyncio.create_task(learning_worker())
        try:
            yield
        finally:
            worker.cancel()
            learner.cancel()
            with suppress(asyncio.CancelledError):
                await worker
            with suppress(asyncio.CancelledError):
                await learner

    app = FastAPI(title="未定之境 · C 世界后端", version="v1", lifespan=lifespan,
                  description="步骤 01—13：世界、战斗、任务、导演、存档、运输学习回退与基础经济。未接模型时使用 fallback。")

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
                   "retryable": code in {"VERSION_CONFLICT", "BACKEND_UNAVAILABLE", 'REQUEST_IN_PROGRESS'}})
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
            "region_id": app.state.region['id'], "map_width_tiles": app.state.region['width_tiles'],
            "map_height_tiles": app.state.region['height_tiles'],
            "capabilities": ["persistent_worlds", "checkpoint", "events", "hit", "death_cleanup",
                             "pickup", "equip", "give", "story", "dialogue", "task_report", "advance", "director",
                             'save', 'load', 'evaluation', 'learning', 'rollback', 'offers', 'craft', 'migration'],
            "model_connected": mode == "live", "map_fixture": app.state.map_fixture,
              "debug_views": allow_debug,
              "director_model": getattr(app.state.turns.provider, 'model', None),
              "director_configured": app.state.turns.provider is not None,
        })

    @app.post("/v1/worlds")
    def new_world(body: NewWorldRequest):
        return app.state.store.create(body, app.state.region)

    @app.get("/v1/worlds/{world_id}/state")
    def state(world_id: str):
        current = app.state.store.state(world_id)
        with app.state.store.connection() as connection:
            runtime = connection.execute('SELECT evaluation_active FROM world_runtime WHERE world_id=?', (world_id,)).fetchone()
            frozen = bool(runtime and runtime[0])
            recovery = connection.execute('''SELECT w.id FROM worlds w LEFT JOIN world_runtime r ON w.id=r.world_id
                WHERE COALESCE(r.evaluation_active,0)=0 ORDER BY w.rowid DESC LIMIT 1''').fetchone() if frozen else None
        data = {"state": current.model_dump(mode="json")}
        if frozen:
            data.update(evaluation_active=True, recovery_world_id=recovery[0] if recovery else None)
        return response("state", current, data)

    @app.get('/v1/worlds/{world_id}/dialogue/{npc_id}/history')
    def dialogue_history(world_id: str, npc_id: str):
        current = app.state.store.state(world_id)
        app.state.agents.check_dialogue(current, npc_id)
        with app.state.store.connection() as connection:
            turns = [json.loads(row[0]) for row in connection.execute(
                'SELECT body FROM npc_dialogue_turns WHERE world_id=? AND npc_id=? ORDER BY rowid DESC LIMIT 20',
                (world_id, npc_id))][::-1]
        return response('dialogue_history', current, {'npc_id':npc_id, 'turns':turns})

    @app.post("/v1/worlds/{world_id}/commands")
    def commands(world_id: str, body: CommandRequest):
        return app.state.store.command(world_id, body)

    @app.post('/v1/worlds/{world_id}/saves')
    def save(world_id: str, body: SaveRequest):
        return app.state.snapshots.save(world_id, body)

    @app.get('/v1/worlds/{world_id}/economy')
    def economy(world_id: str):
        return app.state.economy.view(world_id)

    @app.post('/v1/worlds/{world_id}/offers')
    def offer(world_id: str, body: OfferRequest):
        return app.state.economy.mutate(world_id, body, 'offers')

    @app.post('/v1/worlds/{world_id}/craft')
    def craft(world_id: str, body: CraftRequest):
        return app.state.economy.mutate(world_id, body, 'craft')

    @app.post('/v1/worlds/{world_id}/supply')
    def supply(world_id: str, body: SupplyRequest):
        return app.state.economy.mutate(world_id, body, 'supply')

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

    @app.get('/v1/evaluations/{evaluation_id}/profile')
    def evaluation_profile(evaluation_id: str):
        with app.state.store.connection() as connection:
            data = app.state.evaluations.row(connection, evaluation_id)
            return Envelope[dict](request_id='profile', ok=True, data={
                'baseline_profile': data['baseline_profile'], 'active_profile': data['profile'],
                'learning_mode': data.get('learning_mode', 'fallback'),
                'code_hash': data['code_hash'], 'adapter_hash': data.get('adapter_hash')})

    @app.post('/v1/evaluations/{evaluation_id}/rollback')
    def evaluation_rollback(evaluation_id: str, body: EvaluationRollbackRequest):
        return app.state.evaluations.rollback(evaluation_id, body)

    @app.post("/v1/worlds/{world_id}/dialogue")
    async def dialogue(world_id: str, body: DialogueRequest):
        return await app.state.agents.dialogue(world_id, body)

    @app.post("/v1/worlds/{world_id}/advance")
    async def advance(world_id: str, body: AdvanceRequest):
        return await app.state.turns.advance(world_id, body)

    @app.get("/v1/worlds/{world_id}/director/debug")
    def director_debug(world_id: str, limit: int = Query(default=20, ge=1, le=100)):
        if not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.turns.debug(world_id, limit)

    @app.get("/v1/worlds/{world_id}/events")
    def events(world_id: str, after_seq: int = Query(default=0, ge=0),
               limit: int = Query(default=50, ge=1, le=100), view: Literal["player", "debug"] = "player"):
        if view == "debug" and not allow_debug:
            raise WorldError("DEBUG_DISABLED", "当前未开放调试视图。", 403)
        return app.state.store.events(world_id, after_seq, limit, view == "debug")

    @app.get("/v1/worlds/{world_id}/story/chapters")
    def chapters(world_id: str, after_seq: int = Query(default=0, ge=0), limit: int = Query(default=20, ge=1, le=50),
                 latest: bool = False):
        store = app.state.store
        with store.connection() as connection:
            state = StateView.model_validate_json(store.world_row(connection, world_id)["state"])
            records = chronicle.read(connection, world_id, after_seq, limit + 1, latest=latest)
            page = records[:limit]
            return response("chapters", state, {"chapters": page, "has_more": len(records) > limit,
                "next_after_seq": page[-1]["through_event_seq"] if page else after_seq})

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

    app.mount('/demo', StaticFiles(directory=ROOT / 'server/api/demo', html=True), name='demo')
    return app


app = create_app()
