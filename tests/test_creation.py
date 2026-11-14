from fastapi.testclient import TestClient
from server.main import create_app
from shared.protocol import AgentDecision, ItemState, ItemStats
from tests.test_live_npc_integration import new, near


def test_creation_dialogue_payment_and_rejection(tmp_path):
    async def respond(context, text):
        return AgentDecision(reply='我可以加工一件木雕。', creation_proposal={
            'name': text, 'description': '以现有木料雕刻的小物件，没有特殊效果。',
            'ingredient_ids': ['wood_input'], 'source_event_ids': [context.known_events[-1].id], 'price': 3})
    app = create_app(tmp_path/'creation.sqlite3', dialogue_provider=respond)
    with TestClient(app) as c:
        s = new(c); npc = s['actors'][1]; s = near(c,s,npc)
        route = '/v1/worlds/'+s['world_id']
        with app.state.store.connection(write=True) as conn:
            model = app.state.store.state(s['world_id'])
            source = conn.execute('select id from events where world_id=? order by seq limit 1',(s['world_id'],)).fetchone()[0]
            model.items.append(ItemState(id='wood_input', name='木料', base_type='material',material_id='wood',quality='common',owner_id=npc['id'],origin_event_ids=[source],stats=ItemStats(damage=0,armor=0,cooldown_s=1)))
            conn.execute('update worlds set state=? where id=?',(model.model_dump_json(),model.world_id))
        body={'request_id':'create','expected_world_version':s['world_version'],'npc_id':npc['id'],'text':'为旅途雕刻的松枝纪念物'}
        r=c.post(route+'/dialogue',json=body).json(); assert r['ok'],r
        assert r['data']['intent_status'] != 'rejected',r
        assert c.post(route+'/dialogue',json=body).json()==r
        s=r['data']['state']; item=next(i for i in s['items'] if i['name']==body['text'])
        assert item['owner_id']==npc['id'] and not any(i['id']=='wood_input' for i in s['items'])
        econ=c.get(route+'/economy').json()['data']; offer=econ['offers'][0]
        pay={'request_id':'pay','expected_world_version':s['world_version'],'kind':'ACCEPT_OFFER','payload':{'actor_id':s['player_id'],'offer_id':offer['id']}}
        paid=c.post(route+'/commands',json=pay).json(); assert paid['ok'],paid
        assert c.post(route+'/commands',json=pay).json()==paid
        s=paid['data']['state']; assert next(i for i in s['items'] if i['id']==item['id'])['owner_id']==s['player_id']
        assert c.get(route+'/economy').json()['data']['wallets'][s['player_id']]==econ['wallets'][s['player_id']]-3
        body.update(request_id='no-material',expected_world_version=s['world_version'])
        rejected=c.post(route+'/dialogue',json=body).json()
        assert rejected['data']['intent_status']=='rejected'
        assert rejected['data']['state']['items']==s['items']
