"""R7 authoritative contracts, ecology, information and NPC livelihoods.

Model proposals select supported primitives. Every effect consumes real resources;
movement completes through the existing visible client task reports.
"""
import json
import math
import re
from uuid import uuid4
from pathlib import Path

from shared.protocol import ActorState, ItemState, ItemStats, SiteView, Task, Tile
from server.world.commands import WorldError
from server.world.items import living_actor, require_near
from server.world.tasks import event
from server.world import living_world as life

MATERIALS = {'herb': '草药', 'wood': '木材', 'stone': '石头', 'iron': '铁矿'}
PERIODS = {'herb': 6, 'wood': 10, 'stone': 14, 'iron': 18}
# The map's canonical landmarks, never supplied by model output.
_locations_file = Path(__file__).resolve().parents[2] / 'game/maps/director_locations.json'
LOCATIONS = json.loads(_locations_file.read_text(encoding='utf-8'))['locations']

_SCENE_PROPS = json.loads((Path(__file__).resolve().parents[2] / 'game/maps/scene_props.json').read_text(encoding='utf-8'))['props']
WORKSTATIONS = tuple(p for p in _SCENE_PROPS if p.get('kind') in ('anvil', 'furnace', 'workbench'))


def nearest_workstation(tile):
    if not WORKSTATIONS: return None, float('inf')
    target = min(WORKSTATIONS, key=lambda p: math.hypot(tile.x-p['tile']['x'], tile.y-p['tile']['y']))
    return target, math.hypot(tile.x-target['tile']['x'], tile.y-target['tile']['y'])


def workstation_reachable(c, s, actor, region, source, action, item_ids):
    workstation, distance = nearest_workstation(actor.tile)
    if not workstation or distance > 36: return False
    tile = life.free_tile(region, workstation['tile']['x'], workstation['tile']['y'])
    task = life._schedule(c, s, actor, tile, 'MOVE', source, region,
                          effect={'action': action, 'item_ids': item_ids,
                                  'workstation_id': workstation['id']})
    return bool(task)


def finish_npc_production(s, npc, source, seq, work_kind, item_ids):
    station, distance = nearest_workstation(npc.tile)
    if not station or distance > 3.5: return None
    items = [next((i for i in s.items if i.id == identifier and i.owner_id == npc.id), None)
             for identifier in item_ids]
    if len(items) != len(item_ids) or any(i is None for i in items): return None
    if work_kind == 'NPC_REPAIR':
        if len(items) != 2 or items[0].base_type != 'material' or items[0].material_id != 'iron'                 or items[1].durability >= 100 or items[1].id not in equipped(s,npc): return None
        ore, gear = items
        s.items.remove(ore)
        gear.durability = 100
        return event(s, 'equipment_repaired', seq, npc.id, gear.id,
                     {'item_name': gear.name, 'workstation_id': station['id']},
                     [source,*ore.origin_event_ids], life.near_witnesses(s,npc.tile))
    if work_kind == 'NPC_CRAFT':
        if len(items) != 3 or sorted(i.material_id for i in items) != ['iron','iron','wood']: return None
        for item in items: s.items.remove(item)
        e = event(s,'item_crafted',seq,npc.id,None,
                  {'workstation_id':station['id']},
                  [source,*[x for item in items for x in item.origin_event_ids]][:16],
                  life.near_witnesses(s,npc.tile))
        rng=life._rng(s,'npc_craft:'+npc.id)
        tool=life._new_item(s,npc.id,e.id,rng,quality='uncommon',kind='sword')
        e.facts['item_id']=tool.id
        e.facts['text']='Used an existing workshop to forge equipment from owned materials.'
        previous=next((i for i in s.items if i.id==npc.equipped_item_id),None)
        if previous is None or tool.stats.damage > previous.stats.damage: npc.equipped_item_id=tool.id
        return e
    return None


# All NPC map knowledge must have a source: own home, actual travel, or
# locally visible landmarks. The global map is never dumped to an NPC prompt.
def known_places(actor, person):
    home = person.get('home_tile') if isinstance(person, dict) else None
    visited = set(person.get('visited_place_ids', [])) if isinstance(person, dict) else set()
    result = []
    for location in LOCATIONS:
        tile = location['tile']
        current = math.hypot(actor.tile.x-tile['x'], actor.tile.y-tile['y']) <= 25
        at_home = bool(home) and math.hypot(home['x']-tile['x'], home['y']-tile['y']) <= 25
        if current or at_home or location['id'] in visited:
            # Keep only actual, grounded geography; precise coordinates remain
            # an internal world primitive rather than text for player dialogue.
            result.append({'id': location['id'], 'name': location['name'],
                           'region_id': location['region_id'], 'tags': location.get('tags', [])})
    return result


def record_visits(state, metadata):
    for actor in state.actors:
        if actor.kind != 'npc' or not actor.alive: continue
        person = metadata.get('people', {}).get(actor.id)
        if not person: continue
        visited = set(person.get('visited_place_ids', []))
        for location in LOCATIONS:
            if math.hypot(actor.tile.x-location['tile']['x'], actor.tile.y-location['tile']['y']) <= 15:
                visited.add(location['id'])
        person['visited_place_ids'] = sorted(visited)



def place(tile):
    nearest = min(LOCATIONS, key=lambda p: math.hypot(p['tile']['x']-tile.x, p['tile']['y']-tile.y))
    distance = math.hypot(nearest['tile']['x']-tile.x, nearest['tile']['y']-tile.y)
    if distance > 45:
        dx=tile.x-nearest['tile']['x']
        dy=tile.y-nearest['tile']['y']
        horizontal='东' if dx>12 else ('西' if dx< -12 else '')
        vertical='南' if dy>12 else ('北' if dy< -12 else '')
        direction=vertical+horizontal or '附近'
        return nearest['name']+'往'+direction+'方的荒野（路程较远）'
    return nearest['name'] + '附近'


def wallet(c, s, actor):
    row = c.execute('SELECT gold FROM wallets WHERE world_id=? AND actor_id=?', (s.world_id, actor)).fetchone()
    return row[0] if row else 0


