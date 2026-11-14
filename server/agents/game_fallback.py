"""Explicit offline fallback, not an LLM. No promises of arbitrary language understanding."""
from shared.protocol import AgentDecision, Intent


def dialogue(context,text):
    candidates=context.identity.get('action_candidates',[])
    def choose(action):
        return next((c for c in candidates if c.get('action')==action),None)
    signal='neutral'
    if any(s in text for s in ('\u5783\u573e','\u5e9f\u7269','\u80c6\u5c0f\u9b3c','\u8822\u8d27')):signal='insult'
    elif any(s in text for s in ('\u6740\u4e86\u4f60','\u6253\u6b7b\u4f60')):signal='threat'
    elif any(s in text for s in ('\u5bf9\u4e0d\u8d77','\u62b1\u6b49','\u9053\u6b49')):signal='apology'
    elif '\u8c22' in text:signal='thanks'
    intent=Intent(action='WAIT')
    reply='\u6211\u6b64\u523b\u53ea\u80fd\u7b80\u5355\u4ea4\u8c08\u3002\u53ef\u4ee5\u95ee\u6211\u7684\u540d\u5b57\u3001\u8d27\u7269\u6216\u6709\u6ca1\u6709\u9700\u8981\u5e2e\u5fd9\u7684\u4e8b\u3002'
    priorities=[('GUIDE_HOME',('\u56de\u53bb','\u56de\u5bb6','\u5e26\u8def','\u8ddf\u6211')),
      ('ACCEPT_QUEST',('\u6211\u63a5','\u6211\u6765\u9001','\u4ea4\u7ed9\u6211','\u6211\u5e2e\u4f60')),
      ('BARGAIN',('\u6253\u6298','\u4fbf\u5b9c','\u4f18\u60e0','\u8bae\u4ef7')),
      ('OPEN_TRADE',('\u4e70','\u4e1c\u897f','\u8d27\u7269','\u5546\u54c1','\u4ea4\u6613')),
      ('ASK_WORK',('\u5e2e\u5fd9','\u59d4\u6258','\u4efb\u52a1','\u9700\u8981'))]
    for action,words in priorities:
        if any(word in text for word in words) and choose(action):
            c=choose(action);intent=Intent(action=c['action'],target_id=c.get('target_id'),params=c.get('params',{}))
            reply={'OPEN_TRADE':'\u53ef\u4ee5\uff0c\u5148\u770b\u770b\u8d27\u7269\u3002','BARGAIN':'\u6211\u4f1a\u6839\u636e\u6211\u4eec\u7684\u5f80\u6765\u6838\u5bf9\u62a5\u4ef7\u3002',
                'ASK_WORK':'\u6211\u8bf4\u8bf4\u773c\u4e0b\u7684\u96be\u5904\u3002','ACCEPT_QUEST':'\u8bf7\u5e2e\u6211\u5b8c\u6210\u8fd9\u4ef6\u6258\u4ed8\u3002','GUIDE_HOME':'\u591a\u8c22\u6307\u8def\uff0c\u6211\u8fd9\u5c31\u5f80\u56de\u8d70\u3002'}[action]
            break
    if any(s in text for s in ('\u540d\u5b57','\u4f60\u53eb','\u4f60\u662f\u8c01')):
        reply='\u6211\u53eb'+str(context.identity.get('name','\u65c5\u4eba'))+'\u3002\u6211\u662f'+str(context.identity.get('role','\u65c5\u4eba'))+'\u3002'
    if signal in ('insult','threat'):
        intent=Intent(action='WAIT');reply='\u8bf7\u6536\u56de\u8fd9\u53e5\u8bdd\u3002\u6211\u4f1a\u8bb0\u4f4f\u4f60\u5982\u4f55\u5bf9\u6211\u3002'
    return AgentDecision(reply=reply,intent=intent,social_signal=signal,reason_summary='Explicit offline rule fallback')
