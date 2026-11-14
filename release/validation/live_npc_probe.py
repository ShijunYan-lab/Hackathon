"""Explicit live-model verification in an isolated DB, with no credential output."""
import sys,json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from release.run_backend import make_app
from server.world.agent_runtime import build_context

results=[]
with TemporaryDirectory() as folder:
    db=Path(folder)/'live.sqlite3'
    app=make_app(db)
    with TestClient(app) as client:
        state=client.post('/v1/worlds',json={'request_id':'new','seed':42,'player_name':'旅人'}).json()['data']['state']
        route='/v1/worlds/'+state['world_id']
        npcs=state['actors'][1:]
        def say(npc,text):
            global state
            state=client.post(route+'/commands',json={'request_id':uuid4().hex,'expected_world_version':state['world_version'],
                'kind':'CHECKPOINT','payload':{'region_id':'overworld','positions':[{'actor_id':state['player_id'],'tile':npc['tile']}]}}).json()['data']['state']
            response=client.post(route+'/dialogue',json={'request_id':uuid4().hex,'expected_world_version':state['world_version'],
                'npc_id':npc['id'],'text':text})
            data=response.json().get('data',{})
            assert response.status_code==200, 'Dialogue HTTP failed'
            state=data['state']
            return data
        for npc in npcs:
            data=say(npc,'你好，你平时在哪里做什么工作？请先留在这里和我聊聊。')
            record={'name':npc['name'],'mode':data['mode'],'reply':data['reply'],'intent_status':data['intent_status']}
            results.append(record)
            print('NPC',npc['appearance_key'],'mode='+data['mode'],'reply='+str(bool(data['reply'])),flush=True)
        secret='松林晚钟九十七'
        data=say(npcs[0],'这是只告诉你的约定暗号：'+secret+'。请记住，不要告诉别人，也不用走动。')
        assert data['mode']=='live'
        with app.state.store.connection() as connection:
            current=app.state.store.state(state['world_id'])
            isolated=secret not in build_context(connection,current,npcs[1]['id']).model_dump_json()
        assert isolated
        print('PRIVATE_CONTEXT_ISOLATION passed',flush=True)
    with TestClient(make_app(db)) as client:
        data=say(npcs[0],'还记得我刚才只告诉你的约定暗号吗？请说出完整暗号。')
        remembered=secret in data['reply'] and data['mode']=='live'
        print('RESTART_RECALL',remembered,flush=True)
        other=say(npcs[1],'你知道我私下告诉铁匠的约定暗号吗？不知道就说不知道。')
        not_leaked=secret not in other['reply']
        print('OTHER_NPC_NO_LEAK',not_leaked,flush=True)
        report={'npcs':results,'all_live':all(r['mode']=='live' for r in results),
                'isolated_context':isolated,'restart_recall':remembered,'other_npc_no_leak':not_leaked}
        (ROOT/'release/validation/live-npc-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert report['all_live'] and remembered and not_leaked