def transfer_gold(c, s, payer, payee, amount):
    if type(amount) is not int or amount < 0 or wallet(c, s, payer) < amount:
        raise WorldError('INSUFFICIENT_FUNDS', '金币不足。')
    c.execute('UPDATE wallets SET gold=gold-? WHERE world_id=? AND actor_id=?', (amount, s.world_id, payer))
    c.execute('INSERT INTO wallets VALUES (?,?,?) ON CONFLICT(world_id,actor_id) DO UPDATE SET gold=gold+excluded.gold', (s.world_id, payee, amount))


def sync_coins(c, s):
    """Currency items are a read-only projection of the single wallet ledger."""
    s.items = [i for i in s.items if i.material_id != 'currency']
    for row in c.execute('SELECT actor_id,gold FROM wallets WHERE world_id=? AND gold>0', (s.world_id,)):
        s.items.append(ItemState(id='coins_'+row[0], name='金币', base_type='consumable', material_id='currency',
            quality='common', owner_id=row[0], quantity=row[1], stats=ItemStats(damage=0, armor=0, cooldown_s=1)))


def equipped(s, a):
    return {a.equipped_item_id, *a.equipped_slots.values()}


def stock_owners(s,a):
    box=life.merchant_box(s,a.id)
    return [a.id]+([box['id']] if box and life.distance(a.tile,Tile(**box['tile']))<=4 else [])


def tradable(s, a, owner=None):
    reserved = {q.get('item_id') for q in s.quests if q['status'] in ('open', 'active')}
    return [i for i in s.items if i.owner_id == (owner or a.id) and i.id not in equipped(s, a)
            and i.id not in reserved and i.material_id not in ('currency', 'coins')]


def initialize(c, s, region, source):
    meta = life.read(c, s.world_id)
    if not meta or meta.get('r7_initialized'): return
    meta['r7_initialized'] = True
    s.safe_zones = [{'name': p['name'], 'tile': p['tile'], 'radius': 18}
                    for p in LOCATIONS if 'village' in p.get('tags', [])]
    rng = life._rng(s, 'r7_ecology')
    # Keep fixed sites and add seeded natural deposits, all on reachable ground.
    for site in s.sites:
        site.capacity = max(3, site.remaining)
        site.regen_tick = s.tick + PERIODS.get(site.kind, 10)
    for index in range(40):
        kind = list(MATERIALS)[index % 4]
        center = life.FORESTS[index % len(life.FORESTS)] if kind in ('wood','iron') else life.WAYPOINTS[index % len(life.WAYPOINTS)]
        tile = life.free_tile(region, center[0]+rng.randint(-12,12), center[1]+rng.randint(-12,12))
        s.sites.append(SiteView(id='site_'+uuid4().hex, kind=kind, region_id=s.current_region_id,
            tile=tile, remaining=3, capacity=3, regen_tick=s.tick+PERIODS[kind]))
    for zone in s.safe_zones:
        zone['guard_ids'] = []
        for n in range(2):
            guard = spawn_guard(c, s, region, meta, zone, source, n)
            zone['guard_ids'].append(guard.id)
        tile = life.free_tile(region, zone['tile']['x']+3, zone['tile']['y'])
        s.notices.append({'id':'board_'+uuid4().hex,'kind':'board','label':'酒馆告示牌',
            'region_id':s.current_region_id,'tile':tile.model_dump(),'zone':zone['name']})
    for a in s.actors:
        if a.kind == 'monster':
            if inside_safe(s, a.tile):
                a.tile = life.free_tile(region, 110, 95)
            if rng.random() < .2:
                a.appearance_key='elite_'+rng.choice(['wolf','boar','spider','ghoul','swamp','raven'])
                w = next((i for i in s.items if i.id == a.equipped_item_id), None)
                if w:
                    from server.world.monster_ecology import get_species, apply_species
                    w.base_type = get_species(a.appearance_key).weapon
                    apply_species(a, w)
                drop = life._new_item(s,a.id,source,rng,quality='rare')
    # High-quality equipment is scarce; most caches contain materials instead.
    for box in s.containers:
        if box['kind'] != 'cache': continue
        gear = [i for i in s.items if i.owner_id == box['id'] and i.base_type not in ('consumable','material')]
        for i in gear:
            if rng.random() < .8: s.items.remove(i)
        material(s,box['id'],rng.choice(list(MATERIALS)),source)
    record_visits(s,meta)
    life.write(c,s.world_id,meta)
    sync_coins(c,s)


def inside_safe(s, tile):
    return any(math.hypot(tile.x-z['tile']['x'],tile.y-z['tile']['y']) <= z['radius'] for z in s.safe_zones)


def spawn_guard(c,s,region,meta,zone,source,index=0):
    meta['serial'] += 1
    tile=life.free_tile(region,zone['tile']['x']+index*3,zone['tile']['y']+4,[a.tile for a in s.actors if a.alive])
    a=ActorState(id='npc_'+uuid4().hex,kind='npc',name='卫兵'+str(meta['serial']),alive=True,hp=65,max_hp=65,armor=2,
        tile=tile,region_id=s.current_region_id,appearance_key='guard_'+str(index%5))
    s.actors.append(a)
    meta['people'][a.id]={**life.persona(s,a,'守卫'),'guard':True,'zone':zone['name'],'dynamic':True}
    w=life._new_item(s,a.id,source,life._rng(s,a.id),quality='uncommon');a.equipped_item_id=w.id
    c.execute('INSERT INTO wallets VALUES (?,?,?)',(s.world_id,a.id,20))
    return a


def material(s,owner,kind,source):
    i=ItemState(id='item_'+uuid4().hex,name=MATERIALS[kind],base_type='material',quality='common',material_id=kind,
        owner_id=owner,stats=ItemStats(damage=0,armor=0,cooldown_s=1),origin_event_ids=[source])
    s.items.append(i);return i


