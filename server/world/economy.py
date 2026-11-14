"""Atomic offers, accounts, organization consent and material consumption."""
import json
from uuid import uuid4

from shared.protocol import Event, ItemState, ItemStats, RelationView, StateView
from server.world.commands import WorldError
from server.world.items import living_actor, require_near, apply_item_command


SCHEMA = '''
CREATE TABLE IF NOT EXISTS wallets (world_id TEXT NOT NULL, actor_id TEXT NOT NULL, gold INTEGER NOT NULL,
    PRIMARY KEY(world_id, actor_id));
CREATE TABLE IF NOT EXISTS offers (world_id TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, id));
CREATE TABLE IF NOT EXISTS world_economy_rules (world_id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS resource_needs (world_id TEXT NOT NULL, org_id TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(world_id, org_id));
CREATE TABLE IF NOT EXISTS migration_sources (world_id TEXT NOT NULL, event_id TEXT NOT NULL, npc_id TEXT NOT NULL,
    PRIMARY KEY(world_id, event_id));
'''
RULES = {'starting_gold': 20, 'recipes': {
    'iron_sword': {'materials': {'iron': 2, 'wood': 1}, 'name': '锻造铁剑', 'base_type': 'sword',
                   'material_id': 'iron', 'stats': {'damage': 6, 'cooldown_s': .5, 'armor': 0}},
    'herb_bundle': {'materials': {'herb': 2}, 'name': '药草包', 'base_type': 'consumable',
                    'material_id': 'herb', 'stats': {'damage': 0, 'cooldown_s': 1, 'armor': 0}}}}


def initialize(connection, state):
    connection.execute('INSERT OR IGNORE INTO world_economy_rules VALUES (?, ?)',
                       (state.world_id, json.dumps(RULES)))
    rules = json.loads(connection.execute('SELECT body FROM world_economy_rules WHERE world_id=?', (state.world_id,)).fetchone()[0])
    for actor in state.actors:
        connection.execute('INSERT OR IGNORE INTO wallets VALUES (?, ?, ?)',
                           (state.world_id, actor.id, rules['starting_gold'] if actor.kind != 'monster' else 0))
    return rules


def emit(state, kind, seq, actor_id, target_id, facts, sources=()):
    witnesses = [value for value in (actor_id, target_id) if value]
    return Event(id='evt_' + uuid4().hex, event_seq=seq, tick=state.tick, type=kind,
                 actor_id=actor_id, target_id=target_id, facts=facts, caused_by=list(sources), witness_ids=witnesses)


def organization(state, org_id, representative=None):
    org = next((value for value in state.organizations if value.id == org_id and value.status == 'active'), None)
    if org is None or representative is not None and org.representative_id != representative:
        raise WorldError('NOT_AUTHORIZED', '组织无效或本人不是当前代表。')
    return org


def offer(connection, state, body, seq, sources=()):
    actor, target = living_actor(state, body.actor_id), living_actor(state, body.target_id)
    if actor.id == target.id:
        raise WorldError('PRECONDITION_FAILED', '提议需要另一位参与者。')
    require_near(actor, target.region_id, target.tile)
    if body.kind == 'trade':
        item = next((item for item in state.items if item.id == body.item_id and item.owner_id == actor.id), None)
        if item is None:
            raise WorldError('ITEM_NOT_OWNED', '卖方没有该物品。')
    else:
        organization(state, body.org_id, actor.id)
        if body.kind == 'relation':
            organization(state, body.target_org_id, target.id)
            if body.org_id == body.target_org_id:
                raise WorldError('PRECONDITION_FAILED', '合作需要不同组织。')
    offer_id = 'offer_' + uuid4().hex
    created = emit(state, 'offer_created', seq, actor.id, target.id,
                   {'offer_id': offer_id, 'kind': body.kind}, sources)
    value = body.model_dump(mode='json', exclude={'request_id', 'expected_world_version', 'api_version'})
    value.update(id=offer_id, status='pending', expires_tick=state.tick + body.expires_in_ticks,
                 source_event_ids=[created.id])
    connection.execute('INSERT INTO offers VALUES (?, ?, ?)', (state.world_id, offer_id, json.dumps(value)))
    return [created]


