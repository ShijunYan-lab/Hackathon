"""Immutable world snapshots and isolated branches, with explicit table ownership."""
import hashlib
import json
from uuid import uuid4

from shared.protocol import StateView
from server.storage.sqlite import encode, response
from server.world.commands import WorldError


# Add every new world-owned table here; transient model leases deliberately stay out.
WORLD_TABLES = ('events', 'world_combat_rules', 'attacks', 'attack_hits', 'knowledge_index',
    'event_knowledge', 'npc_memories', 'world_memories', 'story_threads', 'task_effects',
    'task_reports', 'npc_profiles', 'decisions', 'world_runtime', 'director_runs', 'director_focus',
    'story_chapters', 'wallets', 'offers', 'world_economy_rules', 'resource_needs', 'migration_sources', 'npc_dialogue_turns', 'world_life')


def digest(value):
    return hashlib.sha256(encode(value).encode('utf-8')).hexdigest()


class Snapshots:
    def __init__(self, store):
        self.store = store
        with store.connection() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS saves (
                    id TEXT PRIMARY KEY, world_id TEXT NOT NULL, label TEXT NOT NULL,
                    body TEXT NOT NULL, hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS world_branches (
                    world_id TEXT PRIMARY KEY, parent_save_id TEXT NOT NULL
                );
            ''')

    def capture(self, connection, world_id):
        world = dict(self.store.world_row(connection, world_id))
        tables = {}
        present = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in WORLD_TABLES:
            if table in present:
                tables[table] = [dict(row) for row in connection.execute(
                    f'SELECT * FROM {table} WHERE world_id=? ORDER BY rowid', (world_id,))]
        # Preserve settled request ids, but never copy in-flight model executions.
        requests = [dict(row) for row in connection.execute(
            'SELECT * FROM requests WHERE scope >= ? AND scope < ? AND scope != ? ORDER BY rowid',
            (world_id + '/', world_id + '0', world_id + '/saves'))]
        checkpoints = [dict(row) for row in connection.execute(
            'SELECT * FROM checkpoint_requests WHERE scope=? ORDER BY rowid', (world_id + '/commands',))]
        return {'format': 1, 'world': world, 'tables': tables, 'requests': requests,
                'checkpoint_requests': checkpoints, 'saved_at': self.store.clock()}

    def write(self, connection, world_id, label):
        snapshot = self.capture(connection, world_id)
        save_id = 'save_' + uuid4().hex
        connection.execute('INSERT INTO saves VALUES (?, ?, ?, ?, ?)',
                           (save_id, world_id, label, encode(snapshot), digest(snapshot)))
        return save_id

    def read(self, connection, save_id):
        row = connection.execute('SELECT body, hash FROM saves WHERE id=?', (save_id,)).fetchone()
        if row is None:
            raise WorldError('SAVE_NOT_FOUND', '存档不存在。', 404)
        snapshot = json.loads(row['body'])
        if snapshot['format'] != 1 or digest(snapshot) != row['hash']:
            raise WorldError('SNAPSHOT_MISMATCH', '存档校验失败。', 409)
        return snapshot

    def branch(self, connection, save_id):
        snapshot = self.read(connection, save_id)
        previous_id = snapshot['world']['id']
        world_id = 'world_' + uuid4().hex
        state = StateView.model_validate_json(snapshot['world']['state'])
        state.world_id = world_id
        # Keep the saved version: inherited command responses still describe this boundary.
        connection.execute('INSERT INTO worlds VALUES (?, ?, ?, ?)',
            (world_id, state.model_dump_json(), snapshot['world']['region'], snapshot['world']['rng_state']))
        for table, rows in snapshot['tables'].items():
            if table not in WORLD_TABLES:
                raise WorldError('SNAPSHOT_MISMATCH', '存档包含未知数据表。', 409)
            for original in rows:
                row = dict(original)
                row['world_id'] = world_id
                if table == 'attacks':
                    row['started_at'] += self.store.clock() - snapshot['saved_at']
                    row['valid'] = 0  # Never resume an animation's partial multi-target swing.
                if table == 'director_runs':
                    body = json.loads(row['body'])
                    body['result']['world_id'] = world_id
                    row['body'] = encode(body)
                columns = ','.join(row)
                connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in row)})",
                                   tuple(row.values()))
        for table in ('requests', 'checkpoint_requests'):
            for row in snapshot.get(table, []):
                result = json.loads(row['response'])
                result['world_id'] = world_id
                if result.get('data', {}).get('state'):
                    result['data']['state']['world_id'] = world_id
                connection.execute(f'INSERT INTO {table} VALUES (?, ?, ?, ?)',
                    (world_id + row['scope'][len(previous_id):], row['id'], row['body'], encode(result)))
        connection.execute('INSERT INTO world_branches VALUES (?, ?)', (world_id, save_id))
        from server.world.economy import initialize
        initialize(connection, state)
        return state

    def save(self, world_id, body):
        scope = world_id + '/saves'
        with self.store.connection(write=True) as connection:
            cached = self.store.cached(connection, scope, body)
            if cached is not None:
                return cached
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)['state'])
            self.store.require_ordinary(connection, world_id)
            if state.world_version != body.expected_world_version:
                raise WorldError('VERSION_CONFLICT', '世界版本已变化，请刷新。', 409)
            if any(actor.behavior == 'attacking' for actor in state.actors):
                raise WorldError('PRECONDITION_FAILED', '请等攻击动画结束再存档。')
            # A save is a world boundary: pending model results must become stale.
            state.world_version += 1
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), world_id))
            save_id = self.write(connection, world_id, body.label)
            result = response(body.request_id, state, {'save_id': save_id,
                'saved_world_version': state.world_version, 'state': state.model_dump(mode='json')})
            self.store.remember(connection, scope, body, result)
            return result

    def load(self, save_id, body):
        scope = save_id + '/load'
        with self.store.connection(write=True) as connection:
            cached = self.store.cached(connection, scope, body)
            if cached is not None:
                return cached
            state = self.branch(connection, save_id)
            result = response(body.request_id, state, {'new_world_id': state.world_id,
                'parent_save_id': save_id, 'state': state.model_dump(mode='json')})
            self.store.remember(connection, scope, body, result)
            return result
