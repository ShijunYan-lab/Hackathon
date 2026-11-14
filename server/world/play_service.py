"""Transactional gameplay endpoints: shops, containers, consumables and save menu."""
import json
from shared.protocol import StateView
from server.storage.sqlite import response
from server.world.commands import WorldError
from server.world.items import living_actor, require_near
from server.world.tasks import event
from server.world import living_world as life


class PlayService:
    def __init__(self, store):
        self.store=store

    def shop(self,world_id,npc_id):
        with self.store.connection() as c:
            state=StateView.model_validate_json(self.store.world_row(c,world_id)['state'])
            return response('shop',state,life.shop_view(c,state,npc_id))

    def container(self,world_id,box_id):
        with self.store.connection() as c:
            state=StateView.model_validate_json(self.store.world_row(c,world_id)['state'])
            box=self._box(state,box_id)
            return response('container',state,self._box_view(state,box))

    @staticmethod
    def _box(state,box_id):
        box=next((v for v in state.containers if v['id']==box_id),None)
        if not box:raise WorldError('CONTAINER_NOT_FOUND','\u7bb1\u5b50\u5df2\u4e0d\u5b58\u5728\u3002',404)
        from shared.protocol import Tile
        require_near(living_actor(state,state.player_id),box['region_id'],Tile(**box['tile']),3)
        if box['kind']=='merchant':raise WorldError('MERCHANT_STOCK','\u8fd9\u662f\u5546\u4eba\u7684\u8d27\u7bb1\uff0c\u8bf7\u5148\u4e0e\u4ed6\u4ea4\u8c08\u3002')
        return box

    @staticmethod
    def _box_view(state,box):
        return {'container':box,'items':[i.model_dump(mode='json') for i in state.items if i.owner_id==box['id']]}

    def mutate(self,world_id,body,operation,target=None):
        scope=f'{world_id}/play/{operation}/{target or ""}'
        with self.store.connection(write=True) as c:
            cached=self.store.cached(c,scope,body)
            if cached is not None:return cached
            row=self.store.world_row(c,world_id)
            self.store.require_ordinary(c,world_id)
            state=StateView.model_validate_json(row['state'])
            if body.expected_world_version!=state.world_version:
                raise WorldError('VERSION_CONFLICT','\u4e16\u754c\u5df2\u66f4\u65b0\uff0c\u8bf7\u5237\u65b0\u540e\u91cd\u8bd5\u3002',409)
            player=living_actor(state,state.player_id)
            seq=c.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE world_id=?',(world_id,)).fetchone()[0]
            events=[];extra={}
            if operation=='buy':
                shop=life.shop_view(c,state,target)
                if shop['quote_id']!=body.quote_id:raise WorldError('QUOTE_EXPIRED','\u62a5\u4ef7\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u67e5\u770b\u8d27\u7269\u3002',409)
                listing=next((i for i in shop['stock'] if i['item']['id']==body.item_id),None)
                if not listing:raise WorldError('ITEM_SOLD','\u8fd9\u4ef6\u7269\u54c1\u5df2\u7ecf\u4e0d\u5728\u8d27\u67b6\u4e0a\u3002',409)
                if shop['gold']<listing['price']:raise WorldError('INSUFFICIENT_FUNDS','\u91d1\u5e01\u4e0d\u8db3\u3002')
                item=next(i for i in state.items if i.id==body.item_id)
                item.owner_id=player.id
                c.execute('UPDATE wallets SET gold=gold-? WHERE world_id=? AND actor_id=?',(listing['price'],world_id,player.id))
                c.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(listing['price'],world_id,target))
                events=[event(state,'shop_purchase',seq,player.id,target,{'item_id':item.id,'item_name':item.name,'price':listing['price'],'discount_percent':shop['discount_percent']},item.origin_event_ids,[player.id,target])]
                meta=life.read(c,world_id)
                life._change_relation(meta,target,player.id,2,-1,events[0].id);life.write(c,world_id,meta)
                extra['shop']=life.shop_view(c,state,target)
            elif operation=='take':
                box=self._box(state,target)
                if body.item_id is None and not body.take_gold:
                    raise WorldError('EMPTY_REQUEST','\u8bf7\u9009\u62e9\u7269\u54c1\u6216\u91d1\u5e01\u3002')
                if body.item_id is not None:
                    item=next((i for i in state.items if i.id==body.item_id and i.owner_id==box['id']),None)
                    if item is None:raise WorldError('ITEM_NOT_FOUND','\u7269\u54c1\u5df2\u88ab\u53d6\u8d70\u3002',409)
                    item.owner_id=player.id
                    events.append(event(state,'container_item_taken',seq,player.id,None,{'container_id':box['id'],'item_id':item.id,'item_name':item.name},item.origin_event_ids,[player.id]))
                if body.take_gold:
                    gold=int(box.get('gold',0))
                    if gold<=0 and not events:raise WorldError('EMPTY_CONTAINER','\u7bb1\u5b50\u91cc\u5df2\u6ca1\u6709\u91d1\u5e01\u3002')
                    box['gold']=0
                    c.execute('UPDATE wallets SET gold=gold+? WHERE world_id=? AND actor_id=?',(gold,world_id,player.id))
                    events.append(event(state,'gold_collected',seq+len(events),player.id,None,{'container_id':box['id'],'amount':gold},[],[player.id]))
                box['opened']=True
                extra.update(self._box_view(state,box))
            elif operation=='use':
                item=next((i for i in state.items if i.id==body.item_id and i.owner_id==player.id),None)
                if item is None:raise WorldError('ITEM_NOT_OWNED','\u80cc\u5305\u4e2d\u6ca1\u6709\u8fd9\u4ef6\u7269\u54c1\u3002')
                if item.base_type!='consumable' or item.material_id not in ('healing','herb'):
                    raise WorldError('NOT_CONSUMABLE','\u8fd9\u4ef6\u7269\u54c1\u4e0d\u80fd\u4f5c\u4e3a\u836f\u5242\u4f7f\u7528\u3002')
                if player.hp==player.max_hp:raise WorldError('ALREADY_HEALTHY','\u4f60\u7684\u751f\u547d\u503c\u5df2\u6ee1\u3002')
                healed=min(25,player.max_hp-player.hp);player.hp+=healed
                state.items=[i for i in state.items if i.id!=item.id]
                events=[event(state,'item_consumed',seq,player.id,None,{'item_id':item.id,'healed':healed},item.origin_event_ids,[player.id])]
            elif operation=='accept_quest':
                events=life.accept_quest(c,state,body.quest_id,seq)
            else:raise WorldError('ACTION_NOT_SUPPORTED','Unsupported play action')
            life.on_events(c,state,events,json.loads(row['region']))
            state.world_version+=1
            c.execute('UPDATE worlds SET state=? WHERE id=?',(state.model_dump_json(),world_id))
            for e in events:self.store.append_event(c,world_id,e)
            result=response(body.request_id,state,{'state':state.model_dump(mode='json'),'events':[e.model_dump(mode='json') for e in events],**extra})
            self.store.remember(c,scope,body,result)
            return result

    def journal(self,world_id,after_seq=0,limit=50):
        with self.store.connection() as c:
            state=StateView.model_validate_json(self.store.world_row(c,world_id)['state'])
            data=life.journal(c,state,after_seq,limit)
            from server.world import chronicle
            data['chapters']=chronicle.read(c,world_id,0,20,latest=True)
            return response('journal',state,data)

    def saves(self):
        with self.store.connection() as c:
            result=[]
            for row in c.execute('SELECT id,label,body FROM saves ORDER BY rowid DESC LIMIT 40'):
                data=json.loads(row['body']);state=json.loads(data['world']['state'])
                player=next(a for a in state['actors'] if a['id']==state['player_id'])
                result.append({'save_id':row['id'],'label':row['label'],'player_name':player['name'],
                               'tick':state['tick'],'appearance':state.get('appearance','male')})
            return {'saves':result}
