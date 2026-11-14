"""R7 real SQLite/API integration tests. Explicit QA setup never ships as gameplay."""
from test_playable_r6 import game, route, body, post, command, near, speech, edit, fresh, merchant
from server.world import living_world as life
from server.world import continuity as r7
from shared.protocol import StateView
from uuid import uuid4


def ok(r):
    assert r.status_code==200,r.text
    return r.json()['data']['state']


def heartbeat(c,s):return ok(post(c,s,'/heartbeat',reason='idle_timer',trigger_event_ids=[]))
def interact(c,s,action,target):return post(c,s,'/interact',action=action,target_id=target)
def first_npc(s):return next(a for a in s['actors'] if a['kind']=='npc')


def test_free_hire_is_continuous_persistent_and_can_end(game):
    c,app,s=game;npc=first_npc(s);s=near(c,s,s['player_id'],npc['tile'])
    s=ok(speech(c,s,npc,'请免费跟随我，一起同行。'))
    contract=s['contracts'][0];assert contract['status']=='active'
    task=next(t for t in s['tasks'] if t['actor_id']==npc['id'] and t['status']=='pending')
    assert task['kind']=='FOLLOW' and task['target_id']==s['player_id']
    attempt=command(c,s,'TASK_REPORT',{'task_id':task['id'],'actor_id':npc['id'],'status':'succeeded','region_id':'overworld','tile':npc['tile']})
    assert attempt.json()['error']['code']=='CONTINUOUS_TASK'
    save=post(c,s,'/saves',label='hire').json()['data']['save_id']
    restored=c.post('/v1/saves/'+save+'/load',json={'request_id':uuid4().hex}).json()['data']['state']
    assert restored['contracts']==s['contracts']
    s=fresh(c,s)
    s=ok(interact(c,s,'DISMISS',npc['id']))
    assert s['contracts'][0]['status']=='ended'
    assert not any(t['actor_id']==npc['id'] and t['status']=='pending' and t['kind']=='FOLLOW' for t in s['tasks'])


def test_fee_hire_does_not_follow_until_real_payment_and_retry_is_idempotent(game):
    c,app,s=game;npc=first_npc(s);s=near(c,s,s['player_id'],npc['tile'])
    s=ok(speech(c,s,npc,'我想雇佣你保护我，酬金50金币。'))
    assert s['contracts'][0]['status']=='pending_payment'
    assert not any(t['kind']=='FOLLOW' for t in s['tasks'])
    assert interact(c,s,'PAY_HIRE',npc['id']).json()['error']['code']=='INSUFFICIENT_FUNDS'
    s=edit(app,s,lambda conn,m:conn.execute('UPDATE wallets SET gold=70 WHERE world_id=? AND actor_id=?',(m.world_id,m.player_id)))
    payload=body(s,action='PAY_HIRE',target_id=npc['id'])
    first=c.post(route(s)+'/interact',json=payload);s=ok(first)
    assert c.post(route(s)+'/interact',json=payload).json()==first.json()
    assert s['contracts'][0]['status']=='active'
    assert c.get(route(s)+'/economy').json()['data']['wallets'][s['player_id']]==20
    coin=next(i for i in s['items'] if i['owner_id']==s['player_id'] and i['material_id']=='currency')
    assert coin['quantity']==20
    assert command(c,s,'GIVE',{'actor_id':s['player_id'],'target_id':npc['id'],'item_id':coin['id']}).json()['error']['code']=='CURRENCY_LEDGER'


def test_resource_depletion_no_double_claim_and_world_time_regeneration(game):
    c,app,s=game;site=next(v for v in s['sites'] if v['kind']=='stone')
    s=near(c,s,s['player_id'],site['tile'])
    for _ in range(site['remaining']):s=ok(interact(c,s,'GATHER',site['id']))
    assert interact(c,s,'GATHER',site['id']).json()['error']['code']=='RESOURCE_DEPLETED'
    assert sum(i['material_id']=='stone' and i['owner_id']==s['player_id'] for i in s['items'])==3
    def regen(conn,m):
        value=next(x for x in m.sites if x.id==site['id']);m.tick=value.regen_tick-1
        # Prevent NPC competition in this resource-regrowth test.
        for a in m.actors[1:]:a.task_id='busy-qa'
    s=edit(app,s,regen);s=heartbeat(c,s)
    assert next(v for v in s['sites'] if v['id']==site['id'])['remaining']==1


