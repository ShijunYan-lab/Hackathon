import json
from uuid import uuid4
from fastapi.testclient import TestClient
from shared.protocol import AgentDecision
from release.run_backend import make_app
from server.main import create_app
from server.world.agent_runtime import build_context

def new(client):
    return client.post('/v1/worlds',json={'request_id':uuid4().hex,'seed':42,'player_name':'旅人'}).json()['data']['state']
def cmd(client,state,kind,payload):
    return client.post(f"/v1/worlds/{state['world_id']}/commands",json={'request_id':uuid4().hex,
        'expected_world_version':state['world_version'],'kind':kind,'payload':payload})
def near(client,state,npc):
    return cmd(client,state,'CHECKPOINT',{'region_id':state['current_region_id'],
        'positions':[{'actor_id':state['player_id'],'tile':npc['tile']}]}).json()['data']['state']

def test_full_dialogue_is_private_durable_and_snapshot_scoped(tmp_path):
    db=tmp_path/'memory.sqlite3'
    captured=[]
    async def respond(context,text):
        captured.append(context)
        return AgentDecision(reply='我会记住这个约定。',intent={'action':'WAIT'})
    app=create_app(db,dialogue_provider=respond)
    with TestClient(app) as client:
        state=new(client)
        a,b=state['actors'][1:3]
        state=near(client,state,a)
        route=f"/v1/worlds/{state['world_id']}"
        result=client.post(route+'/dialogue',json={'request_id':'private-talk',
            'expected_world_version':state['world_version'],'npc_id':a['id'],'text':'只告诉你：约定暗号是松林晚钟。'}).json()
        assert result['ok']
        state=result['data']['state']
        with app.state.store.connection() as connection:
            current=app.state.store.state(state['world_id'])
            private=build_context(connection,current,a['id']).model_dump_json()
            other=build_context(connection,current,b['id']).model_dump_json()
        assert '松林晚钟' in private and '我会记住' in private
        assert '松林晚钟' not in other and '我会记住' not in other
        saved=client.post(route+'/saves',json={'request_id':'save','expected_world_version':state['world_version'],'label':'memory'}).json()
        save_id=saved['data']['save_id']
    with TestClient(create_app(db,dialogue_provider=respond)) as client:
        history=client.get(route+f"/dialogue/{a['id']}/history").json()['data']['turns']
        assert history[0]['player'].endswith('松林晚钟。') and history[0]['npc']=='我会记住这个约定。'
        branch=client.post('/v1/saves/'+save_id+'/load',json={'request_id':'branch'}).json()['data']['state']
        branch_route='/v1/worlds/'+branch['world_id']
        assert client.get(branch_route+f"/dialogue/{a['id']}/history").json()['data']['turns']==history
        branch=near(client,branch,a)
        client.post(branch_route+'/dialogue',json={'request_id':'branch-talk','expected_world_version':branch['world_version'],
            'npc_id':a['id'],'text':'这条新约定只属于分支。'})
        assert len(client.get(route+f"/dialogue/{a['id']}/history").json()['data']['turns'])==1

def test_hit_protests_schedules_defense_and_rejects_fake_success(tmp_path):
    app=make_app(tmp_path/'combat.sqlite3')
    with TestClient(app) as client:
        state=new(client); player,npc=state['actors'][:2]
        result=cmd(client,state,'HIT',{'attack_id':'first','attacker_id':player['id'],'target_id':npc['id'],
            'weapon_id':player['equipped_item_id'],'region_id':'overworld',
            'attacker_tile':{'x':120.5,'y':143.5},'target_tile':{'x':121.5,'y':143.5}}).json()
        assert result['ok']
        state=result['data']['state']
        assert any(event['type']=='npc_protested' for event in result['data']['events'])
        task=next(task for task in state['tasks'] if task['kind']=='ATTACK')
        assert task['actor_id']==npc['id'] and task['target_id']==player['id']
        report={'task_id':task['id'],'actor_id':npc['id'],'status':'succeeded','region_id':'overworld','tile':{'x':121.5,'y':143.5}}
        assert cmd(client,state,'TASK_REPORT',report).json()['error']['code']=='PRECONDITION_FAILED'
        report.update(status='failed',failure_code='self_defense_ended')
        result=cmd(client,state,'TASK_REPORT',report).json()
        assert result['ok']
        assert any(task['kind']=='MOVE' and task['actor_id']==npc['id'] for task in result['data']['state']['tasks'])

def test_frozen_session_can_find_ordinary_world_without_mutating_evaluation(tmp_path):
    with TestClient(make_app(tmp_path/'frozen.sqlite3')) as client:
        ordinary=new(client)
        evaluation=client.post('/v1/evaluations',json={'request_id':'create-eval','seed':42}).json()['data']
        frozen=client.get('/v1/worlds/'+evaluation['state']['world_id']+'/state').json()['data']
        assert frozen['evaluation_active'] is True
        assert frozen['recovery_world_id']==ordinary['world_id']
        assert frozen['state']==evaluation['state']

def test_existing_spawn_cluster_repairs_once_without_reviving_dead_npc(tmp_path):
    db=tmp_path/'legacy.sqlite3'
    app=make_app(db)
    with TestClient(app) as client:
        state=new(client)
        model=app.state.store.state(state['world_id'])
        for actor in model.actors[1:]: actor.tile=model.actors[0].tile.model_copy()
        model.actors[-1]=model.actors[-1].model_copy(update={'alive':False,'hp':0})
        with app.state.store.connection(write=True) as connection:
            region=json.loads(app.state.store.world_row(connection,state['world_id'])['region'])
            region.pop('reactive_npcs',None)
            connection.execute('UPDATE worlds SET state=?,region=? WHERE id=?',(model.model_dump_json(),json.dumps(region),model.world_id))
    with TestClient(make_app(db)) as client:
        repaired=client.get('/v1/worlds/'+state['world_id']+'/state').json()['data']['state']
        assert not repaired['actors'][-1]['alive']
        assert len({(a['tile']['x'],a['tile']['y']) for a in repaired['actors'][1:-1]})==14
    with TestClient(make_app(db)) as client:
        assert client.get('/v1/worlds/'+state['world_id']+'/state').json()['data']['state']==repaired


def test_authored_npc_gets_visible_reachable_action_candidates(tmp_path):
    app=make_app(tmp_path/'candidates.sqlite3')
    with TestClient(app) as client:
        state=new(client)
        npc=state['actors'][1]
        positioned=cmd(client,state,'CHECKPOINT',{'region_id':'overworld','positions':[
            {'actor_id':state['player_id'],'tile':{'x':120.5,'y':143.5}},
            {'actor_id':npc['id'],'tile':{'x':122.5,'y':143.5}}]}).json()['data']['state']
        with app.state.store.connection() as connection:
            context=build_context(connection,app.state.store.state(state['world_id']),npc['id'])
        candidates=context.identity['action_candidates']
        assert any(c['action']=='MOVE' and c['target_id']==state['player_id'] and c['params']=={} for c in candidates)
        assert all(c['target_id'] in {v['id'] for v in context.known_entities} for c in candidates)
        assert not any(c['target_id']==state['actors'][-1]['id'] for c in candidates)
