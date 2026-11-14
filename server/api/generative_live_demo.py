"""Replayable real-LLM scenario. Godot, not this runner, reports task completion."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4
import httpx

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', default='http://127.0.0.1:8781')
    parser.add_argument('--godot', required=True)
    args = parser.parse_args()
    client = httpx.Client(base_url=args.server, timeout=90, trust_env=False)
    report = {'server': args.server, 'dialogues': [], 'checkpoints_are_demo_staging': True,
              'task_execution': 'Godot client', 'model': 'real configured provider'}
    def call(path, body=None):
        request = {'request_id': uuid4().hex, **body} if body is not None else None
        # Reuse the request identifier after uncertain transport failures.
        for attempt in range(3):
            try:
                response = (client.post(path, json=request) if request is not None else client.get(path)).json()
                break
            except httpx.TransportError:
                if attempt == 2: raise
        if not response['ok']: raise RuntimeError(str(response['error']))
        return response['data']
    state = call('/v1/worlds', {'seed':173, 'player_name':'生成式旅人'})['state']
    path = '/v1/worlds/' + state['world_id']
    npc = state['actors'][1]
    report.update(world_id=state['world_id'], npc_id=npc['id'])
    def current(): return call(path+'/state')['state']
    def write(route, data):
        for attempt in range(3):
            try:
                return call(path+route, {'expected_world_version':current()['world_version'], **data})
            except RuntimeError as exc:
                # A confirmed rejection committed no mutation. Refresh and propose again.
                if 'VERSION_CONFLICT' not in str(exc) or attempt==2: raise
                time.sleep(1)
    write('/commands', {'kind':'CHECKPOINT','payload':{'region_id':'overworld','positions':[
        {'actor_id':npc['id'],'tile':{'x':89.5,'y':96.5}},
        {'actor_id':state['player_id'],'tile':{'x':90.5,'y':96.5}}]}})
    subprocess.Popen([args.godot,'--path',str(ROOT/'game'),'--script',str(ROOT/'server/api/generative_demo.gd'),
        '--','--no-autostart','--fresh','--manual-world-turns','--server='+args.server,'--world='+state['world_id']],cwd=ROOT)
    def talk(text):
        result = write('/dialogue', {'npc_id':npc['id'],'text':text})
        report['dialogues'].append({'player':text, **{k:result[k] for k in ('reply','mode','intent_status')}})
        print(result['reply'], flush=True)
        if result['mode'] != 'live' or result['intent_status']=='rejected':
            raise RuntimeError('Live model unavailable or proposal rejected; inspect report and retry interactively.')
        return result
    def gather():
        result=talk('请你本人现在采集脚边的木材，我在这里等你。请实际行动，不是让我采。')
        if not result['task_ids']: raise RuntimeError('NPC did not choose to gather; continue the conversation in game.')
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            tasks=[t for t in current()['tasks'] if t['id'] in result['task_ids']]
            if tasks and all(t['status']=='succeeded' for t in tasks): return
            if any(t['status']=='failed' for t in tasks): raise RuntimeError('Godot task failed')
            time.sleep(.5)
        raise RuntimeError('Godot did not complete the gathering task')
    def buy():
        economy=call(path+'/economy')
        if not any(o['status']=='pending' and o['actor_id']==npc['id'] for o in economy['offers']):
            talk('我同意你刚才提出的设计，请现在实际制作并建立报价，完成后我接受报价付款。')
            economy=call(path+'/economy')
        offer=next(o for o in economy['offers'] if o['status']=='pending' and o['actor_id']==npc['id'])
        result=write('/commands',{'kind':'ACCEPT_OFFER','payload':{'actor_id':state['player_id'],'offer_id':offer['id']}})
        item=next(i for i in result['state']['items'] if i['id']==offer['item_id'])
        assert item['owner_id']==state['player_id']
        balance=call(path+'/economy')['wallets'][state['player_id']]
        assert balance==economy['wallets'][state['player_id']]-offer['price']
        return {'item':item,'price':offer['price'],'balance':balance}
    try:
        gather()
        talk('请用你采到的木料实际制作一件简朴的松枝纹样旅途纪念物，并向我报价。名称由你设计。')
        report['first']=buy()
        report['before_feedback_save']=write('/saves',{'label':'反馈前'})
        talk('我已买到作品。我的体验是体积太大；我喜欢拇指大小、月牙图案、便于携带的小物。请提炼并记住这次购买后的经验，预算三金币。')
        gather()
        talk('请根据我上次购买后的反馈，实际制作第二件纪念物并报价，说明采用了哪些经验。')
        report['second']=buy()
        report['after_feedback_save']=write('/saves',{'label':'反馈后'})
        report['advance']=write('/advance',{'reason':'rest'})
        report['story']=call(path+'/story')
        restored=call('/v1/saves/'+report['before_feedback_save']['save_id']+'/load',{})['state']
        assert any(i['id']==report['first']['item']['id'] for i in restored['items'])
        assert not any(i['id']==report['second']['item']['id'] for i in restored['items'])
        restored_balance=call('/v1/worlds/'+restored['world_id']+'/economy')['wallets'][restored['player_id']]
        assert restored_balance==report['first']['balance']
        report['restored_baseline_world']=restored['world_id']
        report['success']=True
        (ROOT/'runtime/generative-session.json').write_text(json.dumps(
            {'world_id':state['world_id'],'npc_id':npc['id']},ensure_ascii=False),encoding='utf-8')
    finally:
        target=ROOT/'runtime/generative-live-report.json'
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Report:', target)

if __name__=='__main__': main()
