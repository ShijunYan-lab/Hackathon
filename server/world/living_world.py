"""Bounded living-world rules shared by dialogue, simulation and the playable client.

This module is C's authority, not an LLM. Model intents are proposals; stock,
quotes, rewards, migration and outcomes are validated and transacted here.
Only enabled for the integrated overworld. Source events accompany every effect.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from uuid import uuid4

from shared.protocol import ActorState, ItemState, ItemStats, StateView, Task, Tile
from server.world.commands import WorldError
from server.world.items import living_actor, require_near
from server.world.tasks import event, reachable
from server.generation.equipment import generate_weapon

SCHEMA = """
CREATE TABLE IF NOT EXISTS world_life (
    world_id TEXT PRIMARY KEY, body TEXT NOT NULL
);
"""
NPC_LIMIT = 28
MONSTER_LIMIT = 16
ACTIVE_QUEST_LIMIT = 5
WEAPONS = ('sword', 'axe', 'hammer', 'bow', 'crossbow', 'staff')
WEAPON_NAMES = {'sword':'\u957f\u5251','axe':'\u6218\u65a7','hammer':'\u6218\u9524',
               'bow':'\u730e\u5f13','crossbow':'\u8f7b\u5f29','staff':'\u6cd5\u6756'}
FORESTS = [(89,94),(111,89),(214,61),(190,78),(267,107)]
WAYPOINTS = [(69,166),(243,166),(89,94),(235,50),(142,143)]


def _rng(state, label):
    digest = hashlib.sha256(f'{state.seed}:{state.tick}:{label}'.encode()).digest()
    return random.Random(int.from_bytes(digest[:8], 'big'))


def read(connection, world_id):
    row = connection.execute('SELECT body FROM world_life WHERE world_id=?', (world_id,)).fetchone()
    return json.loads(row[0]) if row else None


def write(connection, world_id, data):
    connection.execute('INSERT OR REPLACE INTO world_life VALUES (?,?)',
                       (world_id, json.dumps(data, ensure_ascii=False)))


def distance(a, b):
    return math.hypot(a.x-b.x, a.y-b.y)


def free_tile(region, x, y, occupied=(), max_radius=24):
    """Place on an actual walkable cell; never spawn inside walls or on actors."""
    blocked = {tuple(c) for c in region['blocked_tiles']}
    occupied = {(int(t.x), int(t.y)) for t in occupied}
    for radius in range(max_radius+1):
        for dy in range(-radius, radius+1):
            for dx in range(-radius, radius+1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                cell = (int(x)+dx, int(y)+dy)
                if (0 <= cell[0] < region['width_tiles'] and 0 <= cell[1] < region['height_tiles']
                        and cell not in blocked and cell not in occupied):
                    return Tile(x=cell[0]+.5, y=cell[1]+.5)
    raise WorldError('NO_FREE_TILE', '\u9644\u8fd1\u6ca1\u6709\u53ef\u7528\u7684\u843d\u811a\u70b9\u3002')


def near_witnesses(state, tile, radius=7):
    return [a.id for a in state.actors if a.alive and distance(a.tile,tile)<=radius]


def _new_item(state, owner_id, source, rng, quality=None, kind=None):
    item = generate_weapon(rng, 'item_'+uuid4().hex, owner_id, source)
    kind = kind or rng.choice(WEAPONS)
    rarity = quality or rng.choices(['common','uncommon','rare'], [65,28,7])[0]
    bonus = {'common':0,'uncommon':2,'rare':4}[rarity]
    item.base_type = kind
    item.quality = rarity
    item.name = {'common':'\u65c5\u9014','uncommon':'\u7cbe\u5236','rare':'\u9057\u7269'}[rarity] + WEAPON_NAMES[kind]
    item.stats = ItemStats(damage=rng.randint(5,8)+bonus, cooldown_s={'hammer':.85,'axe':.7,'crossbow':1.05}.get(kind,.6),armor=0)
    item.affixes = [] if rarity=='common' else ['sharp']
    state.items.append(item)
    return item


def _armor(state, owner, source, rarity='common'):
    item = ItemState(id='item_'+uuid4().hex, name={'common':'\u65c5\u4eba\u5e03\u8863','uncommon':'\u52a0\u56fa\u76ae\u7532','rare':'\u9057\u8ff9\u80f8\u7532'}[rarity],
        base_type='armor', quality=rarity, material_id='cloth' if rarity=='common' else 'leather', equipment_slot='chest',
        owner_id=owner, stats=ItemStats(damage=0,cooldown_s=1,armor={'common':1,'uncommon':2,'rare':3}[rarity]),origin_event_ids=[source])
    state.items.append(item)
    return item


def _potion(state, owner, source):
    item = ItemState(id='item_'+uuid4().hex,name='\u6cbb\u7597\u836f\u5242',base_type='consumable',quality='common',material_id='healing',
        owner_id=owner,stats=ItemStats(damage=0,cooldown_s=1,armor=0),origin_event_ids=[source])
    state.items.append(item)
    return item


def persona(state, actor, role='\u65c5\u4eba'):
    rng = _rng(state, 'personality:'+actor.id)
    return {'role':role,'personality':{'courage':round(rng.uniform(.15,.9),2),'generosity':round(rng.uniform(.15,.85),2),
        'patience':round(rng.uniform(.2,.9),2)},'relations':{},'discount':0,'discount_sources':[],
        'home_tile':actor.tile.model_dump(),'dynamic':False}


def initialize(connection, state, region, source):
    if read(connection,state.world_id) is not None:
        return
    rng = _rng(state,'initial_life')
    meta = {'version':1,'next_population_tick':4,'next_story_tick':3,'serial':0,'people':{},'coin_pouches':{},'quest_escrow':{}}
    player = living_actor(state,state.player_id)
    # New worlds only; do not destroy gear in an already-existing save.
    owned = [i for i in state.items if i.owner_id==player.id]
    sword = next(i for i in owned if i.id==player.equipped_item_id)
    sword.name='\u65e7\u94c1\u5251';sword.stats=ItemStats(damage=4,cooldown_s=.65,armor=0);sword.quality='common';sword.affixes=[]
    state.items=[i for i in state.items if i.owner_id!=player.id or i.id==sword.id]
    cloth=_armor(state,player.id,source)
    player.equipped_slots={'chest':cloth.id};player.armor=1
    connection.execute('UPDATE wallets SET gold=12 WHERE world_id=? AND actor_id=?',(state.world_id,player.id))
    for actor in state.actors[1:]:
        t=next((t for t in region.get('npc_spawns',[]) if t['appearance_key']==actor.appearance_key),{})
        p=persona(state,actor,t.get('role','\u65c5\u4eba'));meta['people'][actor.id]=p
        if any(term in p['role'] for term in ['\u5546','\u94c1\u5320','\u8001\u677f','\u836f']):
            box_id='box_'+uuid4().hex
            tile=free_tile(region,actor.tile.x+1,actor.tile.y+1,[a.tile for a in state.actors])
            state.containers.append({'id':box_id,'label':'\u8d27\u7bb1','kind':'merchant','merchant_id':actor.id,'region_id':region['id'],'tile':tile.model_dump(),'opened':False,'gold':0})
            for index in range(6):
                _new_item(state,box_id,source,rng,kind=WEAPONS[index%len(WEAPONS)])
            _armor(state,box_id,source,rng.choice(['uncommon','rare']))
            _potion(state,box_id,source)
    for xy in [*WAYPOINTS,*FORESTS]:
        tile=free_tile(region,xy[0]+rng.randint(-5,5),xy[1]+rng.randint(-5,5),[a.tile for a in state.actors]+[Tile(**c['tile']) for c in state.containers])
        container={'id':'box_'+uuid4().hex,'label':'\u65e7\u6728\u7bb1','kind':'cache','merchant_id':None,'region_id':region['id'],'tile':tile.model_dump(),'opened':False,'gold':rng.randint(4,17)}
        state.containers.append(container)
        _new_item(state,container['id'],source,rng)
        _potion(state,container['id'],source)
    # Visible nearby wanderers plus wildlife away from the safe starting village.
    for n in range(4):
        _spawn(connection,state,region,meta,source,monster=False,index=n)
    for n in range(10):
        _spawn(connection,state,region,meta,source,monster=True,index=n)
    write(connection,state.world_id,meta)


def _spawn(connection,state,region,meta,source,monster=False,index=0):
    meta['serial']+=1
    rng=_rng(state,'spawn:'+str(meta['serial']))
    center=FORESTS[index%len(FORESTS)] if monster else WAYPOINTS[index%len(WAYPOINTS)]
    tile=free_tile(region,center[0]+rng.randint(-8,8),center[1]+rng.randint(-8,8),[a.tile for a in state.actors if a.alive])
    if monster:
        appearance='wisp' if rng.random()<.3 else 'wolf'
        name='\u68ee\u6797\u7cbe\u602a' if appearance=='wisp' else '\u91ce\u72fc'
        actor=ActorState(id='monster_'+uuid4().hex,kind='monster',name=name,alive=True,hp=22,max_hp=22,armor=0,
            region_id=region['id'],tile=tile,appearance_key=appearance)
    else:
        role=rng.choice(['\u6e38\u8361\u4f63\u5175','\u65c5\u884c\u91c7\u836f\u4eba','\u5546\u961f\u4f19\u8ba1','\u8fdc\u65b9\u5b66\u5f92'])
        actor=ActorState(id='npc_'+uuid4().hex,kind='npc',name=rng.choice(['\u827e\u5c14','\u585e\u62c9','\u7c73\u62c9','\u6d1b\u6069','\u5a1c\u7c73'])+str(meta['serial']),alive=True,hp=38,max_hp=38,armor=0,
            region_id=region['id'],tile=tile,appearance_key=rng.choice(['glen','kyra','leah','renard','scott']))
        meta['people'][actor.id]={**persona(state,actor,role),'dynamic':True}
    state.actors.append(actor)
    weapon=_new_item(state,actor.id,source,rng,quality='common',kind=('staff' if actor.appearance_key=='wisp' else 'sword'))
    if monster:
        weapon.name='\u5929\u751f\u653b\u51fb';weapon.stats=ItemStats(damage=3,cooldown_s=1.25,armor=0)
    actor.equipped_item_id=weapon.id
    connection.execute('INSERT OR IGNORE INTO wallets VALUES (?,?,?)',(state.world_id,actor.id,rng.randint(2,8) if monster else rng.randint(12,26)))
    return actor


def identity(connection,state,actor_id):
    meta=read(connection,state.world_id)
    return meta['people'].get(actor_id,{}) if meta else {}


def _relation(meta,npc_id,other_id):
    return meta['people'].setdefault(npc_id,{}).setdefault('relations',{}).setdefault(other_id,{'trust':0,'hostility':0,'sources':[]})


def _change_relation(meta,npc_id,other_id,trust,hostility,source):
    relation=_relation(meta,npc_id,other_id)
    if source in relation['sources']:
        return
    relation['trust']=max(-100,min(100,relation['trust']+trust))
    relation['hostility']=max(0,min(100,relation['hostility']+hostility))
    relation['sources']=(relation['sources']+[source])[-32:]


def merchant_box(state,merchant_id):
    return next((c for c in state.containers if c.get('merchant_id')==merchant_id and c['kind']=='merchant'),None)


def _assert_trade(connection,state,merchant_id):
    player=living_actor(state,state.player_id);merchant=living_actor(state,merchant_id)
    require_near(player,merchant.region_id,merchant.tile,3)
    meta=read(connection,state.world_id)
    if not meta or not merchant_box(state,merchant_id):
        raise WorldError('NOT_A_MERCHANT','\u8fd9\u4f4d\u4eba\u7269\u6ca1\u6709\u5728\u552e\u7684\u5546\u54c1\u3002')
    box=merchant_box(state,merchant_id)
    require_near(player,box['region_id'],Tile(**box['tile']),4)
    relation=_relation(meta,merchant_id,player.id)
    if merchant.behavior=='attacking' or relation['hostility']>=45 or relation['trust']<=-50:
        raise WorldError('TRADE_REFUSED','\u5bf9\u65b9\u56e0\u4e3a\u6b64\u524d\u7684\u51b2\u7a81\u62d2\u7edd\u4ea4\u6613\u3002')
    return player,merchant,meta


def _price(item):
    if item.base_type=='consumable':return 6
    if item.base_type=='material':return 3
    if item.base_type=='armor':return 8+item.stats.armor*6
    return max(5,round(item.stats.damage*2+{'common':0,'uncommon':6,'rare':15}[item.quality]))


def shop_view(connection,state,merchant_id):
    player,merchant,meta=_assert_trade(connection,state,merchant_id)
    box=merchant_box(state,merchant_id)
    discount=int(meta['people'][merchant_id].get('discount',0))
    stock=[{'item':i.model_dump(mode='json'),'price':max(1,math.ceil(_price(i)*(100-discount)/100)),'base_price':_price(i)}
           for i in state.items if i.owner_id==box['id']]
    stamp=json.dumps([state.world_id,merchant_id,stock,discount,state.tick//5],sort_keys=True)
    quote=hashlib.sha256(stamp.encode()).hexdigest()[:24]
    wallet=connection.execute('SELECT gold FROM wallets WHERE world_id=? AND actor_id=?',(state.world_id,player.id)).fetchone()
    return {'merchant_id':merchant_id,'container_id':box['id'],'stock':stock,'discount_percent':discount,
            'quote_id':quote,'gold':wallet[0] if wallet else 0,'expires_tick':(state.tick//5+1)*5}


def bargain(connection,state,merchant_id,source,seq):
    player,merchant,meta=_assert_trade(connection,state,merchant_id)
    p=meta['people'][merchant_id];relation=_relation(meta,merchant_id,player.id)
    # Do not stack discounts for repeated wording. No client/LLM numeric price accepted.
    generosity=p['personality']['generosity']
    max_discount=max(0,min(25,int(generosity*10)+max(0,relation['trust'])//5-int(relation['hostility']/3)))
    old=int(p.get('discount',0));new=max(old,max_discount)
    p['discount']=new;p['discount_sources']=[source,*relation['sources']][-16:]
    write(connection,state.world_id,meta)
    explanation=('\u6839\u636e\u8fc7\u53bb\u5f80\u6765\u548c\u5f53\u524d\u5e93\u5b58\uff0c\u8fd9\u6b21\u53ef\u4ee5\u51cf\u514d %d%%\u3002'%new) if new else '\u8fd9\u6b21\u4e0d\u80fd\u518d\u4fbf\u5b9c\u4e86\u3002'
    return event(state,'price_negotiated',seq,merchant.id,player.id,{'discount_percent':new,'previous_discount':old,'explanation':explanation},[source,*relation['sources']][-16:],[merchant.id,player.id])


def social_update(connection,state,npc_id,signal,source,seq):
    meta=read(connection,state.world_id)
    if not meta or signal=='neutral':return []
    p=meta['people'].get(npc_id)
    if not p:return []
    deltas={'insult':(-8,10),'threat':(-15,25),'apology':(3,-4),'thanks':(1,-1)}
    # Apologies have a per-world-turn cap; a sentence cannot erase an assault.
    if signal in ('apology','thanks') and p.get('last_social_repair_tick')==state.tick:return []
    if signal in ('apology','thanks'):p['last_social_repair_tick']=state.tick
    trust,hostility=deltas.get(signal,(0,0))
    _change_relation(meta,npc_id,state.player_id,trust,hostility,source)
    if signal in ('insult','threat'):p['discount']=0
    write(connection,state.world_id,meta)
    return [event(state,'relationship_changed',seq,npc_id,state.player_id,{'signal':signal},[source],[npc_id,state.player_id])]


def apply_dialogue_action(connection,state,context,intent,region,seq,source):
    actor=living_actor(state,context.npc_id)
    player=living_actor(state,state.player_id)
    require_near(actor,player.region_id,player.tile)
    if intent.action in ('OPEN_TRADE','BARGAIN'):
        _assert_trade(connection,state,actor.id)
        effects=[]
        if intent.action=='BARGAIN':effects.append(bargain(connection,state,actor.id,source,seq))
        effects.append(event(state,'trade_opened',seq+len(effects),actor.id,player.id,{'merchant_id':actor.id},[source],[actor.id,player.id]))
        return effects,[]
    if intent.action=='ASK_WORK':
        known=[]
        for q in state.quests:
            if q.get('issuer_id')==actor.id or q.get('subject_id')==actor.id:
                q['discovered']=True;known.append(q['id'])
        return [event(state,'quest_information',seq,actor.id,player.id,{'quest_ids':known},[source],[actor.id,player.id])],[]
    if intent.action=='GUIDE_HOME':
        q=next((q for q in state.quests if q.get('subject_id')==actor.id and q['status']=='active' and q.get('assignee_id')==player.id),None)
        if not q:raise WorldError('QUEST_UNAVAILABLE','No active rescue to guide.')
        home=living_actor(state,q['issuer_id'])
        task=_schedule(connection,state,actor,home.tile.model_copy(),'MOVE',source,region,target_id=home.id,effect={'action':'RESCUE','quest_id':q['id']})
        if task is None:raise WorldError('PRECONDITION_FAILED','This route is unavailable or this NPC is already occupied.')
        q['task_id']=task.id
        return [event(state,'task_scheduled',seq,actor.id,home.id,{'task_id':task.id,'action':'RESCUE'},[source],[actor.id,player.id])],[task.id]
    if intent.action=='ACCEPT_QUEST':
        return accept_quest(connection,state,intent.target_id,seq,source,issuer=actor.id),[]
    raise WorldError('ACTION_NOT_SUPPORTED','Unsupported interaction')


def accept_quest(connection,state,quest_id,seq,source=None,issuer=None):
    q=next((q for q in state.quests if q['id']==quest_id),None)
    player=living_actor(state,state.player_id)
    if not q or q['status']!='open':
        raise WorldError('QUEST_UNAVAILABLE','\u8fd9\u4ef6\u4e8b\u5df2\u7ecf\u88ab\u522b\u4eba\u63a5\u624b\u6216\u7ed3\u675f\u3002')
    owner=living_actor(state,q['issuer_id'])
    if issuer and issuer!=owner.id:raise WorldError('NOT_AUTHORIZED','Not this issuer')
    require_near(player,owner.region_id,owner.tile,3)
    q['status']='active';q['assignee_id']=player.id;q['discovered']=True
    if q['kind']=='delivery':
        item=next((i for i in state.items if i.id==q['item_id']),None)
        if item is None or item.owner_id!=owner.id:raise WorldError('QUEST_UNAVAILABLE','\u8d27\u7269\u5df2\u4e0d\u5728\u59d4\u6258\u4eba\u624b\u4e2d\u3002')
        item.owner_id=player.id
    issued=event(state,'quest_accepted',seq,player.id,owner.id,{'quest_id':q['id'],'title':q['title']},[source] if source else q['source_event_ids'],[player.id,owner.id])
    q['source_event_ids'].append(issued.id)
    return [issued]


def on_events(connection,state,events,region):
    meta=read(connection,state.world_id)
    if not meta:return
    initial=list(events)
    for e in initial:
        if e.type=='hit_applied' and e.target_id in meta['people']:
            _change_relation(meta,e.target_id,e.actor_id,-25,55,e.id)
            meta['people'][e.target_id]['discount']=0
            _defend(connection,state,meta,e,events,region)
        elif e.type=='item_given' and e.target_id in meta['people']:
            _change_relation(meta,e.target_id,e.actor_id,4,-1,e.id)
        if e.type=='actor_died':
            target=next((a for a in state.actors if a.id==e.target_id),None)
            if target:
                row=connection.execute('SELECT gold FROM wallets WHERE world_id=? AND actor_id=?',(state.world_id,target.id)).fetchone()
                if row and row[0]>0:
                    purse='item_'+uuid4().hex;gold=int(row[0])
                    dropped=event(state,'gold_dropped',events[-1].event_seq+1,target.id,None,{'item_id':purse,'amount':gold},[e.id],e.witness_ids)
                    state.items.append(ItemState(id=purse,name='\u94b1\u888b',base_type='consumable',quality='common',material_id='coins',
                        stats=ItemStats(damage=0,cooldown_s=1,armor=0),region_id=target.region_id,tile=target.tile.model_copy(),origin_event_ids=[dropped.id]))
                    meta['coin_pouches'][purse]=gold
                    connection.execute('UPDATE wallets SET gold=0 WHERE world_id=? AND actor_id=?',(state.world_id,target.id))
                    events.append(dropped)
                # The deceased merchant's existing stock survives, but no fake clone is created.
                for box in state.containers:
                    if box.get('merchant_id')==target.id:
                        box['kind']='cache';box['estate_id']=target.id;box['merchant_id']=None;box['label']='\u9057\u7559\u7684\u8d27\u7bb1'
        if e.type=='item_picked_up' and e.facts.get('item_id') in meta['coin_pouches']:
            purse=e.facts['item_id'];gold=meta['coin_pouches'].pop(purse)
            connection.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(gold,state.world_id,e.actor_id))
            state.items=[i for i in state.items if i.id!=purse]
            events.append(event(state,'gold_collected',events[-1].event_seq+1,e.actor_id,None,{'amount':gold},[e.id],[e.actor_id]))
    _settle_quests(connection,state,meta,events)
    write(connection,state.world_id,meta)


def _settle_quests(connection,state,meta,events):
    for q in state.quests:
        if q['status'] not in ('open','active'):continue
        participants=[q.get('issuer_id'),q.get('assignee_id'),q.get('recipient_id'),q.get('subject_id')]
        dead=[a for a in state.actors if a.id in participants and not a.alive]
        cancelled=next((e for e in events if e.type in ('task_failed','task_cancelled') and e.facts.get('task_id')==q.get('task_id') and q.get('task_id')),None)
        expired=state.tick-int(q.get('created_tick',state.tick))>80
        if dead or cancelled or expired:
            q['status']='failed'
            q['failure_reason']=('participant_dead' if dead else 'action_interrupted' if cancelled else 'expired')
            failed=event(state,'quest_failed',events[-1].event_seq+1,None,q['issuer_id'],{'quest_id':q['id'],'title':q['title'],'reason':q['failure_reason']},q['source_event_ids'],[state.player_id] if q.get('discovered') else [])
            events.append(failed)
            escrow=meta['quest_escrow'].pop(q['id'],0)
            issuer=next((a for a in state.actors if a.id==q['issuer_id']),None)
            if issuer and issuer.alive:
                connection.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(escrow,state.world_id,issuer.id))
            elif issuer and escrow:
                # A reserved wage belongs to the estate, not to a dead wallet.
                box=next((c for c in state.containers if c.get('estate_id')==issuer.id),None)
                if box:box['gold']=box.get('gold',0)+escrow
            if q.get('subject_id') in meta['people']:meta['people'][q['subject_id']]['lost']=False
            continue
        completion=None
        if q['kind']=='delivery':
            completion=next((e for e in events if e.type=='item_given' and e.facts.get('item_id')==q.get('item_id') and e.target_id==q.get('recipient_id')),None)
        elif q['kind']=='rescue':
            completion=next((e for e in events if e.type=='task_succeeded' and e.actor_id==q.get('subject_id') and e.facts.get('task_id')==q.get('task_id')),None)
        if not completion:continue
        q['status']='completed'
        if q.get('subject_id') in meta['people']:meta['people'][q['subject_id']]['lost']=False
        amount=meta['quest_escrow'].pop(q['id'],0)
        recipient=q.get('assignee_id') or q['issuer_id']
        connection.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(amount,state.world_id,recipient))
        events.append(event(state,'quest_completed',events[-1].event_seq+1,recipient,q['issuer_id'],{'quest_id':q['id'],'title':q['title'],'reward':amount},[completion.id,*q['source_event_ids']][-16:],[recipient,q['issuer_id']] if q.get('discovered') else [recipient]))


def _schedule(connection,state,actor,tile,kind,source,region,target_id=None,effect=None):
    if actor.task_id or not reachable(region,actor.tile,tile):return None
    task=Task(id='task_'+uuid4().hex,actor_id=actor.id,kind=kind,target_id=target_id,target_region_id=actor.region_id,
        target_tile=tile,status='pending',started_tick=state.tick,source_event_ids=[source])
    state.tasks.append(task);actor.task_id=task.id;actor.behavior='moving'
    connection.execute('INSERT INTO task_effects VALUES (?,?,?)',(state.world_id,task.id,json.dumps(effect or {'action':'WANDER'},ensure_ascii=False)))
    return task


def tick(connection,state,region,seq,source_ids=()):
    meta=read(connection,state.world_id)
    if not meta:return []
    events=[]
    def emit(kind,actor,target,facts,sources=(),witnesses=()):
        e=event(state,kind,seq+len(events),actor,target,facts,list(sources),list(witnesses));events.append(e);return e
    # Expire stuck tasks instead of blocking the whole world forever.
    for task in state.tasks:
        if task.status in ('pending','running') and state.tick-task.started_tick>35:
            task.status='failed'
            actor=next((a for a in state.actors if a.id==task.actor_id),None)
            if actor and actor.task_id==task.id:actor.task_id=None;actor.behavior='idle'
            emit('task_failed',task.actor_id,task.target_id,{'task_id':task.id,'reason':'timeout'},task.source_event_ids,[task.actor_id])
    rng=_rng(state,'life_tick')
    if state.tick>=meta['next_population_tick']:
        meta['next_population_tick']=state.tick+rng.randint(4,7)
        counts={kind:sum(a.alive and a.kind==kind for a in state.actors) for kind in ('npc','monster')}
        for monster in (False,True):
            if counts['monster' if monster else 'npc'] >= (MONSTER_LIMIT if monster else NPC_LIMIT):continue
            created=emit('wildlife_arrived' if monster else 'traveler_arrived',None,None,{'source':'wilderness' if monster else 'external_migration','mode':'rules'},source_ids)
            actor=_spawn(connection,state,region,meta,created.id,monster,index=rng.randrange(5))
            created.target_id=actor.id;created.facts.update(tile=actor.tile.model_dump(),region_id=actor.region_id)
            created.witness_ids=near_witnesses(state,actor.tile)
    if state.tick>=meta['next_story_tick']:
        meta['next_story_tick']=state.tick+rng.randint(4,7)
        if sum(q['status'] in ('open','active') for q in state.quests)<ACTIVE_QUEST_LIMIT:
            _create_errand(connection,state,region,meta,emit,rng)
    # One bounded job per tick, not one model call per frame or one per person.
    idle=[a for a in state.actors if a.kind=='npc' and a.alive and not a.task_id and meta['people'].get(a.id,{}).get('dynamic')]
    if idle:
        actor=rng.choice(idle)
        if not meta['people'][actor.id].get('lost') and not any(q.get('assignee_id')==actor.id and q['status']=='active' for q in state.quests):
            p=meta['people'][actor.id];home=p['home_tile']
            tile=free_tile(region,home['x']+rng.randint(-5,5),home['y']+rng.randint(-5,5))
            if distance(actor.tile,tile)>1:
                e=emit('travel_planned',actor.id,None,{'mode':'rules','purpose':'daily_travel'},source_ids,[actor.id])
                task=_schedule(connection,state,actor,tile,'MOVE',e.id,region)
                if task:e.facts['task_id']=task.id
    # Courier arrival is an actual task report, not a timer claiming success.
    if events:
        _settle_quests(connection,state,meta,events)
    write(connection,state.world_id,meta)
    return events


def _create_errand(connection,state,region,meta,emit,rng,preferred_issuer=None,kind=None,mode='rules',sources=()):
    issuers=[a for a in state.actors if a.kind=='npc' and a.alive and merchant_box(state,a.id)]
    if preferred_issuer:issuers=[a for a in issuers if a.id==preferred_issuer]
    if not issuers:return
    issuer=rng.choice(issuers)
    wallet=connection.execute('SELECT gold FROM wallets WHERE world_id=? AND actor_id=?',(state.world_id,issuer.id)).fetchone()
    if not wallet or wallet[0]<5:return
    recipients=[a for a in state.actors if a.kind=='npc' and a.alive and a.id!=issuer.id and distance(a.tile,issuer.tile)>4]
    if not recipients:return
    target=rng.choice(recipients)
    qid='quest_'+uuid4().hex
    kind=kind or rng.choice(['delivery','delivery','rescue'])
    if kind=='rescue':
        wanderers=[a for a in recipients if meta['people'].get(a.id,{}).get('dynamic') and not a.task_id]
        if not wanderers:return
        target=rng.choice(wanderers)
    stock=[i for i in state.items if i.owner_id==merchant_box(state,issuer.id)['id']]
    if kind=='delivery' and not stock:return
    if not reachable(region,issuer.tile,target.tile):return
    created=emit('quest_created',issuer.id,target.id,{'quest_id':qid,'kind':kind,'mode':mode},sources,[issuer.id,target.id])
    reward=5
    connection.execute('UPDATE wallets SET gold=gold-? WHERE world_id=? AND actor_id=?',(reward,state.world_id,issuer.id))
    meta['quest_escrow'][qid]=reward
    q={'id':qid,'kind':kind,'title':'\u5c0f\u8def\u4e0a\u7684\u6258\u4ed8' if kind=='delivery' else '\u5f52\u9014',
       'issuer_id':issuer.id,'recipient_id':target.id,'subject_id':target.id if kind=='rescue' else None,
       'status':'open','assignee_id':None,'reward':reward,'discovered':False,'source_event_ids':[created.id],'created_tick':state.tick,
       'destination':target.tile.model_dump() if kind=='delivery' else issuer.tile.model_dump()}
    if kind=='delivery':
        item=rng.choice(stock);item.owner_id=issuer.id;q['item_id']=item.id;q['item_name']=item.name
        # Some errands go to real available companions, others remain for the player.
        couriers=[a for a in state.actors if a.alive and a.kind=='npc' and not a.task_id and a.id not in (issuer.id,target.id)
                  and meta['people'].get(a.id,{}).get('dynamic') and distance(a.tile,issuer.tile)<=14]
        if couriers and rng.random()<.65:
            courier=rng.choice(couriers)
            # Must collect the parcel at issuer first; no remote teleport of goods.
            task=_schedule(connection,state,courier,issuer.tile.model_copy(),'MOVE',created.id,region,target_id=issuer.id,
                           effect={'action':'COURIER_COLLECT','quest_id':qid})
            if task:q['status']='active';q['assignee_id']=courier.id;q['task_id']=task.id
    else:
        meta['people'].setdefault(target.id,{})['lost']=True
        q['description']='\u6709\u4e00\u4f4d\u65c5\u4eba\u5fd8\u8bb0\u4e86\u5f52\u9014\u3002\u627e\u5230\u4ed6\uff0c\u4e0e\u4ed6\u4ea4\u8c08\uff0c\u518d\u8bf7\u4ed6\u8ddf\u968f\u4f60\u56de\u5230\u59d4\u6258\u4eba\u9644\u8fd1\u3002'
    state.quests.append(q)
    created.facts['title']=q['title']
    return q


def task_effect(connection,state,effect,task,actor,finished,region,seq):
    """Called only after C validated an actual successful arrival."""
    q=next((q for q in state.quests if q['id']==effect.get('quest_id')),None)
    if not q or q['status']!='active':return []
    events=[]
    if effect['action']=='COURIER_COLLECT':
        item=next((i for i in state.items if i.id==q.get('item_id') and i.owner_id==q['issuer_id']),None)
        recipient=next((a for a in state.actors if a.id==q['recipient_id'] and a.alive),None)
        if item is None or recipient is None:
            return [event(state,'task_failed',seq,actor.id,q['recipient_id'],{'task_id':task.id,'reason':'parcel_or_recipient_missing'},[finished.id],[actor.id])]
        item.owner_id=actor.id
        e=event(state,'parcel_collected',seq,actor.id,q['issuer_id'],{'quest_id':q['id'],'item_id':item.id},[finished.id],near_witnesses(state,actor.tile));events.append(e)
        following=_schedule(connection,state,actor,recipient.tile.model_copy(),'MOVE',e.id,region,target_id=recipient.id,
                            effect={'action':'COURIER_DELIVER','quest_id':q['id']})
        if following:
            q['task_id']=following.id
        else:
            events.append(event(state,'task_failed',seq+len(events),actor.id,recipient.id,{'task_id':task.id,'reason':'route_unavailable'},[e.id],[actor.id]))
    elif effect['action']=='COURIER_DELIVER':
        from server.world.items import apply_item_command
        events=apply_item_command(state,'GIVE',{'actor_id':actor.id,'target_id':q['recipient_id'],'item_id':q['item_id']},seq)
        events[0].caused_by=[finished.id]
    return events


EVENT_LABELS={
 'hit_applied':'\u6218\u6597\u4e2d\u7684\u4e00\u51fb','player_downed':'\u65c5\u4eba\u5012\u4e0b','gold_dropped':'\u9057\u843d\u7684\u94b1\u888b',
 'world_created':'\u65b0\u7684\u65c5\u9014\u5f00\u59cb', 'trade_opened':'\u67e5\u770b\u8d27\u7269',
 'price_negotiated':'\u5546\u8bae\u4ef7\u683c','shop_purchase':'\u5b8c\u6210\u4ea4\u6613','container_opened':'\u6253\u5f00\u7bb1\u5b50',
 'container_item_taken':'\u83b7\u53d6\u7bb1\u4e2d\u7269\u54c1','gold_collected':'\u62fe\u53d6\u91d1\u5e01','actor_died':'\u6709\u4eba\u5012\u4e0b',
 'traveler_arrived':'\u65c5\u4eba\u5230\u6765','wildlife_arrived':'\u91ce\u5916\u751f\u7075\u51fa\u73b0',
 'quest_created':'\u65b0\u7684\u59d4\u6258','quest_information':'\u5f97\u77e5\u59d4\u6258','quest_accepted':'\u63a5\u4e0b\u6258\u4ed8',
 'quest_completed':'\u6258\u4ed8\u5b8c\u6210','quest_failed':'\u6258\u4ed8\u4e2d\u65ad','parcel_collected':'\u5546\u961f\u63d0\u8d27',
 'task_succeeded':'\u884c\u52a8\u5b8c\u6210','task_failed':'\u884c\u52a8\u53d7\u963b','item_given':'\u7269\u54c1\u8f6c\u4ea4',
 'item_equipped':'\u66f4\u6362\u88c5\u5907','item_picked_up':'\u62fe\u53d6\u7269\u54c1','resource_gathered':'\u6536\u96c6\u8d44\u6e90',
 'relationship_changed':'\u5173\u7cfb\u53d8\u5316','item_consumed':'\u4f7f\u7528\u836f\u5242','npc_speech':'\u4e00\u6b21\u4ea4\u8c08'}


def journal(connection,state,after_seq=0,limit=50):
    rows=connection.execute('SELECT body FROM events WHERE world_id=? AND seq>? ORDER BY seq',(state.world_id,after_seq))
    entries=[]
    for row in rows:
        e=json.loads(row[0])
        if state.player_id not in e['witness_ids'] or e['type'] not in EVENT_LABELS:continue
        detail=e['facts'].get('title') or e['facts'].get('explanation') or ''
        if e['type']=='npc_speech':detail=e['facts'].get('text','')
        if e['type']=='shop_purchase':detail=e['facts'].get('item_name','')+'  '+str(e['facts'].get('price',0))+' \u91d1\u5e01'
        if e['type']=='hit_applied':detail='\u5b9e\u9645\u4f24\u5bb3 '+str(e['facts'].get('damage',0))
        if e['type']=='container_item_taken':detail=next((i.name for i in state.items if i.id==e['facts'].get('item_id')),detail)
        if e['type']=='gold_collected':detail=str(e['facts'].get('amount',0))+' \u91d1\u5e01'
        entries.append({'event_id':e['id'],'event_seq':e['event_seq'],'tick':e['tick'],'title':EVENT_LABELS[e['type']],
                        'text':str(detail)[:600],'caused_by':e['caused_by'],'type':e['type']})
        if len(entries)>limit:break
    page=entries[:limit]
    return {'entries':page,'has_more':len(entries)>limit,'next_after_seq':page[-1]['event_seq'] if page else after_seq,
            'quests':[q for q in state.quests if q.get('discovered') or q.get('assignee_id')==state.player_id]}


def _defend(connection,state,meta,hit,events,region):
    defender=next((a for a in state.actors if a.id==hit.target_id and a.alive),None)
    attacker=next((a for a in state.actors if a.id==hit.actor_id and a.alive),None)
    if defender is None or attacker is None:return
    if any(t.actor_id==defender.id and t.target_id==attacker.id and t.kind in ('ATTACK','FLEE') and t.status in ('pending','running') for t in state.tasks):return
    for task in state.tasks:
        if task.actor_id==defender.id and task.status in ('pending','running'):
            task.status='cancelled'
            events.append(event(state,'task_cancelled',events[-1].event_seq+1,defender.id,attacker.id,{'task_id':task.id,'reason':'danger'},[hit.id],[defender.id]))
    defender.task_id=None
    p=meta['people'][defender.id]
    events.append(event(state,'npc_protested',events[-1].event_seq+1,defender.id,attacker.id,
        {'text':'\u4f4f\u624b\uff01','mode':'policy'},[hit.id],near_witnesses(state,defender.tile)))
    run=defender.hp/defender.max_hp<.4 or p.get('personality',{}).get('courage',.5)<.55
    guards=[a for a in state.actors if a.alive and a.kind=='npc' and a.id not in (attacker.id,defender.id)
            and distance(a.tile,defender.tile)<7 and any(w in meta['people'].get(a.id,{}).get('role','') for w in ('\u4f63\u5175','\u730e\u4eba','\u5b88\u536b'))]
    help_event=None
    if run and guards:
        guard=min(guards,key=lambda a:distance(a.tile,defender.tile))
        help_event=event(state,'npc_speech',events[-1].event_seq+1,defender.id,guard.id,{'text':'\u6709\u4eba\u88ad\u51fb\u6211\uff0c\u8bf7\u5e2e\u5fd9\uff01','mode':'policy','source_type':'report'},[hit.id],near_witnesses(state,defender.tile))
        events.append(help_event)
        if not guard.task_id and p.get('relations',{}).get(guard.id,{}).get('hostility',0)<40:
            guard_task=Task(id='task_'+uuid4().hex,actor_id=guard.id,kind='ATTACK',target_id=attacker.id,target_region_id=guard.region_id,
                target_tile=attacker.tile.model_copy(),status='pending',started_tick=state.tick,source_event_ids=[help_event.id])
            state.tasks.append(guard_task);guard.task_id=guard_task.id;guard.behavior='attacking'
    if run:
        dx=defender.tile.x-attacker.tile.x;dy=defender.tile.y-attacker.tile.y
        scale=max(.1,math.hypot(dx,dy))
        destination=free_tile(region,defender.tile.x+dx/scale*7,defender.tile.y+dy/scale*7)
        if not reachable(region,defender.tile,destination):destination=defender.tile.model_copy()
        kind='FLEE';behavior='fleeing'
    else:destination=attacker.tile.model_copy();kind='ATTACK';behavior='attacking'
    task=Task(id='task_'+uuid4().hex,actor_id=defender.id,kind=kind,target_id=attacker.id,target_region_id=defender.region_id,
        target_tile=destination,status='pending',started_tick=state.tick,source_event_ids=[hit.id])
    state.tasks.append(task);defender.task_id=task.id;defender.behavior=behavior
    connection.execute('INSERT INTO task_effects VALUES (?,?,?)',(state.world_id,task.id,json.dumps({'action':'SELF_DEFENSE'})))
    events.append(event(state,'task_scheduled',events[-1].event_seq+1,defender.id,attacker.id,{'task_id':task.id,'action':kind,'mode':'policy','reason':'health_and_personality'},[hit.id],[defender.id,attacker.id]))


def director_errand(connection,state,proposal,region,seq):
    meta=read(connection,state.world_id)
    if not meta:raise WorldError('FEATURE_DISABLED','Living-world tasks are not enabled here.')
    if sum(q['status'] in ('open','active') for q in state.quests)>=ACTIVE_QUEST_LIMIT:
        raise WorldError('QUEST_LIMIT','Too many active errands.')
    emitted=[]
    def emit(kind,actor,target,facts,sources=(),witnesses=()):
        value=event(state,kind,seq+len(emitted),actor,target,facts,list(sources),list(witnesses))
        emitted.append(value);return value
    q=_create_errand(connection,state,region,meta,emit,_rng(state,'director:'+proposal.target_id),
                     preferred_issuer=proposal.target_id,kind=proposal.quest_kind,mode='live',sources=proposal.source_event_ids)
    if not q:raise WorldError('PRECONDITION_FAILED','No safe route, available parcel, helper or reward budget.')
    emitted[0].facts['reason_summary']=proposal.reason_summary
    write(connection,state.world_id,meta)
    return emitted[0]