def quest_view(s,q):
    result=dict(q)
    target=next((a for a in s.actors if a.id==q.get('recipient_id') or a.id==q.get('subject_id')),None)
    issuer=next((a for a in s.actors if a.id==q.get('issuer_id')),None)
    if target:
        identity=target.name if target.id in s.known_npc_ids else '一位当地人（可向委托人打听姓名）'
        last_tile = q.get('recipient_last_known_tile') or q.get('destination')
        last_place = Tile.model_validate(last_tile) if isinstance(last_tile, dict) else target.tile
        result['clue']=identity+'，最后据说在'+place(last_place)+'。'
        if q['kind']=='delivery': result['description']='将'+q.get('item_name','货物')+'交给'+identity+'；可向委托人询问姓名和去向。'
    if q['kind']=='gather':result['clue']='采集'+MATERIALS.get(q.get('material'),q.get('material','材料'))+'，送回'+(place(issuer.tile) if issuer else '委托处')
    if q['kind']=='hunt':result['clue']='在'+q.get('place','野外')+'处理威胁，再向委托人复命。'
    # Quest coordinates remain authoritative server-only data; agent context,
    # player journals and the UI receive narrative clues, never raw tile pairs.
    for key in ('destination', 'recipient_last_known_tile', 'tile', 'source_event_ids'):
        result.pop(key,None)
    return result


def candidates(c,s,npc,entities,choices,spoken=''):
    meta=life.read(c,s.world_id)
    if not meta:return
    player=living_actor(s,s.player_id)
    if life.distance(npc.tile,player.tile)>6:return
    def add(action,params,description,target=None):
        choices.append({'action':action,'target_id':target or player.id,'params':params,'description':description})
    add('OPEN_TRADE',{},'玩家要求买卖时打开真实双向交易；可拒绝。')
    add('BARGAIN',{},'根据关系与人格议价。')
    relation=life._relation(meta,npc.id,player.id)
    if sum(q['status'] in ('open','active') for q in s.quests)<life.ACTIVE_QUEST_LIMIT:
        box=life.merchant_box(s,npc.id)
        reserved={q.get('item_id') for q in s.quests if q['status'] in ('open','active')}
        own=[i for i in s.items if i.owner_id in stock_owners(s,npc) and i.id not in equipped(s,npc) and i.material_id!='currency' and i.id not in reserved]
        recipients=[a for a in s.actors if a.kind=='npc' and a.alive and a.id!=npc.id and (life.distance(a.tile,npc.tile)<20 or bool(set(a.org_ids)&set(npc.org_ids)))]
        if own and recipients and (wallet(c,s,npc.id)>=5 or relation['hostility']>0):
            recipient=min(recipients,key=lambda a:life.distance(npc.tile,a.tile))
            if not any(e.get('id')==recipient.id for e in entities):entities.append(recipient.model_dump(mode='json'))
            for item in own[:3]:
                add('PROPOSE_DELIVERY',{'item_id':item.id},'在玩家愿意帮助或商议和解条件时，提议将'+item.name+'送给'+recipient.name+'（'+place(recipient.tile)+'）。真实交付后才支付报酬或兑现原谅。',recipient.id)
    contract=next((v for v in s.contracts if v['npc_id']==npc.id and v['status'] in ('active','pending_payment')),None)
    if contract:
        add('DISMISS',{},'玩家明确要求结束同行时解除约定。')
        if contract['status']=='pending_payment':add('PAY_HIRE',{},'玩家明确同意支付已约定酬金时付款并开始跟随。')
    elif relation['hostility']<35:
        add('HIRE',{'fee':0},'仅在玩家请求且你自愿无偿同行时接受，建立持续跟随。')
        requested=re.search(r'(\d{1,4})\s*(?:枚|个)?\s*金币',spoken)
        fees=sorted({10,20,50}|({int(requested.group(1))} if requested else set()))
        for fee in fees:add('HIRE',{'fee':fee},f'同意以{fee}金币为条件同行；生成待付款契约，不能声称已付款。')
    for q in s.quests:
        if q.get('issuer_id')==npc.id or (q.get('discovered') and any(e.get('id')==q['id'] for e in entities)):
            view=quest_view(s,q)
            if not any(e.get('id')==q['id'] for e in entities):entities.append({'kind':'quest',**view})
            add('QUEST_INFO',{},'说明这项真实任务的收件人姓名、地点线索与完成条件。',q['id'])
    for notice in s.notices:
        if notice.get('kind')=='incident' and npc.id in notice.get('knowers',[]):
            entities.append({'id':notice['id'],'kind':'known_incident','description':notice['description']})
            add('SHARE_NEWS',{},'向玩家告知自己亲历或听说的事件。',notice['id'])