def test_nonmerchant_two_way_trade_conserves_money_and_inventory(game):
    c,app,s=game;npc=next(a for a in s['actors'] if a['kind']=='npc' and not any(b.get('merchant_id')==a['id'] for b in s['containers']))
    s=near(c,s,s['player_id'],npc['tile'])
    def grant(conn,m):
        r7.material(m,m.player_id,'stone',r7.source_event(conn,m))
    s=edit(app,s,grant)
    quote=c.get(route(s)+'/shops/'+npc['id']).json()['data'];listing=quote['sellable'][0]
    before=c.get(route(s)+'/economy').json()['data']['wallets'];total=sum(before.values())
    sale=post(c,s,'/shops/'+npc['id']+'/sell',item_id=listing['item']['id'],quote_id=quote['quote_id']);s=ok(sale)
    quote=c.get(route(s)+'/shops/'+npc['id']).json()['data']
    assert any(v['item']['id']==listing['item']['id'] for v in quote['stock'])
    purchase=next(v for v in quote['stock'] if v['item']['id']==listing['item']['id'])
    s=ok(post(c,s,'/shops/'+npc['id']+'/buy',item_id=listing['item']['id'],quote_id=quote['quote_id']))
    assert next(i for i in s['items'] if i['id']==listing['item']['id'])['owner_id']==s['player_id']
    assert sum(c.get(route(s)+'/economy').json()['data']['wallets'].values())==total


def test_boards_discover_real_material_request_and_submission(game):
    c,app,s=game
    for _ in range(6):s=heartbeat(c,s)
    q=next(q for q in s['quests'] if q['kind']=='gather')
    board=next(n for n in s['notices'] if n['kind']=='board')
    s=near(c,s,s['player_id'],board['tile']);s=ok(interact(c,s,'BOARD',board['id']))
    assert next(v for v in s['quests'] if v['id']==q['id'])['discovered']
    issuer=next(a for a in s['actors'] if a['id']==q['issuer_id']);s=near(c,s,s['player_id'],issuer['tile'])
    s=ok(post(c,s,'/quests/accept',quest_id=q['id']))
    assert interact(c,s,'SUBMIT',q['id']).json()['error']['code']=='INSUFFICIENT_MATERIALS'
    def grant(conn,m):
        for _ in range(q['quantity']):r7.material(m,m.player_id,q['material'],r7.source_event(conn,m))
    s=edit(app,s,grant);s=ok(interact(c,s,'SUBMIT',q['id']))
    assert next(v for v in s['quests'] if v['id']==q['id'])['status']=='completed'
    assert interact(c,s,'SUBMIT',q['id']).status_code==400


def test_npc_crafting_healing_repair_and_trade_consume_real_resources(game):
    c,app,s=game;a=first_npc(s)
    def setup(conn,m):
        actor=next(a for a in m.actors if a.id==a_id)
        actor.hp=10
        life._potion(m,actor.id,r7.source_event(conn,m))
        for kind in ('wood','iron','iron','iron'):
            r7.material(m,actor.id,kind,r7.source_event(conn,m))
    a_id=a['id'];s=edit(app,s,setup);s=heartbeat(c,s)
    assert next(v for v in s['actors'] if v['id']==a_id)['hp']==35
    s=heartbeat(c,s)
    assert any(i['owner_id']==a_id and i['quality']=='uncommon' for i in s['items'])
    def damage(conn,m):
        actor=next(a for a in m.actors if a.id==a_id)
        next(i for i in m.items if i.id==actor.equipped_item_id).durability=20
    s=edit(app,s,damage);s=heartbeat(c,s)
    actor=next(a for a in s['actors'] if a['id']==a_id)
    assert next(i for i in s['items'] if i['id']==actor['equipped_item_id'])['durability']==100


