"""Interactive terminal testing for NPC cognition and online behavior adaptation.

Run at repository root: python -m server.agents.cli --seed 20261113
All physical outcomes are explicitly marked *local simulation*, NOT measured game results.
"""
from __future__ import annotations
import argparse, cmd, shlex
from .sandbox import BLocalSandbox, LOCATIONS, ROLE_NAMES, WEAPONS

class BConsole(cmd.Cmd):
    prompt = "npc-b> "
    intro = "B 智能体本地测试沙盒（规则模拟，不是真实 Godot 世界/比赛成绩）。输入 help 查看命令。"
    def __init__(self,seed:int):
        super().__init__()
        self.s = BLocalSandbox(seed)
        p=self.s.spawn("villager")
        self.selected=p.id
        print(f"种子={seed}，随机降生示例：{p.name}/{p.id}，家={LOCATIONS[p.home][0]}")
    def do_world(self,arg):
        "查看地点、建筑、资源、五种武器: world"
        for k,(name,features) in LOCATIONS.items():print(f" {k:14} {name}：{features} 资源={self.s.resources.get(k,'--')}")
        print(" 武器：", ", ".join(v[0] for v in WEAPONS.values()))
    def do_spawn(self,arg):
        "创建随机 NPC，也可指定职业: spawn [villager|merchant|blacksmith|guard|bandit|wildling]"
        try:
            npc=self.s.spawn(arg.strip() or None)
            print(f"生成 {npc.id} {npc.name} 位置={LOCATIONS[npc.location][0]} 装备={WEAPONS[npc.weapon][0]}")
        except ValueError as e:print(e)
    def do_npcs(self,arg):
        "查看所有 NPC: npcs"
        for npc in self.s.npcs.values():print(f"{npc.id} {npc.name} role={npc.role} 家={LOCATIONS[npc.home][0]} 当前={LOCATIONS[npc.location][0]} HP={npc.hp} 学习v{npc.version} 记忆={len(npc.memories)}")
    def do_select(self,arg):
        "选择当前测试 NPC: select npc_local_001"
        if arg in self.s.npcs:
            self.selected=arg;print("当前NPC：",arg)
        else:print("不存在该 NPC ID")
    def do_ask(self,arg):
        "询问当前NPC（离线规则答复，不调用大模型）: ask 你知道遗迹里有什么？"
        if not arg.strip():print("请输入问题");return
        print(self.s.ask_offline(self.selected,arg))
    def do_asklive(self,arg):
        "用本地.env中的API进行真正NPC中文自由对话: asklive <问题>"
        if not arg.strip():print('请输入问题');return
        from .provider import ask_live,AgentCallFailed
        try:
            answer,model=ask_live(self.s.npcs[self.selected],arg)
            print(f"[live模型={model}] {answer}")
        except AgentCallFailed as e:
            print(f"[未调用成功，非live] {e}")

    def do_talk(self,arg):
        "让两名同区NPC交流传闻: talk <发送者ID> <接收者ID> <内容>"
        try:
            a,b,text=arg.split(maxsplit=2)
            ev=self.s.interact(a,b,text)
            print(f"{ev['id']}: {ev['detail']}（接收者标记report，不当事实）")
        except (ValueError,KeyError) as e:print("需要两个NPC ID和消息；",e)
    def do_step(self,arg):
        "自动游走、资源再生、遇人交流/抢劫（本地规则模拟）：step [回合数]"
        try:
            count=int(arg.strip() or '1')
            if count<1 or count>20:raise ValueError('回合数限定1..20')
            events=self.s.step_world(count)
            for ev in events[-30:]:print(f"{ev['id']} {ev['kind']}: {ev['detail']}")
            print(f"本次产生{len(events)}条本地模拟事件；tick={self.s.tick}；C尚未进行权威结算")
        except ValueError as e:print(e)

    def do_run(self,arg):
        "第一次执行任务（woodcut/mine/trade/explore）: run woodcut"
        goal=arg.strip() or "woodcut"
        try:
            tr=self.s.run(self.selected,goal)
            print("[本地模拟首跑]",self.s.summary(tr))
            for ev in tr.source_events:print(" ",ev['id'],ev['detail'])
            print("后续使用 learn 根据实际模拟结果学习（不是手改Q值）")
        except (ValueError,RuntimeError) as e:print(e)
    def do_learn(self,arg):
        "使用上一轮实际运行事件更新已执行策略: learn"
        try:
            strategy,old,new,version=self.s.learn()
            print(f"自学习 {strategy}: Q {old:.3f} → {new:.3f} 版本 v{version}，来源与记忆已记录")
        except RuntimeError as e:print(e)
    def do_rerun(self,arg):
        "相同初始身体/资源/随机种子+学习后认知复测: rerun"
        try:
            tr=self.s.run(self.selected,self.s._last.goal,second=True)
            print("[本地模拟二跑]",self.s.summary(tr))
            print("[本地模拟首跑]",self.s.summary(self.s._last))
            print("说明：相同地点的遭遇使用同一局种子固定；路线不同意味着经历的地点不同。这是本地测试，不是正式评审分数")
        except (ValueError,RuntimeError) as e:print(e)
    def do_memory(self,arg):
        "仅查看指定 NPC 自己的记忆：memory [npc_id]"
        npc=self.s.npcs.get(arg.strip() or self.selected)
        if not npc:print("没有该 NPC");return
        for m in npc.memories[-20:]:print(f"{m.id} v{m.version} [{m.source_type},可信度{m.confidence}] {m.text} evidence={m.source_event_ids}")
        if not npc.memories:print("（目前没有记忆）")
    def do_profile(self,arg):
        "查看当前 NPC 的可学习策略：profile"
        npc=self.s.npcs[self.selected]
        print(npc.id,"version",npc.version,"Q:",npc.q,"信任关系:",npc.trust)
    def do_events(self,arg):
        "查看最近事件（仅调试日志；NPC不会自动看到全体事件）: events"
        for ev in self.s.events[-20:]:print(ev)
    def do_rollback(self,arg):
        "回退学习前策略/记忆以及物理场景：rollback"
        try:
            npc=self.s.rollback();print(f"已恢复 {npc.id} v{npc.version}；审计事件仍保留，未来经验不可检索")
        except RuntimeError as e:print(e)
    def do_exit(self,arg):return True
    def do_EOF(self,arg):print();return True

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--seed",type=int,default=20261113)
    args=parser.parse_args()
    BConsole(args.seed).cmdloop()