def dialogue_action(c,s,npc,action,params,target,region,seq,source):
    player=living_actor(s,s.player_id);require_near(npc,player.region_id,player.tile)
    meta=life.read(c,s.world_id)
    if action=='PROPOSE_DELIVERY':
        entities=[];choices=[];candidates(c,s,npc,entities,choices)
        if not any(v['action']==action and v['params']==params and v['target_id']==target for v in choices):raise WorldError('INVALID_INTENT','这项送货约定已不可用。')
        item=next(i for i in s.items if i.id==params['item_id'])
        recipient=living_actor(s,target)
        if not life.reachable(region,npc.tile,recipient.tile):raise WorldError('ROUTE_UNAVAILABLE','收件地点无法到达。')
        reconciliation=life._relation(meta,npc.id,player.id)['hostility']>0
        reward=0 if reconciliation else 5
        if reward:c.execute('UPDATE wallets SET gold=gold-5 WHERE world_id=? AND actor_id=?',(s.world_id,npc.id))
        item.owner_id=npc.id
        q={'id':'quest_'+uuid4().hex,'kind':'delivery','title':'以行动和解' if reconciliation else '递送'+item.name,
            'issuer_id':npc.id,'recipient_id':recipient.id,'item_id':item.id,'item_name':item.name,'reward':reward,
            'reconcile':reconciliation,'status':'open','assignee_id':None,'created_tick':s.tick,'discovered':True,'source_event_ids':[source],
            'recipient_last_known_tile':recipient.tile.model_dump()}
        s.quests.append(q);meta['quest_escrow'][q['id']]=reward;life.write(c,s.world_id,meta)
        return [event(s,'quest_information',seq,npc.id,player.id,{'quest_ids':[q['id']],'text':'请把'+item.name+'送给'+recipient.name+'，他在'+place(recipient.tile)+'。'+('交付后我会原谅此前的冲突。' if reconciliation else '送到后领取5金币。')+'愿意的话请明确接下委托。'},[source],[npc.id,player.id])],[]
    if action=='HIRE':
        fee=params.get('fee')
        if type(fee) is not int or not 0<=fee<=9999:raise WorldError('INVALID_INTENT','酬金超出可执行范围。')
        if life._relation(meta,npc.id,player.id)['hostility']>=35:raise WorldError('HIRE_REFUSED','对方不信任你。')
        if any(v['npc_id']==npc.id and v['status'] in ('active','pending_payment') for v in s.contracts):raise WorldError('CONTRACT_EXISTS','已有同行约定。')
        value={'id':'contract_'+uuid4().hex,'npc_id':npc.id,'employer_id':player.id,'fee':fee,
            'status':'pending_payment' if fee else 'active','created_tick':s.tick,'source_event_ids':[source]}
        s.contracts.append(value)
        e=event(s,'contract_created',seq,npc.id,player.id,{'contract_id':value['id'],'fee':fee,'text':f'同行约定已建立，酬金 {fee} 金币。'+('付款后开始同行。' if fee else '现在开始同行。')},[source],[npc.id,player.id])
        if not fee:start_follow(c,s,npc,player,region,e.id)
        return [e],[]
    if action in ('PAY_HIRE','DISMISS'):
        value=next((v for v in s.contracts if v['npc_id']==npc.id and v['status'] in ('active','pending_payment')),None)
        if not value:raise WorldError('CONTRACT_MISSING','没有有效约定。')
        if action=='PAY_HIRE':
            if value['status']!='pending_payment':raise WorldError('ALREADY_PAID','约定已经生效，无需重复付款。')
            transfer_gold(c,s,player.id,npc.id,value['fee']);value['status']='active'
            start_follow(c,s,npc,player,region,source)
            kind='contract_activated';text='酬金已支付，对方开始跟随你。'
        else:
            value['status']='ended';stop_follow(s,npc);kind='contract_ended';text='双方结束了同行约定。'
        sync_coins(c,s)
        return [event(s,kind,seq,npc.id,player.id,{'contract_id':value['id'],'text':text},[source],[npc.id,player.id])],[]
    if action=='QUEST_INFO':
        q=next((q for q in s.quests if q['id']==target and q.get('issuer_id')==npc.id),None)
        if not q:raise WorldError('UNKNOWN_QUEST','这不是对方知道的委托。')
        q['discovered']=True
        recipient=next((a for a in s.actors if a.id==q.get('recipient_id')),None)
        if recipient and recipient.id not in s.known_npc_ids:s.known_npc_ids.append(recipient.id)
        view=quest_view(s,q)
        return [event(s,'quest_information',seq,npc.id,player.id,{'quest_ids':[q['id']],'text':view.get('description','')+' '+view.get('clue','')},[source],[npc.id,player.id])],[]
    if action=='SHARE_NEWS':
        news=next((n for n in s.notices if n['id']==target and npc.id in n.get('knowers',[])),None)
        if not news:raise WorldError('UNKNOWN_EVENT','对方没有这条消息。')
        news['discovered']=True
        for q in s.quests:
            if q.get('incident_id')==news['id']:q['discovered']=True
        return [event(s,'news_discovered',seq,npc.id,player.id,{'text':'听说：'+news['description']},[source,*news['sources']],[npc.id,player.id])],[]
    raise WorldError('ACTION_NOT_SUPPORTED','不支持的互动。')


def stop_follow(s,npc):
    for t in s.tasks:
        if t.actor_id==npc.id and t.status in ('pending','running'):
            t.status='cancelled'
    npc.task_id=None;npc.behavior='idle'


def start_follow(c,s,npc,player,region,source):
    stop_follow(s,npc)
    life._schedule(c,s,npc,player.tile.model_copy(),'FOLLOW',source,region,target_id=player.id,effect={'action':'FOLLOW'})


