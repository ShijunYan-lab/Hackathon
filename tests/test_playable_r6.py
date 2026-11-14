"""Real API/database regression tests; no model credentials or Godot required."""
import asyncio
import json
import random
import time
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from release.run_backend import make_app
from shared.protocol import StateView, Tile, AgentDecision
from server.world import living_world as life
from server.world.director import DirectorProposal
from server.world.director_execution import execute

@pytest.fixture
def game(tmp_path,monkeypatch):
    for key in ('LLM_API_KEY','WORLD_MODEL_API_KEY','LLM_MODEL','LLM_BASE_URL','WORLD_NPC_MODEL_DEMO'):
        monkeypatch.setenv(key,'')
    app=make_app(tmp_path/'game.sqlite3')
    with TestClient(app) as client:
        result=client.post('/v1/worlds',json={'request_id':'new','seed':42,'player_name':'Player','appearance':'female'})
        assert result.status_code==200,result.text
        yield client,app,result.json()['data']['state']

def route(state):return '/v1/worlds/'+state['world_id']
def body(state,**kwargs):return {'request_id':uuid4().hex,'expected_world_version':state['world_version'],**kwargs}
def post(c,s,path,**kwargs):return c.post(route(s)+path,json=body(s,**kwargs))
def command(c,s,kind,payload):return post(c,s,'/commands',kind=kind,payload=payload)
def fresh(c,s):return c.get(route(s)+'/state').json()['data']['state']
def near(c,s,actor_id,tile):
    result=command(c,s,'CHECKPOINT',{'region_id':'overworld','positions':[{'actor_id':actor_id,'tile':tile}]})
    assert result.status_code==200,result.text
    return result.json()['data']['state']
def merchant(s):
    box=next(v for v in s['containers'] if v['kind']=='merchant')
    return next(a for a in s['actors'] if a['id']==box['merchant_id'])
def speech(c,s,npc,text):return post(c,s,'/dialogue',npc_id=npc['id'],text=text)
def edit(app,s,fn):
    model=app.state.store.state(s['world_id'])
    with app.state.store.connection(write=True) as conn:
        fn(conn,model)
        conn.execute('UPDATE worlds SET state=? WHERE id=?',(model.model_dump_json(),model.world_id))
    return model.model_dump(mode='json')

def test_new_game_modest_gear_and_auto_save(game):
    c,app,s=game
    own=[i for i in s['items'] if i['owner_id']==s['player_id']]
    assert {i['base_type'] for i in own}=={'sword','armor'} and len(own)==2
    assert next(i for i in own if i['base_type']=='sword')['stats']['damage']==4
    assert s['appearance']=='female' and s['known_npc_ids']==[]
    assert c.get('/v1/saves').json()['data']['saves'][0]['appearance']=='female'
    assert c.get(route(s)+'/economy').json()['data']['wallets'][s['player_id']]==12
    repeated=c.post('/v1/worlds',json={'request_id':'new','seed':42,'player_name':'Player','appearance':'female'})
    assert repeated.json()['data']['state']==s
    assert len(c.get('/v1/saves').json()['data']['saves'])==1

def test_population_and_containers_are_walkable_and_stock_not_worn(game):
    c,app,s=game
    assert sum(a['kind']=='npc' for a in s['actors'])==19
    assert sum(a['kind']=='monster' for a in s['actors'])==10
    assert len(s['containers'])>=10
    region=app.state.region;blocked={tuple(x) for x in region['blocked_tiles']}
    for a in s['actors']+s['containers']:
        assert (int(a['tile']['x']),int(a['tile']['y'])) not in blocked
    for box in [b for b in s['containers'] if b['kind']=='merchant']:
        stock=[i for i in s['items'] if i['owner_id']==box['id']]
        actor=next(a for a in s['actors'] if a['id']==box['merchant_id'])
        assert len(stock)>=6 and actor['equipped_item_id'] not in {i['id'] for i in stock}