def accept(connection, state, actor_id, offer_id, seq, org_id=None):
    row = connection.execute('SELECT body FROM offers WHERE world_id=? AND id=?', (state.world_id, offer_id)).fetchone()
    if row is None:
        raise WorldError('OFFER_NOT_FOUND', '提议不存在。', 404)
    value = json.loads(row[0])
    if value['status'] != 'pending' or value['expires_tick'] <= state.tick or value['target_id'] != actor_id:
        raise WorldError('OFFER_INVALID', '提议过期、已处理或不属于该接收人。')
    actor, proposer = living_actor(state, actor_id), living_actor(state, value['actor_id'])
    require_near(actor, proposer.region_id, proposer.tile)
    events = []
    if org_id is not None and (value['kind'] != 'invite' or value['org_id'] != org_id):
        raise WorldError('NOT_AUTHORIZED', '该邀请不对应请求的组织。')
    if value['kind'] == 'trade':
        initialize(connection, state)
        balance = connection.execute('SELECT gold FROM wallets WHERE world_id=? AND actor_id=?', (state.world_id, actor.id)).fetchone()[0]
        if balance < value['price']:
            raise WorldError('INSUFFICIENT_FUNDS', '买方余额不足。')
        events = apply_item_command(state, 'GIVE', {'actor_id': proposer.id, 'target_id': actor.id,
                                                  'item_id': value['item_id']}, seq)
        events[0].caused_by = value['source_event_ids']
        connection.execute('UPDATE attacks SET valid=0 WHERE world_id=? AND attacker_id=?', (state.world_id, proposer.id))
        connection.execute('UPDATE wallets SET gold=gold-? WHERE world_id=? AND actor_id=?', (value['price'], state.world_id, actor.id))
        connection.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?', (value['price'], state.world_id, proposer.id))
    elif value['kind'] == 'invite':
        org = organization(state, value['org_id'], proposer.id)
        if actor.id in org.member_ids:
            raise WorldError('PRECONDITION_FAILED', '角色已经在该组织中。')
        org.member_ids.append(actor.id)
        actor.org_ids.append(org.id)
    else:
        left = organization(state, value['org_id'], proposer.id)
        right = organization(state, value['target_org_id'], actor.id)
        for origin, destination in ((left.id, right.id), (right.id, left.id)):
            state.relations = [relation for relation in state.relations
                               if (relation.from_org_id, relation.to_org_id) != (origin, destination)]
            state.relations.append(RelationView(from_org_id=origin, to_org_id=destination,
                stance=value['stance'], trust=0, source_event_ids=value['source_event_ids']))
    events.append(emit(state, 'offer_accepted', seq + len(events), actor.id, proposer.id,
        {'offer_id': offer_id, 'kind': value['kind'], 'price': value['price'], 'org_id': value['org_id'],
         'target_org_id': value['target_org_id'], 'stance': value['stance']}, value['source_event_ids']))
    if value['kind'] == 'relation':
        for relation in state.relations:
            if {relation.from_org_id, relation.to_org_id} == {value['org_id'], value['target_org_id']}:
                relation.source_event_ids = [events[-1].id]
    value['status'] = 'accepted'
    connection.execute('UPDATE offers SET body=? WHERE world_id=? AND id=?', (json.dumps(value), state.world_id, offer_id))
    return events


def leave(state, actor_id, org_id, seq):
    actor = living_actor(state, actor_id)
    org = organization(state, org_id)
    if actor.id not in org.member_ids:
        raise WorldError('NOT_AUTHORIZED', '角色不是该组织成员。')
    actor.org_ids = [value for value in actor.org_ids if value != org.id]
    org.member_ids = [value for value in org.member_ids if value != actor.id]
    if org.representative_id == actor.id:
        org.representative_id = next(iter(sorted(org.member_ids)), None)
    if not org.member_ids:
        org.status = 'inactive'
    return [emit(state, 'organization_member_left', seq, actor.id, None,
                 {'org_id': org.id, 'representative_id': org.representative_id})]