def action(c,s,body,region,seq):
    player=living_actor(s,s.player_id)
    if body.action=='GIVE_GOLD':
        target=living_actor(s,body.target_id);require_near(player,target.region_id,target.tile)
        if target.id==player.id:raise WorldError('INVALID_TARGET','请选择另一位人物。')
        transfer_gold(c,s,player.id,target.id,body.amount)
        return [event(s,'gold_given',seq,player.id,target.id,{'amount':body.amount,'text':'赠送了'+str(body.amount)+'金币。'},[],[player.id,target.id])]
    if body.action=='REPAIR':
        item=next((i for i in s.items if i.id==body.target_id and i.owner_id==player.id and i.base_type in life.WEAPONS),None)
        if not item:raise WorldError('ITEM_NOT_OWNED','请选择自己的武器。')
        if item.durability==100:raise WorldError('ALREADY_REPAIRED','武器完好。')
        iron=next((i for i in s.items if i.owner_id==player.id and i.base_type=='material' and i.material_id=='iron'),None)
        if not iron:raise WorldError('INSUFFICIENT_MATERIALS','维修需要一份铁矿。')
        s.items.remove(iron);item.durability=100
        return [event(s,'equipment_repaired',seq,player.id,None,{'item_name':item.name},iron.origin_event_ids,[player.id])]
    if body.action in ('PAY_HIRE','DISMISS'):
        return dialogue_action(c,s,living_actor(s,body.target_id),body.action,{},None,region,seq,source_event(c,s))[0]
    if body.action=='GATHER':
        site=next((v for v in s.sites if v.id==body.target_id),None)
        if not site:raise WorldError('SITE_NOT_FOUND','资源点不存在。')
        require_near(player,site.region_id,site.tile,2.5)
        if site.remaining<1:raise WorldError('RESOURCE_DEPLETED','资源已耗尽，稍后会再生。')
        e=gather(s,player,site,seq,source_event(c,s));return [e]
    if body.action=='BOARD':
        board=next((n for n in s.notices if n['id']==body.target_id and n['kind']=='board'),None)
        if not board:raise WorldError('BOARD_NOT_FOUND','告示牌不存在。')
        require_near(player,board['region_id'],Tile(**board['tile']),3)
        for n in s.notices:
            if n.get('posted'):n['discovered']=True
        for q in s.quests:
            if q.get('posted'):q['discovered']=True
        return [event(s,'board_read',seq,player.id,None,{'text':'你查看了告示牌上的委托与消息。'},[],[player.id])]
    if body.action=='SUBMIT':
        q=next((v for v in s.quests if v['id']==body.target_id and v['status']=='active' and v.get('assignee_id')==player.id),None)
        if not q:raise WorldError('QUEST_UNAVAILABLE','没有可提交的委托。')
        issuer=living_actor(s,q['issuer_id']);require_near(player,issuer.region_id,issuer.tile,3)
        if q['kind']=='gather':
            items=[i for i in s.items if i.owner_id==player.id and i.material_id==q['material']][:q['quantity']]
            if len(items)<q['quantity']:raise WorldError('INSUFFICIENT_MATERIALS','材料还不够。')
            for i in items:i.owner_id=issuer.id
        elif q['kind']=='hunt':
            target=next((a for a in s.actors if a.id==q['subject_id']),None)
            if not target or target.alive:raise WorldError('THREAT_REMAINS','威胁尚未解除。')
        else:raise WorldError('QUEST_CONDITION','这项委托需实际交付物品或护送抵达。')
        meta=life.read(c,s.world_id);amount=meta['quest_escrow'].pop(q['id'],0)
        c.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(amount,s.world_id,player.id))
        q['status']='completed';life.write(c,s.world_id,meta)
        return [event(s,'quest_completed',seq,player.id,issuer.id,{'quest_id':q['id'],'title':q['title'],'reward':amount},q['source_event_ids'],[player.id,issuer.id])]
    raise WorldError('ACTION_NOT_SUPPORTED','无法执行这项操作。')


def source_event(c,s):
    return c.execute('SELECT id FROM events WHERE world_id=? ORDER BY seq DESC LIMIT 1',(s.world_id,)).fetchone()[0]


def gather(s,a,site,seq,source):
    site.remaining-=1
    if site.remaining==0:site.regen_tick=s.tick+PERIODS.get(site.kind,10)
    e=event(s,'resource_gathered',seq,a.id,site.id,{'material_id':site.kind,'text':'采集了'+MATERIALS.get(site.kind,site.kind)},[source],life.near_witnesses(s,a.tile))
    i=material(s,a.id,site.kind,e.id);e.facts['item_id']=i.id
    return e


def react(c,s,events,region,meta):
    """React only to committed physical facts; knowledge travels via witnesses."""
    for e in list(events):
        if e.type=='hit_applied':
            weapon=next((i for i in s.items if i.id==e.facts.get('weapon_id')),None)
            if weapon:weapon.durability=max(0,weapon.durability-1)
            victim=next((a for a in s.actors if a.id==e.target_id),None)
            if victim:
                for item in s.items:
                    if item.id in victim.equipped_slots.values():item.durability=max(0,item.durability-1)
            if not victim or victim.kind!='npc':continue
            knowers=[a.id for a in s.actors if a.kind=='npc' and a.alive and a.id in e.witness_ids]
            if not knowers:continue
            existing=next((n for n in s.notices if n.get('suspect_id')==e.actor_id and n.get('victim_id')==e.target_id),None)
            if existing:
                existing['knowers']=list(set(existing['knowers']+knowers))
                continue
            n={'id':'incident_'+uuid4().hex,'kind':'incident','description':place(victim.tile)+'发生袭击，有人正在寻找援助。',
                'suspect_id':e.actor_id,'victim_id':victim.id,'knowers':knowers,'sources':[e.id],
                'posted':False,'discovered':s.player_id in e.witness_ids,'created_tick':s.tick,'tile':victim.tile.model_dump()}
            s.notices.append(n)
            for knower in knowers:meta['people'].setdefault(knower,{}).setdefault('news',[]).append(n['id'])
        if e.type=='actor_died':
            for v in s.contracts:
                if v['status'] in ('active','pending_payment') and e.target_id in (v['npc_id'],v['employer_id']):
                    v['status']='failed'
            # Guard replacement is a new identity, never resurrection or memory copying.
            if meta['people'].get(e.target_id,{}).get('guard'):
                for zone in s.safe_zones:
                    if e.target_id in zone.get('guard_ids',[]):zone['replace_tick']=s.tick+6
    for q in s.quests:
        if q['kind']=='delivery' and q['status']=='completed' and q.get('reconcile'):
            relation=life._relation(meta,q['issuer_id'],s.player_id)
            relation['hostility']=0;relation['trust']=max(0,relation['trust'])
            for n in s.notices:
                if n.get('suspect_id')==s.player_id and n.get('victim_id')==q['issuer_id']:n['resolved']=True
    sync_coins(c,s)


