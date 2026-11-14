"""Transparent offline intent recognition; the live provider remains primary."""
from shared.protocol import Intent
import re

def adapt(context,text,intent,reply):
    choices=context.identity.get('action_candidates',[])
    def choose(action,predicate=lambda c:True):
        return next((c for c in choices if c['action']==action and predicate(c)),None)
    action=None
    if any(w in text for w in ('离队','解雇','不用跟','结束同行')):action='DISMISS'
    elif any(w in text for w in ('支付','付钱','给你50','给你 50','同意付')) and choose('PAY_HIRE'):action='PAY_HIRE'
    elif any(w in text for w in ('雇佣','同行','跟随我','跟着我','加入我的队伍','保护我')):
        action='HIRE'
    elif any(w in text for w in ('送给谁','收件人','送到哪','叫什么','在哪','去哪里')) and choose('QUEST_INFO'):action='QUEST_INFO'
    elif any(w in text for w in ('帮你送','送货','如何原谅','怎么原谅','和解')) and choose('PROPOSE_DELIVERY') and not choose('ACCEPT_QUEST'):action='PROPOSE_DELIVERY'
    elif any(w in text for w in ('出了什么事','消息','袭击','通缉','发生什么')) and choose('SHARE_NEWS'):action='SHARE_NEWS'
    elif any(w in text for w in ('卖','交易')):action='OPEN_TRADE'
    if action:
        fee=0
        if action=='HIRE':
            match=re.search(r'(\d{1,4})\s*(?:枚|个)?\s*金币',text)
            fee=int(match.group(1)) if match else 0
        c=choose(action,lambda c:action!='HIRE' or c.get('params',{}).get('fee')==fee)
        if c:return Intent(action=action,target_id=c.get('target_id'),params=c.get('params',{})), '让我确认一下实际约定与情况。'
    return intent,reply