def test_free_text_opens_real_shop_and_name_is_learned(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    result=speech(c,s,npc,'\u6211\u60f3\u770b\u770b\u4f60\u7684\u4e1c\u897f')
    assert result.status_code==200,result.text
    data=result.json()['data'];s=data['state']
    assert data['mode']=='fallback' and data['ui_actions']==[{'kind':'open_trade','merchant_id':npc['id']}]
    assert s['known_npc_ids']==[]
    data=speech(c,s,npc,'\u4f60\u53eb\u4ec0\u4e48\u540d\u5b57').json()['data']
    assert npc['id'] in data['state']['known_npc_ids']
    assert npc['name'] in data['reply']

def test_bargain_is_bounded_nonstacking_and_reacts_to_actual_memory(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    def set_generosity(conn,model):
        meta=life.read(conn,model.world_id);meta['people'][npc['id']]['personality']['generosity']=.9
        life.write(conn,model.world_id,meta)
    s=edit(app,s,set_generosity)
    for _ in range(2):
        r=speech(c,s,npc,'\u80fd\u7ed9\u6211\u6253\u6298\u5417');assert r.status_code==200,r.text
        s=r.json()['data']['state'];quote=c.get(route(s)+'/shops/'+npc['id']).json()['data']
        assert quote['discount_percent']==9
    r=speech(c,s,npc,'\u4f60\u662f\u4e2a\u80c6\u5c0f\u9b3c');s=r.json()['data']['state']
    assert c.get(route(s)+'/shops/'+npc['id']).json()['data']['discount_percent']==0
    for _ in range(2):s=speech(c,s,npc,'\u6211\u8981\u6740\u4e86\u4f60').json()['data']['state']
    assert c.get(route(s)+'/shops/'+npc['id']).json()['error']['code']=='TRADE_REFUSED'
    with app.state.store.connection() as conn:
        relation=life.read(conn,s['world_id'])['people'][npc['id']]['relations'][s['player_id']]
        assert relation['hostility']>=45 and len(relation['sources'])==3

def test_buy_transfers_exact_item_and_retries_do_not_charge_twice(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    shop=c.get(route(s)+'/shops/'+npc['id']).json()['data']
    listing=next(v for v in shop['stock'] if v['item']['base_type']=='consumable')
    payload=body(s,item_id=listing['item']['id'],quote_id=shop['quote_id'])
    r=c.post(route(s)+'/shops/'+npc['id']+'/buy',json=payload);assert r.status_code==200,r.text
    assert c.post(route(s)+'/shops/'+npc['id']+'/buy',json=payload).json()==r.json()
    s=r.json()['data']['state'];assert next(i for i in s['items'] if i['id']==listing['item']['id'])['owner_id']==s['player_id']
    assert c.get(route(s)+'/economy').json()['data']['wallets'][s['player_id']]==6

@pytest.mark.parametrize('case',['poor','quote','price','far'])
def test_trade_rejects_invalid_requests(game,case):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    shop=c.get(route(s)+'/shops/'+npc['id']).json()['data'];listing=max(shop['stock'],key=lambda v:v['price'])
    payload=body(s,item_id=listing['item']['id'],quote_id=shop['quote_id'])
    expected='INSUFFICIENT_FUNDS'
    if case=='quote':payload['quote_id']='old';expected='QUOTE_EXPIRED'
    if case=='price':payload['price']=0;expected='INVALID_SCHEMA'
    if case=='far':
        s=near(c,s,s['player_id'],{'x':120.5,'y':143.5});payload['expected_world_version']=s['world_version'];expected='OUT_OF_RANGE'
    r=c.post(route(s)+'/shops/'+npc['id']+'/buy',json=payload)
    assert r.json()['error']['code']==expected,r.text

def test_chest_take_coins_item_and_snapshot_persistence(game):
    c,app,s=game;box=next(b for b in s['containers'] if b['kind']=='cache');s=near(c,s,s['player_id'],box['tile'])
    data=c.get(route(s)+'/containers/'+box['id']).json()['data'];item=data['items'][0]
    request=body(s,item_id=item['id'],take_gold=True)
    r=c.post(route(s)+'/containers/'+box['id']+'/take',json=request);assert r.status_code==200,r.text
    assert c.post(route(s)+'/containers/'+box['id']+'/take',json=request).json()==r.json()
    s=r.json()['data']['state']
    assert c.get(route(s)+'/economy').json()['data']['wallets'][s['player_id']]==12+box['gold']
    again=post(c,s,'/containers/'+box['id']+'/take',item_id=None,take_gold=True)
    assert again.json()['error']['code']=='EMPTY_CONTAINER'
    save=post(c,s,'/saves',label='Chest checked').json()['data']['save_id']
    branch=c.post('/v1/saves/'+save+'/load',json={'request_id':'load-chest'}).json()['data']['state']
    actual=next(b for b in branch['containers'] if b['id']==box['id']);assert actual['gold']==0 and actual['opened']
    assert next(i for i in branch['items'] if i['id']==item['id'])['owner_id']==branch['player_id']
    with app.state.store.connection() as conn:
        assert life.read(conn,branch['world_id'])==life.read(conn,s['world_id'])

def test_owned_merchant_chest_cannot_be_looted(game):
    c,app,s=game;box=next(b for b in s['containers'] if b['kind']=='merchant');s=near(c,s,s['player_id'],box['tile'])
    assert c.get(route(s)+'/containers/'+box['id']).json()['error']['code']=='MERCHANT_STOCK'

def test_potions_and_armor_have_real_effects(game):
    c,app,s=game;box=next(b for b in s['containers'] if b['kind']=='cache');s=near(c,s,s['player_id'],box['tile'])
    item=next(i for i in s['items'] if i['owner_id']==box['id'] and i['base_type']=='consumable')
    s=post(c,s,'/containers/'+box['id']+'/take',item_id=item['id']).json()['data']['state']
    assert post(c,s,'/consume',item_id=item['id']).json()['error']['code']=='ALREADY_HEALTHY'
    s=edit(app,s,lambda conn,model:setattr(model.actors[0],'hp',30))
    s=post(c,s,'/consume',item_id=item['id']).json()['data']['state'];assert s['actors'][0]['hp']==55
    assert item['id'] not in {i['id'] for i in s['items']}
    armor=next(i for i in s['items'] if i['owner_id']==s['player_id'] and i['base_type']=='armor')
    for _ in range(2):s=command(c,s,'EQUIP',{'actor_id':s['player_id'],'item_id':armor['id']}).json()['data']['state']
    assert s['actors'][0]['armor']==1

@pytest.mark.parametrize('courage,expected',[(.1,'FLEE'),(.95,'ATTACK')])
def test_personality_reaction_and_persistent_hostility(game,courage,expected):
    c,app,s=game;npc=merchant(s)
    def temperament(conn,model):
        meta=life.read(conn,model.world_id);meta['people'][npc['id']]['personality']['courage']=courage;life.write(conn,model.world_id,meta)
    s=edit(app,s,temperament)
    r=command(c,s,'HIT',{'attack_id':uuid4().hex,'attacker_id':s['player_id'],'target_id':npc['id'],'weapon_id':s['actors'][0]['equipped_item_id'],'region_id':'overworld','attacker_tile':{'x':120.5,'y':143.5},'target_tile':{'x':121.5,'y':143.5}})
    assert r.status_code==200,r.text;s=r.json()['data']['state']
    assert any(t['actor_id']==npc['id'] and t['kind']==expected for t in s['tasks'])
    with app.state.store.connection() as conn:assert life.read(conn,s['world_id'])['people'][npc['id']]['relations'][s['player_id']]['hostility']>=55

def test_death_converts_existing_stock_and_drops_gold_once(game):
    c,app,s=game;npc=merchant(s)
    s=edit(app,s,lambda conn,model:setattr(next(a for a in model.actors if a.id==npc['id']),'hp',1))
    hit={'attack_id':'kill','attacker_id':s['player_id'],'target_id':npc['id'],'weapon_id':s['actors'][0]['equipped_item_id'],'region_id':'overworld','attacker_tile':{'x':120.5,'y':143.5},'target_tile':{'x':121.5,'y':143.5}}
    r=command(c,s,'HIT',hit);assert r.status_code==200,r.text;s=r.json()['data']['state']
    assert not next(a for a in s['actors'] if a['id']==npc['id'])['alive']
    assert next(b for b in s['containers'] if b.get('estate_id')==npc['id'])['kind']=='cache'
    purse=next(i for i in s['items'] if i['material_id']=='coins')
    s=command(c,s,'PICKUP',{'actor_id':s['player_id'],'item_id':purse['id']}).json()['data']['state']
    assert not any(i['id']==purse['id'] for i in s['items'])
    assert command(c,s,'PICKUP',{'actor_id':s['player_id'],'item_id':purse['id']}).status_code>=400

def heartbeat(c,s):
    r=post(c,s,'/heartbeat',reason='idle_timer',trigger_event_ids=[]);assert r.status_code==200,r.text
    return r.json()['data']['state']

def test_world_generates_real_errands_and_caps_population(game):
    c,app,s=game
    for _ in range(18):s=heartbeat(c,s)
    assert len(s['quests'])>=1
    assert sum(a['alive'] and a['kind']=='npc' for a in s['actors'])<=life.NPC_LIMIT
    assert sum(a['alive'] and a['kind']=='monster' for a in s['actors'])<=life.MONSTER_LIMIT
    assert any(t['kind']=='MOVE' for t in s['tasks'])
    assert sum(q['status'] in ('open','active') for q in s['quests'])<=life.ACTIVE_QUEST_LIMIT
    with app.state.store.connection() as conn:
        ids={r[0] for r in conn.execute('SELECT id FROM events WHERE world_id=?',(s['world_id'],))}
        assert all(set(q['source_event_ids'])<=ids for q in s['quests'])
        assert all(i['owner_id'] is None or i['owner_id'] in {a['id'] for a in s['actors']}|{b['id'] for b in s['containers']} for i in s['items'])

def make_quest(app,s,kind='delivery'):
    state=app.state.store.state(s['world_id'])
    with app.state.store.connection(write=True) as conn:
        source=conn.execute('SELECT id FROM events WHERE world_id=? ORDER BY seq LIMIT 1',(state.world_id,)).fetchone()[0]
        issuer=merchant(s)['id']
        proposal=DirectorProposal(kind='ERRAND',target_id=issuer,quest_kind=kind,source_event_ids=[source],reason_summary='Existing merchant resources and a safe route support this task.')
        seq=conn.execute('SELECT MAX(seq)+1 FROM events WHERE world_id=?',(state.world_id,)).fetchone()[0]
        state,outcome,accepted=execute(conn,state,proposal,app.state.turns.config,app.state.region,seq)
        assert accepted,outcome
        # Force an open player task for this test, cancelling any actual courier.
        q=state.quests[-1]
        if q.get('task_id'):
            t=next(t for t in state.tasks if t.id==q['task_id']);t.status='cancelled'
            a=next(a for a in state.actors if a.id==t.actor_id);a.task_id=None;a.behavior='idle'
            q.pop('task_id');q['status']='open';q['assignee_id']=None
        conn.execute('UPDATE worlds SET state=? WHERE id=?',(state.model_dump_json(),state.world_id))
        app.state.store.append_event(conn,state.world_id,outcome)
    return state.model_dump(mode='json'),q

@pytest.mark.parametrize('kind',['delivery','rescue'])
def test_real_quest_accept_execution_and_escrow_reward(game,kind):
    c,app,s=game;s,q=make_quest(app,s,kind)
    issuer=next(a for a in s['actors'] if a['id']==q['issuer_id']);s=near(c,s,s['player_id'],issuer['tile'])
    s=post(c,s,'/quests/accept',quest_id=q['id']).json()['data']['state']
    target=next(a for a in s['actors'] if a['id']==q['recipient_id'])
    s=near(c,s,s['player_id'],target['tile'])
    if kind=='delivery':
        r=command(c,s,'GIVE',{'actor_id':s['player_id'],'target_id':target['id'],'item_id':q['item_id']})
    else:
        r=speech(c,s,target,'\u6211\u5e26\u4f60\u56de\u5bb6');assert r.status_code==200,r.text;s=r.json()['data']['state']
        task=next(t for t in s['tasks'] if t['actor_id']==target['id'] and t['status']=='pending')
        s=near(c,s,target['id'],task['target_tile'])
        r=command(c,s,'TASK_REPORT',{'task_id':task['id'],'actor_id':target['id'],'status':'succeeded','region_id':'overworld','tile':task['target_tile'],'failure_code':None})
    assert r.status_code==200,r.text;s=r.json()['data']['state']
    assert next(v for v in s['quests'] if v['id']==q['id'])['status']=='completed'
    assert c.get(route(s)+'/economy').json()['data']['wallets'][s['player_id']]==17

def test_journal_is_source_linked_and_private_memories_are_not_returned(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    s=speech(c,s,npc,'\u4f60\u53eb\u4ec0\u4e48\u540d\u5b57').json()['data']['state']
    page=c.get(route(s)+'/journal?limit=1').json()['data']
    assert len(page['entries'])==1 and page['has_more']
    assert not any(k in page for k in ('memories','personality','beliefs','relationships'))
    second=c.get(route(s)+'/journal?after_seq='+str(page['next_after_seq'])).json()['data']
    assert all(v['event_seq']>page['next_after_seq'] for v in second['entries'])
    s=heartbeat(c,s)
    # Purchased items and task outcomes are covered by the persistent journal; all
    # event IDs exposed here belong to the same actual world ledger.
    with app.state.store.connection() as conn:
        ids={r[0] for r in conn.execute('SELECT id FROM events WHERE world_id=?',(s['world_id'],))}
    assert all(set(v['caused_by'])<=ids for v in second['entries'])

def test_model_configuration_never_echoes_or_saves_key(game):
    c,app,s=game
    secret='example-test-key-not-a-real-secret'
    r=c.post('/v1/local/model',json={'request_id':'config','enabled':True,'base_url':'https://example.invalid/v1','model':'example','api_key':secret})
    assert r.status_code==200,r.text
    assert secret not in r.text and secret not in c.get('/v1/local/model').text
    with app.state.store.connection() as conn:
        assert secret not in '\n'.join(conn.iterdump())
    blocked=c.post('/v1/local/model',headers={'Origin':'https://untrusted.example'},json={'request_id':'bad','enabled':False})
    assert blocked.status_code==403
    assert c.post('/v1/local/model',json={'request_id':'http','enabled':True,'base_url':'http://example.invalid','model':'m','api_key':'k'}).status_code==400
    c.post('/v1/local/model',json={'request_id':'off','enabled':False})

def test_ambient_model_work_does_not_block_command_response(game):
    c,app,s=game
    async def slow_plan(context,triggers):
        await asyncio.sleep(.8)
        return AgentDecision(reply='',intent={'action':'WAIT'})
    app.state.agents.gateway.plan_provider=slow_plan
    start=time.monotonic();s=heartbeat(c,s);elapsed=time.monotonic()-start
    assert elapsed<.7
    r=command(c,s,'CHECKPOINT',{'region_id':'overworld','positions':[{'actor_id':s['player_id'],'tile':s['actors'][0]['tile']}]})
    assert r.status_code==200,r.text

def test_autonomous_courier_collects_then_delivers_real_parcel(game,monkeypatch):
    c,app,s=game
    issuer=merchant(s)
    with app.state.store.connection() as conn:
        meta=life.read(conn,s['world_id'])
    courier=next(a for a in s['actors'] if meta['people'].get(a['id'],{}).get('dynamic'))
    s=near(c,s,courier['id'],issuer['tile'])
    class FirstChoices:
        def choice(self,values):return values[0]
        def random(self):return 0.0
    monkeypatch.setattr(life,'_rng',lambda *args:FirstChoices())
    state=app.state.store.state(s['world_id'])
    with app.state.store.connection(write=True) as conn:
        source=conn.execute('SELECT id FROM events WHERE world_id=? ORDER BY seq LIMIT 1',(state.world_id,)).fetchone()[0]
        proposal=DirectorProposal(kind='ERRAND',target_id=issuer['id'],quest_kind='delivery',source_event_ids=[source],reason_summary='Real stock, budget and a free courier are available.')
        seq=conn.execute('SELECT MAX(seq)+1 FROM events WHERE world_id=?',(state.world_id,)).fetchone()[0]
        state,outcome,accepted=execute(conn,state,proposal,app.state.turns.config,app.state.region,seq)
        assert accepted
        conn.execute('UPDATE worlds SET state=? WHERE id=?',(state.model_dump_json(),state.world_id))
        app.state.store.append_event(conn,state.world_id,outcome)
    s=state.model_dump(mode='json');q=s['quests'][-1]
    assert q['status']=='active' and q['assignee_id']==courier['id']
    assert next(i for i in s['items'] if i['id']==q['item_id'])['owner_id']==issuer['id']
    old_gold=c.get(route(s)+'/economy').json()['data']['wallets'][courier['id']]
    for step in range(2):
        task=next(t for t in s['tasks'] if t['actor_id']==courier['id'] and t['status']=='pending')
        s=near(c,s,courier['id'],task['target_tile'])
        r=command(c,s,'TASK_REPORT',{'task_id':task['id'],'actor_id':courier['id'],'status':'succeeded','region_id':'overworld','tile':task['target_tile'],'failure_code':None})
        assert r.status_code==200,r.text
        s=r.json()['data']['state']
        owner=next(i for i in s['items'] if i['id']==q['item_id'])['owner_id']
        assert owner==(courier['id'] if step==0 else q['recipient_id'])
    assert next(v for v in s['quests'] if v['id']==q['id'])['status']=='completed'
    assert c.get(route(s)+'/economy').json()['data']['wallets'][courier['id']]==old_gold+5


def test_ambient_proposal_is_applied_on_following_heartbeat(game):
    c,app,s=game
    async def planner(context,triggers):
        return AgentDecision(reply='',intent={'action':'WAIT'},reason_summary='Nothing urgent in this private context.')
    app.state.agents.gateway.plan_provider=planner
    s=heartbeat(c,s)
    deadline=time.monotonic()+2
    while s['world_id'] not in app.state.ambient.ready and time.monotonic()<deadline:time.sleep(.02)
    result=post(c,s,'/heartbeat',reason='idle_timer',trigger_event_ids=[])
    assert result.status_code==200,result.text
    summaries=result.json()['data']['decision_summaries']
    assert summaries and summaries[0]['mode']=='live'


def test_journal_creates_persistent_factual_chapter_after_purchase(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    shop=c.get(route(s)+'/shops/'+npc['id']).json()['data']
    listing=next(v for v in shop['stock'] if v['item']['base_type']=='consumable')
    s=post(c,s,'/shops/'+npc['id']+'/buy',item_id=listing['item']['id'],quote_id=shop['quote_id']).json()['data']['state']
    s=heartbeat(c,s)
    chapters=c.get(route(s)+'/journal').json()['data']['chapters']
    assert chapters and chapters[0]['mode']=='rules' and chapters[0]['source_event_ids']
    with app.state.store.connection() as conn:
        ids={r[0] for r in conn.execute('SELECT id FROM events WHERE world_id=?',(s['world_id'],))}
    assert set(chapters[0]['source_event_ids'])<=ids