def test_safe_zones_guards_elites_and_new_guard_identity(game):
    c,app,s=game
    assert all(not r7.inside_safe(StateView.model_validate(s),__import__('shared.protocol',fromlist=['Tile']).Tile(**a['tile'])) for a in s['actors'] if a['kind']=='monster')
    assert any(a['appearance_key'].startswith('elite_') and a['hp']>22 for a in s['actors'])
    zone=s['safe_zones'][0];guard=zone['guard_ids'][0]
    def kill(conn,m):
        m.actors=[a.model_copy(update={'hp':0,'alive':False,'behavior':'dead'}) if a.id==guard else a for a in m.actors]
        m.safe_zones[0]['replace_tick']=m.tick+1
    s=edit(app,s,kill);s=heartbeat(c,s)
    new=next(v for v in s['safe_zones'][0]['guard_ids'] if v not in zone['guard_ids'])
    assert next(a for a in s['actors'] if a['id']==new)['alive']
    with app.state.store.connection() as conn:
        assert not conn.execute('SELECT 1 FROM npc_dialogue_turns WHERE world_id=? AND npc_id=?',(s['world_id'],new)).fetchone()


def test_task_clues_and_journal_hide_internal_coordinates_and_noise(game):
    c,app,s=game
    for _ in range(8):s=heartbeat(c,s)
    q=next(q for q in s['quests'] if q['kind']=='delivery')
    issuer=next(a for a in s['actors'] if a['id']==q['issuer_id']);s=near(c,s,s['player_id'],issuer['tile'])
    result=speech(c,s,issuer,'这份货物要送给谁，叫什么，在哪里？');s=ok(result)
    recipient=next(a for a in s['actors'] if a['id']==q['recipient_id'])
    assert recipient['name'] in result.json()['data']['reply']
    data=c.get(route(s)+'/journal').json()['data']
    assert all('destination' not in v for v in data['quests'])
    assert not any(v['type'] in ('hit_applied','npc_speech','gold_collected','item_picked_up') for v in data['entries'])


def test_reconciliation_delivery_names_recipient_and_only_forgives_after_handoff(game):
    c,app,s=game;npc=merchant(s);s=near(c,s,s['player_id'],npc['tile'])
    def hostile(conn,m):
        meta=life.read(conn,m.world_id)
        relation=life._relation(meta,npc['id'],m.player_id);relation['hostility']=30
        life.write(conn,m.world_id,meta)
    s=edit(app,s,hostile)
    r=speech(c,s,npc,'我该怎么和解，能帮你送货吗？');s=ok(r)
    q=next(q for q in s['quests'] if q.get('reconcile'))
    recipient=next(a for a in s['actors'] if a['id']==q['recipient_id'])
    assert recipient['name'] in r.json()['data']['reply']
    s=ok(post(c,s,'/quests/accept',quest_id=q['id']))
    with app.state.store.connection() as conn:assert life._relation(life.read(conn,s['world_id']),npc['id'],s['player_id'])['hostility']==30
    s=near(c,s,s['player_id'],recipient['tile'])
    s=ok(command(c,s,'GIVE',{'actor_id':s['player_id'],'target_id':recipient['id'],'item_id':q['item_id']}))
    assert next(v for v in s['quests'] if v['id']==q['id'])['status']=='completed'
    with app.state.store.connection() as conn:assert life._relation(life.read(conn,s['world_id']),npc['id'],s['player_id'])['hostility']==0


