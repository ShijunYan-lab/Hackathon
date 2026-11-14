"""Rule-checked resource requests and bounded migration; suggestions aren't facts."""
import json
import random
from uuid import uuid4

from shared.protocol import ActorState, Event
from server.generation.equipment import generate_weapon
from server.world.commands import WorldError, apply_checkpoint
from server.world.economy import initialize, organization
from server.world.tasks import event


def tuple_tree(value):
    return tuple(tuple_tree(item) for item in value) if isinstance(value, list) else value


def execute(connection, state, proposal, config, region, seq):
    candidate = state.model_copy(deep=True)
    connection.execute('SAVEPOINT director_execution')
    try:
        if proposal.kind == 'RESOURCE_NEED':
            org = organization(candidate, proposal.target_id)
            if proposal.resource not in config.resource_limits or proposal.quantity > config.resource_limits[proposal.resource]:
                raise WorldError('RESOURCE_NOT_SUPPORTED', '资源或需求量超出配置。')
            if org.resources.get(proposal.resource, 0) >= proposal.quantity:
                raise WorldError('NEED_NOT_PRESENT', '组织资源已达到需求量。')
            prior = connection.execute('SELECT body FROM resource_needs WHERE world_id=? AND org_id=?',
                                       (state.world_id, org.id)).fetchone()
            if prior and json.loads(prior[0])['status'] == 'open':
                raise WorldError('NEED_ALREADY_OPEN', '组织已有待处理需求。')
            actual = event(candidate, 'resource_need_created', seq, org.representative_id, None,
                {'org_id': org.id, 'resource': proposal.resource,
                 'quantity': proposal.quantity - org.resources.get(proposal.resource, 0), 'status': 'open',
                 'reason_summary': proposal.reason_summary}, proposal.source_event_ids, [org.representative_id])
            connection.execute('INSERT OR REPLACE INTO resource_needs VALUES (?, ?, ?)',
                (state.world_id, org.id, json.dumps({**actual.facts, 'source_event_ids': [actual.id]})))
        elif proposal.kind == 'MIGRATION':
            if sum(actor.alive and actor.kind == 'npc' for actor in state.actors) >= config.npc_alive_limit:
                raise WorldError('POPULATION_LIMIT', '人口已达上限。')
            location = next((value for value in config.locations if value.id == proposal.location_id
                             and 'migration_entry' in value.tags), None)
            if location is None or location.region_id != state.current_region_id:
                raise WorldError('INVALID_ENTRY', '迁入需要当前地图已配置的入口。')
            source = None
            for source_id in proposal.source_event_ids:
                row = connection.execute('SELECT body FROM events WHERE world_id=? AND id=?', (state.world_id, source_id)).fetchone()
                used = connection.execute('SELECT 1 FROM migration_sources WHERE world_id=? AND event_id=?',
                                          (state.world_id, source_id)).fetchone()
                source_event = Event.model_validate_json(row[0]) if row else None
                if source_event and source_event.type == 'actor_died' and not used and any(
                        actor.id == source_event.target_id and actor.kind == 'npc' and not actor.alive for actor in state.actors):
                    source = source_id
                    break
                if source_event and source_event.type == 'resource_need_created' and not used:
                    demand = connection.execute('SELECT body FROM resource_needs WHERE world_id=? AND org_id=?',
                        (state.world_id, source_event.facts.get('org_id'))).fetchone()
                    if demand and json.loads(demand[0])['status'] == 'open' and source_id in json.loads(demand[0])['source_event_ids']:
                        source = source_id
                        break
            if source is None:
                raise WorldError('NO_MIGRATION_CAUSE', '迁入需要尚未使用的死亡或未解决资源需求来源。')
            npc_id = 'npc_' + uuid4().hex
            npc = ActorState(id=npc_id, name=proposal.npc_name, kind='npc', alive=True, hp=45, max_hp=45, armor=0,
                region_id=location.region_id, tile=location.tile, appearance_key='traveler')
            candidate.actors.append(npc)
            apply_checkpoint(candidate, {'region_id': location.region_id, 'positions': [
                {'actor_id': npc_id, 'tile': location.tile.model_dump()}]}, region)
            actual = event(candidate, 'npc_migrated', seq, npc_id, None,
                {'location_id': location.id, 'reused_death_identity': False,
                 'invitation_org_id': source_event.facts.get('org_id') if source_event.type == 'resource_need_created' else None,
                 'reason_summary': proposal.reason_summary}, proposal.source_event_ids, [npc_id])
            rng = random.Random()
            rng.setstate(tuple_tree(json.loads(connection.execute('SELECT rng_state FROM worlds WHERE id=?', (state.world_id,)).fetchone()[0])))
            weapon = generate_weapon(rng, 'item_' + uuid4().hex, npc.id, actual.id)
            npc.equipped_item_id, npc.armor = weapon.id, weapon.stats.armor
            candidate.items.append(weapon)
            initialize(connection, candidate)
            connection.execute('UPDATE worlds SET rng_state=? WHERE id=?', (json.dumps(rng.getstate()), state.world_id))
            connection.execute('INSERT INTO migration_sources VALUES (?, ?, ?)', (state.world_id, source, npc_id))
        else:
            raise WorldError('ACTION_NOT_SUPPORTED', '未知导演执行器。')
        connection.execute('RELEASE director_execution')
        return candidate, actual, True
    except (WorldError, ValueError) as exc:
        connection.execute('ROLLBACK TO director_execution')
        connection.execute('RELEASE director_execution')
        rejected = event(state, 'director_proposal_rejected', seq, None, proposal.target_id,
            {'kind': proposal.kind, 'reason': getattr(exc, 'code', 'INVALID_ENTRY')}, proposal.source_event_ids, [])
        return state, rejected, False