def tick(c,s,region,seq):
    meta=life.read(c,s.world_id)
    if not meta:return []
    if not meta.get('r7_initialized'):initialize(c,s,region,source_event(c,s));meta=life.read(c,s.world_id)
    record_visits(s,meta)
    events=[]
    def emit(kind,actor=None,target=None,facts=None,sources=(),witnesses=()):
        e=event(s,kind,seq+len(events),actor,target,facts or {},list(sources),list(witnesses));events.append(e);return e
    for site in s.sites:
        if site.remaining<site.capacity and s.tick>=site.regen_tick:
            site.remaining+=1;site.regen_tick=s.tick+PERIODS.get(site.kind,10)
    for zone in s.safe_zones:
        if zone.get('replace_tick',s.tick+1)<=s.tick:
            live=[a for a in s.actors if a.id in zone['guard_ids'] and a.alive]
            while len(live)<2:
                e=emit('guard_arrived',facts={'text':zone['name']+'迎来一名新守卫。'})
                a=spawn_guard(c,s,region,meta,zone,e.id,len(live));zone['guard_ids'].append(a.id);live.append(a)
                e.target_id=a.id;e.witness_ids=life.near_witnesses(s,a.tile)
            zone.pop('replace_tick',None)
    for v in s.contracts:
        if v['status'] not in ('active','pending_payment'):continue
        a=next((a for a in s.actors if a.id==v['npc_id']),None)
        p=next((a for a in s.actors if a.id==v['employer_id']),None)
        if not a or not a.alive or not p or not p.alive:v['status']='failed';continue
        if life._relation(meta,a.id,p.id)['hostility']>=45:v['status']='broken';stop_follow(s,a);continue
        if v['status']=='active' and not a.task_id:start_follow(c,s,a,p,region,v['source_event_ids'][0])
    # Guards defend their vicinity even without a model request.
    for g in [a for a in s.actors if a.alive and meta['people'].get(a.id,{}).get('guard') and not a.task_id]:
        enemy=next((a for a in s.actors if a.alive and a.kind=='monster' and life.distance(a.tile,g.tile)<8),None)
        if enemy:
            life._schedule(c,s,g,enemy.tile.model_copy(),'ATTACK',source_event(c,s),region,target_id=enemy.id,effect={'action':'DEFEND_SETTLEMENT'})
            g.behavior='attacking'
    # A report reaches guards only when a knower physically reaches a guard.
    for n in [v for v in s.notices if v['kind']=='incident' and not v.get('resolved')]:
        witnesses=[a for a in s.actors if a.id in n['knowers'] and a.alive]
        guards=[a for a in s.actors if a.alive and meta['people'].get(a.id,{}).get('guard')]
        for w in witnesses:
            nearby=[g for g in guards if life.distance(g.tile,w.tile)<6]
            if not n['posted'] and nearby:
                n['posted']=True;n['knowers']=list(set(n['knowers']+[g.id for g in nearby]))
                report=emit('crime_reported',w.id,n['suspect_id'],{'text':'守卫接到袭击报告，开始调查。'},n['sources'],life.near_witnesses(s,w.tile))
                for g in nearby:life._change_relation(meta,g.id,n['suspect_id'],-15,50,report.id)
                # A local threat can create a funded bounty, with a real target.
                threat=next((a for a in s.actors if a.id==n['suspect_id'] and a.alive and a.kind=='monster'),None)
                issuer=nearby[0]
                if threat and wallet(c,s,issuer.id)>=10 and sum(q['status'] in ('open','active') for q in s.quests)<life.ACTIVE_QUEST_LIMIT:
                    q={'id':'quest_'+uuid4().hex,'kind':'hunt','title':'清除袭击者','issuer_id':issuer.id,'subject_id':threat.id,
                        'status':'open','reward':10,'created_tick':s.tick,'discovered':False,'posted':True,'source_event_ids':[report.id],
                        'incident_id':n['id'],'place':place(threat.tile),'description':'消除已经袭击居民的威胁，向守卫复命。'}
                    s.quests.append(q);meta['quest_escrow'][q['id']]=10
                    c.execute('UPDATE wallets SET gold=gold-10 WHERE world_id=? AND actor_id=?',(s.world_id,issuer.id))
            elif not n['posted'] and not w.task_id and guards:
                g=min(guards,key=lambda a:life.distance(a.tile,w.tile))
                life._schedule(c,s,w,g.tile.model_copy(),'MOVE',n['sources'][0],region,target_id=g.id)
            if s.player_id not in n.get('knowers',[]) and life.distance(w.tile,living_actor(s,s.player_id).tile)<5:
                if not n.get('warned'):
                    n['warned']=True
                    emit('npc_speech',w.id,s.player_id,{'text':'附近出了事！请停下听我说。','mode':'policy'},n['sources'],life.near_witnesses(s,w.tile))
        if n['posted']:
            suspect=next((a for a in s.actors if a.id==n['suspect_id'] and a.alive),None)
            if suspect:
                for g in guards:
                    if not g.task_id and life.distance(g.tile,suspect.tile)<10:
                        task=life._schedule(c,s,g,suspect.tile.model_copy(),'ATTACK',n['sources'][0],region,target_id=suspect.id,effect={'action':'LAW_ENFORCEMENT'})
                        if task:g.behavior='attacking'
        if s.tick%3==0 and witnesses:
            speaker=witnesses[0]
            listener=next((a for a in s.actors if a.kind=='npc' and a.alive and a.id not in n['knowers'] and life.distance(a.tile,speaker.tile)<4),None)
            if listener:
                n['knowers'].append(listener.id)
                emit('info_shared',speaker.id,listener.id,{'statement':n['description'],'source_type':'report','root_event_ids':n['sources']},n['sources'],[speaker.id,listener.id])
    # Needs form actual material requests; no fabricated reward money.
    if s.tick%6==0 and sum(q['status'] in ('open','active') for q in s.quests)<life.ACTIVE_QUEST_LIMIT:
        issuers=[a for a in s.actors if a.kind=='npc' and a.alive and wallet(c,s,a.id)>=8]
        if issuers:
            a=issuers[(s.tick//6)%len(issuers)];kind=list(MATERIALS)[s.tick//6%4]
            e=emit('quest_created',a.id,facts={'text':place(a.tile)+'有人需要'+MATERIALS[kind]},witnesses=[a.id])
            q={'id':'quest_'+uuid4().hex,'kind':'gather','title':'收集'+MATERIALS[kind],'issuer_id':a.id,'recipient_id':a.id,
                'material':kind,'quantity':2,'status':'open','reward':8,'created_tick':s.tick,'discovered':False,
                'posted':True,'source_event_ids':[e.id],'description':'收集两份'+MATERIALS[kind]+'并交还委托人。'}
            e.facts.update(quest_id=q['id'],title=q['title']);s.quests.append(q)
            c.execute('UPDATE wallets SET gold=gold-8 WHERE world_id=? AND actor_id=?',(s.world_id,a.id));meta['quest_escrow'][q['id']]=8
    # One decision per idle NPC per cycle, bounded by population and inventory.
    rng=life._rng(s,'livelihood')
    for a in s.actors:
        if a.kind!='npc' or not a.alive or a.task_id:continue
        p=meta['people'].get(a.id,{})
        if p.get('lost'):continue
        reserved={q.get('item_id') for q in s.quests if q['status'] in ('open','active')}
        owned=[i for i in s.items if i.owner_id==a.id and i.material_id!='currency' and i.id not in reserved]
        ground=next((i for i in s.items if i.owner_id is None and i.region_id==a.region_id and i.base_type in ('material','consumable')
                     and i.material_id not in ('coins','currency') and life.distance(a.tile,i.tile)<2),None)
        if ground:
            from server.world.items import apply_item_command
            picked=apply_item_command(s,'PICKUP',{'actor_id':a.id,'item_id':ground.id},seq+len(events))
            picked[0].caused_by=ground.origin_event_ids;events.extend(picked);continue
        potion=next((i for i in owned if i.base_type=='consumable' and i.material_id in ('healing','herb')),None)
        if a.hp<a.max_hp*.65:
            if potion:
                healed=min(25,a.max_hp-a.hp);a.hp+=healed;s.items.remove(potion)
                emit('item_consumed',a.id,facts={'healed':healed,'text':'使用药品恢复伤势。'},sources=potion.origin_event_ids,witnesses=life.near_witnesses(s,a.tile));continue
            herbs=[i for i in owned if i.base_type=='material' and i.material_id=='herb'][:2]
            if len(herbs)==2:
                for herb in herbs:s.items.remove(herb)
                e=emit('item_crafted',a.id,facts={'text':'将采集的草药调制为药剂。'},sources=list(dict.fromkeys(x for herb in herbs for x in herb.origin_event_ids)),witnesses=life.near_witnesses(s,a.tile))
                potion=life._potion(s,a.id,e.id);e.facts['item_id']=potion.id;continue
            sellers=[b for b in s.actors if b.kind=='npc' and b.alive and b.id!=a.id]
            seller=next((b for b in sellers if life.distance(a.tile,b.tile)<32 and any(i.material_id=='healing' and i.owner_id in stock_owners(s,b) and i.id not in reserved for i in s.items)),None)
            if seller and wallet(c,s,a.id)>=6:
                if life.distance(a.tile,seller.tile)>2:
                    life._schedule(c,s,a,seller.tile.model_copy(),'MOVE',source_event(c,s),region,target_id=seller.id);continue
                stock=next(i for i in s.items if i.material_id=='healing' and i.owner_id in stock_owners(s,seller) and i.id not in reserved)
                transfer_gold(c,s,a.id,seller.id,6);stock.owner_id=a.id
                emit('npc_trade',a.id,seller.id,{'item_name':stock.name,'price':6},stock.origin_event_ids,life.near_witnesses(s,a.tile));continue
        weapon=next((i for i in owned if i.id==a.equipped_item_id),None)
        worn=[i for i in owned if i.id in equipped(s,a)]
        damaged=min(worn,key=lambda i:i.durability) if worn else None
        iron=next((i for i in owned if i.base_type=='material' and i.material_id=='iron'),None)
        if damaged and damaged.durability<70 and iron:
            station, station_distance = nearest_workstation(a.tile)
            if station_distance <= 3.5:
                repaired=finish_npc_production(s,a,source_event(c,s),seq+len(events),'NPC_REPAIR',[iron.id,damaged.id])
                if repaired:events.append(repaired);continue
            elif workstation_reachable(c,s,a,region,source_event(c,s),'NPC_REPAIR',[iron.id,damaged.id]):
                continue
        # A genuine social act: a generous NPC can give away an OWNED medicine
        # to another physically nearby wounded person. No healing out of thin air.
        if p.get('personality',{}).get('generosity',0) >= .67:
            medicine=next((i for i in owned if i.base_type=='consumable' and i.material_id=='healing'),None)
            neighbor=next((b for b in s.actors if b.kind=='npc' and b.alive and b.id!=a.id
                            and b.hp < b.max_hp*.4 and life.distance(a.tile,b.tile)<=2.5
                            and b.behavior!='attacking'
                            and life._relation(meta,a.id,b.id)['hostility']<35),None)
            if medicine and neighbor:
                before=neighbor.hp
                neighbor.hp=min(neighbor.max_hp,neighbor.hp+25)
                s.items.remove(medicine)
                helped=emit('npc_aided',a.id,neighbor.id,
                            {'item_name':medicine.name,'healed':neighbor.hp-before},
                            medicine.origin_event_ids,life.near_witnesses(s,a.tile))
                life._change_relation(meta,neighbor.id,a.id,6,-2,helped.id)
                continue
        if p.get('guard'):
            if s.tick%4==0:
                home=p['home_tile'];tile=life.free_tile(region,home['x']+rng.randint(-4,4),home['y']+rng.randint(-4,4))
                life._schedule(c,s,a,tile,'MOVE',source_event(c,s),region)
            continue
        mats={k:[i for i in owned if i.base_type=='material' and i.material_id==k] for k in MATERIALS}
        if len(mats['wood'])>=1 and len(mats['iron'])>=2:
            chosen=[mats['wood'][0],*mats['iron'][:2]]
            station, station_distance = nearest_workstation(a.tile)
            if station_distance <= 3.5:
                crafted=finish_npc_production(s,a,source_event(c,s),seq+len(events),'NPC_CRAFT',[i.id for i in chosen])
                if crafted:events.append(crafted);continue
            elif workstation_reachable(c,s,a,region,source_event(c,s),'NPC_CRAFT',[i.id for i in chosen]):
                continue
        if s.tick%3!=0:continue
        surplus=[i for i in tradable(s,a) if i.base_type=='material']
        buyers=[b for b in s.actors if b.kind=='npc' and b.alive and b.id!=a.id and life.distance(a.tile,b.tile)<3 and wallet(c,s,b.id)>=3
                and life._relation(meta,a.id,b.id)['hostility']<35]
        if len(surplus)>3 and buyers:
            b=buyers[0];i=surplus[0];transfer_gold(c,s,b.id,a.id,3);i.owner_id=b.id
            emit('npc_trade',a.id,b.id,{'item_name':i.name,'price':3},i.origin_event_ids,life.near_witnesses(s,a.tile));continue
        if len(owned)>14:continue
        # Curious characters may explore without inventing destinations or
        # teleporting. Actual locomotion and arrival are confirmed by A/C.
        # Guards, the lost and hired followers do not abandon their duties.
        adventurous=any(label in str(p.get('role','')) for label in
                        ('旅人','猎人','游荡','探险','佣兵','学徒'))
        if s.tick>0 and s.tick%9==0 and adventurous and p.get('personality',{}).get('courage',0)>.68:
            roll=life._rng(s,'expedition:'+a.id)
            destination=life.free_tile(region,a.tile.x+roll.randint(-15,15),
                                       a.tile.y+roll.randint(-15,15))
            if life.distance(a.tile,destination)>=6 and life.reachable(region,a.tile,destination):
                source=source_event(c,s)
                task=life._schedule(c,s,a,destination,'MOVE',source,region,
                                    effect={'action':'NPC_EXPLORE','start_tile':a.tile.model_dump()})
                if task:
                    emit('npc_expedition_started',a.id,None,
                         {'task_id':task.id,'text':'An NPC set out to explore a reachable stretch of wilderness.'},
                         [source],life.near_witnesses(s,a.tile))
                    continue
        sites=[site for site in s.sites if site.remaining and life.distance(a.tile,site.tile)<32
               and (p.get('personality',{}).get('courage',.5)>.55 or not any(m.alive and m.kind=='monster' and life.distance(m.tile,site.tile)<7 for m in s.actors))]
        if sites:
            site=min(sites,key=lambda site:life.distance(a.tile,site.tile)+(8 if len(mats.get(site.kind,[]))>2 else 0))
            if life.distance(a.tile,site.tile)<2:events.append(gather(s,a,site,seq+len(events),source_event(c,s)))
            else:life._schedule(c,s,a,site.tile.model_copy(),'MOVE',source_event(c,s),region,effect={'action':'NPC_GATHER','site_id':site.id})
    life.write(c,s.world_id,meta);sync_coins(c,s)
    return events


def arrival(c,s,effect,actor,finished,seq):
    work_kind=effect.get('action','')
    if work_kind in ('NPC_REPAIR','NPC_CRAFT'):
        # The task report must originate from the real reachable station.
        intended=effect.get('workstation_id')
        station,distance=nearest_workstation(actor.tile)
        if not station or station['id']!=intended or distance>3.5:return []
        result=finish_npc_production(s,actor,finished.id,seq,work_kind,effect.get('item_ids',[]))
        return [result] if result else []
    if work_kind=='NPC_EXPLORE':
        before=effect.get('start_tile',{})
        if not isinstance(before,dict) or life.distance(actor.tile,Tile.model_validate(before))<4:return []
        return [event(s,'npc_explored',seq,actor.id,None,
                      {'text':'The NPC explored a real route and reached the destination.'},
                      [finished.id],life.near_witnesses(s,actor.tile))]
    if work_kind!='NPC_GATHER':return []
    site=next((v for v in s.sites if v.id==effect['site_id'] and v.remaining>0),None)
    if not site:return []
    return [gather(s,actor,site,seq,finished.id)]


def director_request(c,s,proposal,region,seq):
    """World-model proposals share the same funded task/settlement primitives."""
    meta=life.read(c,s.world_id)
    if not meta or sum(q['status'] in ('open','active') for q in s.quests)>=life.ACTIVE_QUEST_LIMIT:
        raise WorldError('QUEST_LIMIT','当前无法再发布委托。')
    issuer=living_actor(s,proposal.target_id)
    if issuer.kind!='npc':raise WorldError('INVALID_ISSUER','委托人必须是现存居民。')
    q={'id':'quest_'+uuid4().hex,'kind':proposal.quest_kind,'issuer_id':issuer.id,'status':'open',
        'created_tick':s.tick,'discovered':False,'posted':True,'source_event_ids':list(proposal.source_event_ids)}
    if proposal.quest_kind=='gather':
        if proposal.resource not in MATERIALS or not any(site.kind==proposal.resource for site in s.sites):
            raise WorldError('RESOURCE_NOT_SUPPORTED','当前世界不存在这种采集资源。')
        q.update(title='收集'+MATERIALS[proposal.resource],recipient_id=issuer.id,material=proposal.resource,
            quantity=proposal.quantity,reward=proposal.quantity*3,description='收集'+str(proposal.quantity)+'份'+MATERIALS[proposal.resource]+'交还委托人。')
    else:
        involved=set()
        for source in proposal.source_event_ids:
            row=c.execute('SELECT body FROM events WHERE world_id=? AND id=?',(s.world_id,source)).fetchone()
            if row:
                e=json.loads(row[0]);involved.update((e.get('actor_id'),e.get('target_id')))
        threat=next((a for a in s.actors if a.id in involved and a.alive and a.kind=='monster'),None)
        if not threat:raise WorldError('UNKNOWN_THREAT','证据中没有可讨伐的真实威胁。')
        q.update(title='讨伐野外威胁',subject_id=threat.id,reward=10,place=place(threat.tile),description='解决已知威胁后向委托人复命。')
    if wallet(c,s,issuer.id)<q['reward']:raise WorldError('INSUFFICIENT_FUNDS','委托人无法支付报酬。')
    c.execute('UPDATE wallets SET gold=gold-? WHERE world_id=? AND actor_id=?',(q['reward'],s.world_id,issuer.id))
    meta['quest_escrow'][q['id']]=q['reward'];s.quests.append(q);life.write(c,s.world_id,meta)
    created=event(s,'quest_created',seq,issuer.id,q.get('subject_id') or issuer.id,
        {'quest_id':q['id'],'title':q['title'],'kind':q['kind'],'mode':'live','reason_summary':proposal.reason_summary},q['source_event_ids'],[issuer.id])
    q['source_event_ids']=[created.id];return created