def test_npc_buys_medicine_and_trades_surplus_with_real_money(game):
    c,app,s=game;npc=first_npc(s);seller=next(a for a in s['actors'] if a['kind']=='npc' and a['id']!=npc['id'])
    def setup(conn,m):
        a=next(a for a in m.actors if a.id==npc['id']);a.hp=10
        b=next(a for a in m.actors if a.id==seller['id']);b.tile=a.tile.model_copy()
        life._potion(m,b.id,r7.source_event(conn,m))
        c_id=m.world_id
        for k in range(5):r7.material(m,b.id,'wood',r7.source_event(conn,m))
    s=edit(app,s,setup)
    before=c.get(route(s)+'/economy').json()['data']['wallets']
    s=heartbeat(c,s)
    assert any(i['owner_id']==npc['id'] and i['material_id']=='healing' for i in s['items'])
    after=c.get(route(s)+'/economy').json()['data']['wallets']
    assert after[npc['id']]==before[npc['id']]-6
    s=heartbeat(c,s)
    assert next(a for a in s['actors'] if a['id']==npc['id'])['hp']==35


def test_witness_report_creates_guard_response_and_funded_bounty(game):
    c,app,s=game
    guard=next(a for a in s['actors'] if a['appearance_key'].startswith('guard_'))
    victim=first_npc(s);monster=next(a for a in s['actors'] if a['kind']=='monster')
    s=near(c,s,victim['id'],guard['tile']);s=near(c,s,monster['id'],guard['tile'])
    hit={'attack_id':uuid4().hex,'attacker_id':monster['id'],'target_id':victim['id'],'weapon_id':monster['equipped_item_id'],
        'region_id':'overworld','attacker_tile':guard['tile'],'target_tile':guard['tile']}
    s=ok(command(c,s,'HIT',hit))
    assert any(n['kind']=='incident' and guard['id'] in n['knowers'] for n in s['notices'])
    s=heartbeat(c,s)
    assert any(n.get('posted') for n in s['notices'])
    q=next(q for q in s['quests'] if q['kind']=='hunt')
    with app.state.store.connection() as conn:assert life.read(conn,s['world_id'])['quest_escrow'][q['id']]==10


def test_negotiated_fee_is_not_limited_to_example_fifty(game):
    c,app,s=game;npc=first_npc(s);s=near(c,s,s['player_id'],npc['tile'])
    s=ok(speech(c,s,npc,'我想雇佣你跟随我，酬金75金币。'))
    assert s['contracts'][0]['fee']==75 and s['contracts'][0]['status']=='pending_payment'


def test_coin_gift_is_split_from_wallet_and_cannot_overdraw(game):
    c,app,s=game;npc=first_npc(s);s=near(c,s,s['player_id'],npc['tile'])
    before=c.get(route(s)+'/economy').json()['data']['wallets']
    s=ok(post(c,s,'/interact',action='GIVE_GOLD',target_id=npc['id'],amount=5))
    after=c.get(route(s)+'/economy').json()['data']['wallets']
    assert after[s['player_id']]==7 and after[npc['id']]==before[npc['id']]+5
    assert post(c,s,'/interact',action='GIVE_GOLD',target_id=npc['id'],amount=8).json()['error']['code']=='INSUFFICIENT_FUNDS'


def test_weapon_wear_affects_damage_and_real_material_repairs_it(game):
    c,app,s=game;npc=first_npc(s);s=near(c,s,s['player_id'],npc['tile'])
    def wear(conn,m):
        next(i for i in m.items if i.id==m.actors[0].equipped_item_id).durability=10
        r7.material(m,m.player_id,'iron',r7.source_event(conn,m))
    s=edit(app,s,wear);player=s['actors'][0]
    hit={'attack_id':uuid4().hex,'attacker_id':player['id'],'target_id':npc['id'],'weapon_id':player['equipped_item_id'],
        'region_id':'overworld','attacker_tile':player['tile'],'target_tile':npc['tile']}
    s=ok(command(c,s,'HIT',hit))
    assert next(a for a in s['actors'] if a['id']==npc['id'])['hp']==npc['hp']-max(1,2-npc['armor'])
    s=ok(interact(c,s,'REPAIR',player['equipped_item_id']))
    assert next(i for i in s['items'] if i['id']==player['equipped_item_id'])['durability']==100
    assert not any(i['base_type']=='material' and i['material_id']=='iron' and i['owner_id']==player['id'] for i in s['items'])
