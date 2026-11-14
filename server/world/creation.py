"""Material-backed, source-linked creation; narrative never grants mechanical powers."""
from uuid import uuid4
from shared.protocol import ItemState, ItemStats
from shared.world_protocol import OfferRequest
from server.world.commands import WorldError
from server.world.items import living_actor, require_near
from server.world import economy


def execute(connection, state, context, proposal, seq, decision_id):
    actor = living_actor(state, context.npc_id)
    buyer = living_actor(state, state.player_id)
    require_near(actor, buyer.region_id, buyer.tile)
    known = {e.id for e in context.known_events}
    if not set(proposal.source_event_ids) <= known:
        raise WorldError('UNKNOWN_EVIDENCE', '创造提案引用了未知事件。')
    ids = set(proposal.ingredient_ids)
    if len(ids) != len(proposal.ingredient_ids):
        raise WorldError('INVALID_INGREDIENTS', '材料不能重复计数。')
    ingredients = [i for i in state.items if i.id in ids and i.owner_id == actor.id and i.base_type == 'material']
    if len(ingredients) != len(ids):
        raise WorldError('INSUFFICIENT_MATERIALS', '必须消耗本人实际持有的原料。')
    # The first primitive creates a tradeable crafted object, not executable effects.
    created = economy.emit(state, 'content_created', seq, actor.id, buyer.id,
        {'name': proposal.name, 'description': proposal.description,
         'ingredient_ids': sorted(ids), 'mechanical_effects': []},
        list(dict.fromkeys([decision_id, *proposal.source_event_ids,
                           *[s for i in ingredients for s in i.origin_event_ids]])))
    item = ItemState(id='item_' + uuid4().hex, name=proposal.name, base_type='consumable',
        quality='common', material_id=ingredients[0].material_id,
        stats=ItemStats(damage=0, armor=0, cooldown_s=1), owner_id=actor.id,
        origin_event_ids=[created.id])
    created.facts['item_id'] = item.id
    state.items = [i for i in state.items if i.id not in ids] + [item]
    offer = OfferRequest(request_id=decision_id, expected_world_version=state.world_version,
        actor_id=actor.id, target_id=buyer.id, kind='trade', item_id=item.id, price=proposal.price)
    return [created, *economy.offer(connection, state, offer, seq + 1, [created.id])]