def craft(connection, state, actor_id, recipe_id, seq, sources=()):
    actor = living_actor(state, actor_id)
    rules = initialize(connection, state)
    recipe = rules['recipes'].get(recipe_id)
    if recipe is None:
        raise WorldError('RECIPE_NOT_FOUND', '没有这份制造配方。')
    consumed = []
    for material, quantity in recipe['materials'].items():
        matches = sorted((item for item in state.items if item.owner_id == actor.id
                          and item.base_type == 'material' and item.material_id == material), key=lambda item: item.id)
        if len(matches) < quantity:
            raise WorldError('INSUFFICIENT_MATERIALS', '制造材料不足。')
        consumed.extend(matches[:quantity])
    crafted = emit(state, 'item_crafted', seq, actor.id, None,
        {'recipe_id': recipe_id, 'consumed_item_ids': [item.id for item in consumed]},
        list(dict.fromkeys([*sources, *[source for item in consumed for source in item.origin_event_ids]])))
    item = ItemState(id='item_' + uuid4().hex, name=recipe['name'], base_type=recipe['base_type'],
        material_id=recipe['material_id'], quality='common', stats=ItemStats.model_validate(recipe['stats']),
        owner_id=actor.id, origin_event_ids=[crafted.id])
    crafted.facts['item_id'] = item.id
    ids = {item.id for item in consumed}
    state.items = [value for value in state.items if value.id not in ids] + [item]
    return [crafted]


def reconcile(connection, state, events):
    if not events:
        return
    alive = {actor.id for actor in state.actors if actor.alive}
    for row in connection.execute('SELECT id, body FROM offers WHERE world_id=?', (state.world_id,)).fetchall():
        value = json.loads(row['body'])
        if value['status'] != 'pending':
            continue
        valid = value['actor_id'] in alive and value['target_id'] in alive and value['expires_tick'] > state.tick
        if value['kind'] != 'trade':
            for org_id, rep in ((value['org_id'], value['actor_id']), (value['target_org_id'], value['target_id'])):
                if org_id:
                    valid = valid and any(org.id == org_id and org.status == 'active' and org.representative_id == rep
                                          for org in state.organizations)
        if not valid:
            value['status'] = 'cancelled'
            connection.execute('UPDATE offers SET body=? WHERE world_id=? AND id=?',
                               (json.dumps(value), state.world_id, row['id']))
            events.append(emit(state, 'offer_cancelled', events[-1].event_seq + 1, value['actor_id'], value['target_id'],
                               {'offer_id': row['id'], 'reason': 'EXPIRED_OR_AUTHORITY_CHANGED'}, value['source_event_ids']))


class EconomyAPI:
    def __init__(self, store):
        self.store = store

    def mutate(self, world_id, body, operation):
        from server.storage.sqlite import response
        scope = world_id + '/' + operation
        with self.store.connection(write=True) as connection:
            cached = self.store.cached(connection, scope, body)
            if cached is not None:
                return cached
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)['state'])
            self.store.require_ordinary(connection, world_id)
            if state.world_version != body.expected_world_version:
                raise WorldError('VERSION_CONFLICT', '世界版本已变化。', 409)
            seq = connection.execute('SELECT MAX(seq) FROM events WHERE world_id=?', (world_id,)).fetchone()[0] + 1
            events = offer(connection, state, body, seq) if operation == 'offers' else craft(
                connection, state, body.actor_id, body.recipe_id, seq)
            state.world_version += 1
            connection.execute('UPDATE worlds SET state=? WHERE id=?', (state.model_dump_json(), world_id))
            for entry in events:
                self.store.append_event(connection, world_id, entry)
            result = response(body.request_id, state, {'state': state.model_dump(mode='json'),
                                                       'events': [entry.model_dump(mode='json') for entry in events]})
            self.store.remember(connection, scope, body, result)
            return result

    def view(self, world_id):
        from server.storage.sqlite import response
        with self.store.connection() as connection:
            state = StateView.model_validate_json(self.store.world_row(connection, world_id)['state'])
            wallets = {row['actor_id']: row['gold'] for row in connection.execute('SELECT * FROM wallets WHERE world_id=?', (world_id,))}
            offers = [json.loads(row[0]) for row in connection.execute('SELECT body FROM offers WHERE world_id=?', (world_id,))]
            rules = json.loads(connection.execute('SELECT body FROM world_economy_rules WHERE world_id=?', (world_id,)).fetchone()[0])
            needs = [json.loads(row[0]) for row in connection.execute('SELECT body FROM resource_needs WHERE world_id=?', (world_id,))]
            return response('economy', state, {'wallets': wallets, 'offers': offers, 'recipes': rules['recipes'], 'resource_needs': needs})
