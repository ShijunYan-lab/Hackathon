"""Authoritative transport lifecycle; client only submits ordinary action reports."""
import asyncio
import importlib
import json
from pathlib import Path
from uuid import uuid4

from shared.evaluation_protocol import (EvaluationSession, LearningProfile, RunView, RunMetrics,
    TransportChoice, TransportContext, TransportOutcome)
from server.evaluation.learning import fallback_update, validate_update
from shared.protocol import ActorState, Envelope, NewWorldRequest, StateView, Task
from server.storage.sqlite import encode
from server.storage.snapshots import digest
from server.world.commands import WorldError, apply_checkpoint
from server.world.tasks import event, reachable


SCHEMA = '''
CREATE TABLE IF NOT EXISTS evaluations (id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL, world_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL
);
'''


def implementation_hash():
    root = Path(__file__).resolve().parents[2]
    files = sorted(path for folder in ('server', 'shared') for path in (root / folder).rglob('*.py'))
    return digest({str(path.relative_to(root)): path.read_text(encoding='utf-8') for path in files})


class Evaluations:
    def __init__(self, store, snapshots, turns, scenario, region, choose_provider=None, learn_provider=None):
        self.store, self.snapshots, self.turns = store, snapshots, turns
        self.scenario, self.region = scenario, region
        self.choose_provider = choose_provider
        self.learn_provider = learn_provider
        self.code_hash = implementation_hash()
        with store.connection() as connection:
            connection.executescript(SCHEMA)
        store.command_guard = self.guard
        store.command_observer = self.observe

    def row(self, connection, evaluation_id):
        row = connection.execute('SELECT body FROM evaluations WHERE id=?', (evaluation_id,)).fetchone()
        if row is None:
            raise WorldError('EVALUATION_NOT_FOUND', '评审会话不存在。', 404)
        return json.loads(row[0])

    @staticmethod
    def persist(connection, data):
        connection.execute('INSERT OR REPLACE INTO evaluations VALUES (?, ?)',
                           (data['session']['evaluation_id'], encode(data)))

    @staticmethod
    def persist_run(connection, run):
        connection.execute('INSERT OR REPLACE INTO evaluation_runs VALUES (?, ?, ?, ?)',
            (run['view']['run_id'], run['evaluation_id'], run['view']['world_id'], encode(run)))

    def output(self, connection, data, request_id):
        session = EvaluationSession.model_validate(data['session'])
        state = None
        if session.active_world_id:
            state = StateView.model_validate_json(self.store.world_row(connection, session.active_world_id)['state'])
        run = None
        if session.run_ids:
            run = json.loads(connection.execute('SELECT body FROM evaluation_runs WHERE id=?',
                (session.run_ids[-1],)).fetchone()[0])['view']
        return Envelope[dict](request_id=request_id, ok=True, world_id=session.active_world_id,
            world_version=state.world_version if state else None,
            data={'session': session.model_dump(mode='json'), 'run': run,
                  'state': state.model_dump(mode='json') if state else None}).model_dump(mode='json')

    def create(self, body):
        # World creation uses a private request scope and is reused if evaluation creation retries.
        with self.store.connection() as connection:
            cached = self.store.cached(connection, 'evaluations/create', body)
            if cached is not None:
                return cached
        created = self.store.create(NewWorldRequest(request_id='eval_base_' + digest(body.request_id),
            seed=body.seed, player_name='评审观察者'), self.region)
        world_id = created['world_id']
        with self.store.connection(write=True) as connection:
            cached = self.store.cached(connection, 'evaluations/create', body)
            if cached is not None:
                return cached
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)['state'])
            config = self.scenario.model_dump(mode='json')
            if config['escort_cost'] > config['gold_initial']:
                raise WorldError('PRECONDITION_FAILED', '护卫费用不能超过场景预算。')
            merchant, guard = state.actors[1:3]
            merchant.tile = self.scenario.start.model_copy()
            guard.tile = self.scenario.start.model_copy()
            # Dynamic actor identity; threat and gear are frozen once in S0.
            threat_id = 'monster_' + uuid4().hex
            threat = ActorState(id=threat_id, name='路途威胁', kind='monster', alive=True,
                hp=35, max_hp=35, armor=0, tile=self.scenario.threat, region_id=state.current_region_id,
                appearance_key='monster')
            weapon = state.items[1].model_copy(deep=True)
            weapon.id, weapon.owner_id, weapon.name = 'item_' + uuid4().hex, threat_id, '威胁武器'
            weapon.stats.damage, weapon.stats.armor, weapon.stats.cooldown_s = 12, 0, .5
            threat.equipped_item_id = weapon.id
            state.actors.append(threat)
            state.items.append(weapon)
            for tile in (self.scenario.start, self.scenario.destination, self.scenario.threat):
                apply_checkpoint(state, {'region_id': state.current_region_id, 'positions': [
                    {'actor_id': state.player_id, 'tile': tile.model_dump()}]}, self.region)
            state.actors[0].tile = self.scenario.start.model_copy()
            if not reachable(self.region, self.scenario.start, self.scenario.destination):
                raise WorldError('PRECONDITION_FAILED', '运输终点不可达。')
            profile = LearningProfile(profile_id='profile_' + uuid4().hex, learner_id=merchant.id, version=0,
                context_key='transport_v1', alpha=self.scenario.alpha,
                values={'direct': self.scenario.direct_value, 'escort': self.scenario.escort_value}, retrieval_epoch=0)
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), world_id))
            self.turns.runtime(connection, world_id)
            connection.execute('UPDATE world_runtime SET evaluation_active=1 WHERE world_id=?', (world_id,))
            snapshot_id = self.snapshots.write(connection, world_id, 'evaluation S0')
            scenario_hash = digest({'config': config, 'region': self.region, 'code': self.code_hash,
                'snapshot': self.snapshots.read(connection, snapshot_id), 'profile': profile.model_dump(mode='json')})
            session = EvaluationSession(evaluation_id='evaluation_' + uuid4().hex, evaluation_version=0,
                seed=body.seed, scenario_hash=scenario_hash, snapshot_id=snapshot_id, learner_id=merchant.id,
                baseline_profile_version=0, active_profile_version=0, status='ready', active_world_id=world_id,
                mode='fallback')
            data = {'session': session.model_dump(mode='json'), 'config': config,
                'baseline_profile': profile.model_dump(mode='json'), 'profile': profile.model_dump(mode='json'),
                'guard_id': guard.id, 'threat_id': threat_id, 'code_hash': self.code_hash,
                'learning_update': None, 'notes': ['动作报告来自客户端；真实 Godot 验收另行记录。']}
            self.persist(connection, data)
            result = self.output(connection, data, body.request_id)
            self.store.remember(connection, 'evaluations/create', body, result)
            return result

    async def choose(self, context, profile):
        provider = self.choose_provider
        if provider is None:
            try:
                provider = importlib.import_module('server.agents.transport_learning').choose_transport
            except (ImportError, AttributeError):
                provider = None
        if provider is not None:
            try:
                async def invoke():
                    async with self.turns.agents.gateway.semaphore:
                        return await asyncio.to_thread(provider, context.model_copy(deep=True), profile.model_copy(deep=True))
                raw = await asyncio.wait_for(invoke(), 8)
                return TransportChoice.model_validate(raw), 'live'
            except Exception:
                pass
        strategy = max(context.available_strategies, key=lambda value: (profile.values[value], value == 'direct'))
        return TransportChoice(strategy=strategy, profile_version=profile.version,
            evidence_memory_ids=[memory.id for memory in profile.memories],
            reason_summary='规则降级：从合法策略中选择当前价值最高者。'), 'fallback'

    @staticmethod
    def check_phase(data, body):
        session = data['session']
        if session['evaluation_version'] != body.expected_evaluation_version:
            raise WorldError('EVALUATION_VERSION_CONFLICT', '评审版本已改变，请刷新。', 409)
        allowed = {'first': 'ready', 'second': 'ready_for_second', 'rollback_check': 'rolled_back'}
        if session['status'] != allowed[body.kind]:
            raise WorldError('INVALID_PHASE', '当前阶段不能启动该轮任务。', 409)

    async def start(self, evaluation_id, body):
        scope = evaluation_id + '/runs'
        with self.store.connection(write=True) as connection:
            cached, token = self.turns.agents.reserve(connection, scope, body)
            if cached is not None:
                return cached
            data = self.row(connection, evaluation_id)
            self.check_phase(data, body)
            profile = LearningProfile.model_validate(data['profile'])
            config = data['config']
            snapshot = self.snapshots.read(connection, data['session']['snapshot_id'])
            baseline = StateView.model_validate_json(snapshot['world']['state'])
            guard = next(actor for actor in baseline.actors if actor.id == data['guard_id'])
            available = ['direct']
            if guard.alive and config['guard_consents'] and config['gold_initial'] >= config['escort_cost']:
                available.append('escort')
            context = TransportContext(learner_id=profile.learner_id, context_key=profile.context_key,
                available_strategies=available, own_gold=config['gold_initial'], escort_cost=config['escort_cost'],
                guard_id=guard.id, known_event_ids=list(dict.fromkeys(
                    source for memory in profile.memories for source in memory.source_event_ids)))
        try:
            choice, mode = await self.choose(context, profile)
            with self.store.connection(write=True) as connection:
                data = self.row(connection, evaluation_id)
                self.check_phase(data, body)
                active = connection.execute('SELECT token FROM agent_requests WHERE scope=? AND id=?',
                                             (scope, body.request_id)).fetchone()
                if not active or active[0] != token:
                    raise WorldError('REQUEST_EXPIRED', '选策请求已过期。', 409)
                if data['code_hash'] != self.code_hash:
                    raise WorldError('SNAPSHOT_MISMATCH', '代码环境已改变，需重新创建评审会话。', 409)
                if (choice.profile_version != profile.version or choice.strategy not in available or
                    not set(choice.evidence_memory_ids) <= {memory.id for memory in profile.memories}):
                    raise WorldError('PRECONDITION_FAILED', '选策引用无效版本、策略或经验。')
                state = self.snapshots.branch(connection, data['session']['snapshot_id'])
                merchant = next(actor for actor in state.actors if actor.id == profile.learner_id)
                guard = next(actor for actor in state.actors if actor.id == data['guard_id'])
                seq = connection.execute('SELECT MAX(seq) FROM events WHERE world_id=?', (state.world_id,)).fetchone()[0] + 1
                run_id = 'run_' + uuid4().hex
                started = event(state, 'transport_started', seq, merchant.id, None,
                    {'run_id': run_id, 'strategy': choice.strategy, 'cargo_initial': config['cargo_initial'],
                     'gold_initial': config['gold_initial'], 'profile_version': profile.version}, [], [merchant.id])
                events = [started]
                spent = config['escort_cost'] if choice.strategy == 'escort' else 0
                if choice.strategy == 'escort':
                    events.append(event(state, 'escort_paid', seq + len(events), merchant.id, guard.id,
                        {'gold_spent': spent, 'merchant_gold': config['gold_initial'] - spent,
                         'guard_gold_received': spent, 'guard_consented': True}, [started.id], [merchant.id, guard.id]))
                    escort = Task(id='task_' + uuid4().hex, actor_id=guard.id, kind='ESCORT', target_id=merchant.id,
                        status='pending', started_tick=state.tick, source_event_ids=[events[-1].id])
                    state.tasks.append(escort)
                    guard.task_id, guard.behavior = escort.id, 'moving'
                task = Task(id='task_' + uuid4().hex, actor_id=merchant.id, kind='MOVE', status='pending',
                    target_region_id=state.current_region_id, target_tile=config['destination'], started_tick=state.tick,
                    source_event_ids=[started.id])
                state.tasks.append(task)
                merchant.task_id, merchant.behavior = task.id, 'moving'
                connection.execute('INSERT INTO task_effects VALUES (?, ?, ?)',
                    (state.world_id, task.id, encode({'action': 'TRANSPORT'})))
                events.append(event(state, 'task_scheduled', seq + len(events), merchant.id, None,
                                    {'task_id': task.id, 'action': 'TRANSPORT'}, [started.id], [merchant.id]))
                state.world_version += 1
                connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), state.world_id))
                for entry in events:
                    self.store.append_event(connection, state.world_id, entry)
                run = {'view': RunView(run_id=run_id, kind=body.kind, world_id=state.world_id,
                    profile_version=profile.version, status='running', mode=mode, measured=False,
                    strategy=choice.strategy).model_dump(mode='json'), 'evaluation_id': evaluation_id,
                    'started_at': self.store.clock(), 'start_seq': seq, 'cargo_remaining': config['cargo_initial'],
                    'gold_spent': spent, 'guard_gold': spent, 'task_id': task.id, 'choice': choice.model_dump(mode='json'),
                    'scenario_hash': data['session']['scenario_hash'], 'code_hash': self.code_hash}
                self.persist_run(connection, run)
                session = data['session']
                session['evaluation_version'] += 1
                session['status'] = {'first': 'first_running', 'second': 'second_running', 'rollback_check': 'rollback_running'}[body.kind]
                session['active_world_id'], session['mode'] = state.world_id, mode
                session['run_ids'].append(run_id)
                self.persist(connection, data)
                result = self.output(connection, data, body.request_id)
                self.store.remember(connection, scope, body, result)
                return result
        finally:
            self.turns.agents.release(scope, body.request_id, token)

    def guard(self, connection, world_id, body):
        row = connection.execute('SELECT body FROM evaluation_runs WHERE world_id=?', (world_id,)).fetchone()
        if row:
            run = json.loads(row[0])
            if run['view']['status'] != 'running':
                raise WorldError('INVALID_PHASE', '该评审任务已结束，不能再改变执行世界。', 409)
            if body.kind not in ('CHECKPOINT', 'HIT', 'TASK_REPORT'):
                raise WorldError('PRECONDITION_FAILED', '评审只接受位置、命中与任务报告。')
        else:
            self.store.require_ordinary(connection, world_id)

    def observe(self, connection, state, events):
        row = connection.execute('SELECT body FROM evaluation_runs WHERE world_id=?', (state.world_id,)).fetchone()
        if row is None:
            return
        run = json.loads(row[0])
        if run['view']['status'] != 'running':
            return
        data = self.row(connection, run['evaluation_id'])
        merchant_id = data['session']['learner_id']
        for hit in list(events):
            if hit.type == 'hit_applied' and hit.target_id == merchant_id:
                loss = min(run['cargo_remaining'], data['config']['cargo_loss_per_hit'])
                run['cargo_remaining'] -= loss
                events.append(event(state, 'cargo_lost', events[-1].event_seq + 1, merchant_id, None,
                    {'quantity': loss, 'cargo_remaining': run['cargo_remaining']}, [hit.id], [merchant_id]))
        merchant = next(actor for actor in state.actors if actor.id == merchant_id)
        task = next(task for task in state.tasks if task.id == run['task_id'])
        reason = None
        if not merchant.alive:
            reason = 'merchant_died'
        elif self.store.clock() - run['started_at'] >= data['config']['timeout_s']:
            reason = 'timeout'
        elif task.status in ('succeeded', 'failed', 'cancelled'):
            reason = 'arrived' if task.status == 'succeeded' else 'task_failed'
        if reason:
            self.finish(connection, data, run, state, events, reason)
        self.persist_run(connection, run)

    def finish(self, connection, data, run, state, events, reason):
        config = data['config']
        merchant = next(actor for actor in state.actors if actor.id == data['session']['learner_id'])
        delivered = run['cargo_remaining'] if reason == 'arrived' and merchant.alive else 0
        ratio = delivered / config['cargo_initial']
        metrics = RunMetrics(cargo_initial=config['cargo_initial'], cargo_delivered=delivered,
            gold_initial=config['gold_initial'], gold_spent=run['gold_spent'],
            duration_ms=max(0, int((self.store.clock() - run['started_at']) * 1000)),
            merchant_survived=merchant.alive, task_success=merchant.alive and ratio >= config['success_ratio'],
            delivered_ratio=ratio, reward=ratio - .1 * run['gold_spent'] / config['gold_initial'])
        previous = [row[0] for row in connection.execute(
            'SELECT id FROM events WHERE world_id=? AND seq>=? ORDER BY seq', (state.world_id, run['start_seq']))]
        seq = events[-1].event_seq + 1 if events else connection.execute(
            'SELECT MAX(seq) FROM events WHERE world_id=?', (state.world_id,)).fetchone()[0] + 1
        finished = event(state, run['view']['kind'] + '_finished', seq, merchant.id, None,
            {'run_id': run['view']['run_id'], 'reason': reason, 'metrics': metrics.model_dump(mode='json')},
            [*previous, *[entry.id for entry in events]], [merchant.id])
        events.append(finished)
        for task in state.tasks:
            if task.status in ('pending', 'running'):
                task.status = 'cancelled'
                events.append(event(state, 'task_cancelled', events[-1].event_seq + 1, task.actor_id, None,
                    {'task_id': task.id, 'reason': 'RUN_FINISHED'}, [finished.id], [task.actor_id]))
                actor = next(actor for actor in state.actors if actor.id == task.actor_id)
                actor.task_id, actor.behavior = None, 'idle' if actor.alive else 'dead'
        run['view'].update(status='finished', measured=True, metrics=metrics.model_dump(mode='json'),
                           source_event_ids=[*previous, *[entry.id for entry in events]])
        data['session']['status'] = {'first': 'learning', 'second': 'complete', 'rollback_check': 'rolled_back'}[run['view']['kind']]
        data['session']['evaluation_version'] += 1
        self.persist(connection, data)

    def expire(self):
        with self.store.connection(write=True) as connection:
            for row in connection.execute('SELECT body FROM evaluation_runs').fetchall():
                run = json.loads(row[0])
                if run['view']['status'] != 'running':
                    continue
                data = self.row(connection, run['evaluation_id'])
                if self.store.clock() - run['started_at'] < data['config']['timeout_s']:
                    continue
                state = StateView.model_validate_json(self.store.world_row(connection, run['view']['world_id'])['state'])
                events = []
                self.finish(connection, data, run, state, events, 'timeout')
                state.world_version += 1
                connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), state.world_id))
                for entry in events:
                    self.store.append_event(connection, state.world_id, entry)
                self.persist_run(connection, run)

    def get(self, evaluation_id):
        with self.store.connection() as connection:
            return self.output(connection, self.row(connection, evaluation_id), 'evaluation')

    async def learn_pending(self):
        with self.store.connection(write=True) as connection:
            candidates = [json.loads(row[0]) for row in connection.execute('SELECT body FROM evaluations')]
            data = next((value for value in candidates if value['session']['status'] == 'learning'
                and value.get('learning_lease_until', 0) <= self.store.clock()), None)
            if data is None:
                return
            run = json.loads(connection.execute('SELECT body FROM evaluation_runs WHERE id=?',
                (data['session']['run_ids'][0],)).fetchone()[0])
            profile = LearningProfile.model_validate(data['profile'])
            outcome = TransportOutcome(run_id=run['view']['run_id'], learner_id=profile.learner_id,
                context_key=profile.context_key, profile_version=profile.version,
                strategy=run['view']['strategy'], metrics=run['view']['metrics'],
                source_event_ids=run['view']['source_event_ids'])
            token = uuid4().hex
            data['learning_token'], data['learning_lease_until'] = token, self.store.clock() + 30
            version = data['session']['evaluation_version']
            self.persist(connection, data)
        provider, mode, rejection = self.learn_provider, 'fallback', None
        if provider is None:
            try:
                provider = importlib.import_module('server.agents.transport_learning').learn_transport
            except (ImportError, AttributeError):
                provider = None
        update = None
        if provider is not None:
            try:
                async def invoke():
                    async with self.turns.agents.gateway.semaphore:
                        return await asyncio.to_thread(provider, profile.model_copy(deep=True), outcome.model_copy(deep=True))
                raw = await asyncio.wait_for(invoke(), 8)
                update = validate_update(profile, outcome, raw)
                mode = 'live'
            except Exception:
                rejection = 'PROVIDER_FAILED_OR_INVALID_UPDATE'
        if update is None:
            update = validate_update(profile, outcome, fallback_update(profile, outcome))
        with self.store.connection(write=True) as connection:
            current = self.row(connection, data['session']['evaluation_id'])
            if (current['session']['status'] != 'learning' or current.get('learning_token') != token
                    or current['session']['evaluation_version'] != version or current['learning_update'] is not None):
                return
            world_id = run['view']['world_id']
            existing = {row[0] for row in connection.execute('SELECT id FROM events WHERE world_id=?', (world_id,))}
            if not set(update.source_event_ids) <= existing:
                raise WorldError('INVALID_LEARNING_UPDATE', '学习来源未写入本轮账本。')
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)['state'])
            seq = connection.execute('SELECT MAX(seq) FROM events WHERE world_id=?', (world_id,)).fetchone()[0] + 1
            audit = event(state, 'learning_committed', seq, profile.learner_id, None,
                {'source_run_id': outcome.run_id, 'from_version': profile.version, 'to_version': update.to_version,
                 'changed_values': {key: value.model_dump() for key, value in update.changed_values.items()},
                 'mode': mode, 'provider_rejection': rejection}, update.source_event_ids, [profile.learner_id])
            self.store.append_event(connection, world_id, audit)
            state.world_version += 1
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), world_id))
            current['profile'], current['learning_update'] = update.updated_profile.model_dump(mode='json'), update.model_dump(mode='json')
            current['learning_mode'] = mode
            current['learning_lease_until'] = 0
            current['session'].update(status='ready_for_second', active_profile_version=update.to_version,
                                      evaluation_version=version + 1)
            if mode == 'fallback':
                current['session']['mode'] = 'fallback'
            self.persist(connection, current)

    def report(self, evaluation_id):
        with self.store.connection() as connection:
            data = self.row(connection, evaluation_id)
            runs = [json.loads(row[0])['view'] for row in connection.execute(
                'SELECT body FROM evaluation_runs WHERE evaluation_id=? ORDER BY rowid', (evaluation_id,))]
            return Envelope[dict](request_id='report', ok=True, data={'session': data['session'], 'runs': runs,
                'learning_update': data['learning_update'], 'comparable': False, 'improvement': 'not_measured',
                'notes': data['notes']}).model_dump(mode='json')
