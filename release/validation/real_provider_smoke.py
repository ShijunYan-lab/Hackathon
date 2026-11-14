"""Exercise installed B via C in an isolated DB; never print provider config."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from release.run_backend import make_app
with TemporaryDirectory() as folder, TestClient(make_app(Path(folder)/'smoke.sqlite3')) as client:
    state=client.post('/v1/worlds',json={'request_id':'new','seed':42,'player_name':'旅人'}).json()['data']['state']
    npc=state['actors'][1]
    response=client.post(f"/v1/worlds/{state['world_id']}/commands",json={'request_id':'near',
        'expected_world_version':state['world_version'],'kind':'CHECKPOINT','payload':{'region_id':'overworld',
        'positions':[{'actor_id':state['player_id'],'tile':npc['tile']}]}})
    state=response.json()['data']['state']
    response=client.post(f"/v1/worlds/{state['world_id']}/dialogue",json={'request_id':'talk',
        'expected_world_version':state['world_version'],'npc_id':npc['id'],'text':'你好，你是做什么工作的？'})
    data=response.json().get('data',{})
    print('REAL_B_PROVIDER',response.status_code,'mode='+str(data.get('mode')),'reply_present='+str(bool(data.get('reply'))))
    assert response.status_code==200 and data.get('reply')
