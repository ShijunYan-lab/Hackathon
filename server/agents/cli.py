"""Interactive terminal testing for NPC cognition and online behavior adaptation.

Run at repository root: python -m server.agents.cli --seed 20261113
All physical outcomes are explicitly marked *local simulation*, NOT measured game results.
"""
from __future__ import annotations
import argparse
import cmd
from time import perf_counter

from .sandbox import ADJACENT, BLocalSandbox, GOAL_NAMES, LOCATIONS, SCENES, WEAPONS

class BConsole(cmd.Cmd):
    prompt = "npc-b> "
    intro = "B 智能体本地沙盒 [local simulation]。直接输入中文与当前 NPC 对话，输入 help 查看命令。"
    def __init__(self,seed:int):
        super().__init__()
        self.s = BLocalSandbox(seed, populate=True)
        p = next(iter(self.s.npcs.values()))
        self.selected=p.id
        print(f"种子={seed}，开局 {len(self.s.npcs)} 名 NPC，当前选择 {p.name}/{p.id}")

    def default(self, line):
        if any("\u3400" <= char <= "\u9fff" for char in line):
            self.do_asklive(line)
        else:
            super().default(line)

    def emptyline(self):
        """Wait for input without repeating the previous action or model call."""

    def do_world(self,arg):
        "查看地点、建筑、资源、五种武器: world"
        for k,(name,features) in LOCATIONS.items():
            scope = "主场景" if k in SCENES else "路径/子区域"
            links = "、".join(LOCATIONS[place][0] for place in ADJACENT[k])
            stock = self.s.resources.get(k, '—')
            if k in self.s.market_gold:
                stock = f"集市购入预算 {self.s.market_gold[k]} 金币"
            print(f" {name} [{scope}] {features}；资源={stock}；通往 {links}")
        print(" 武器：", ", ".join(v[0] for v in WEAPONS.values()))
    def do_spawn(self,arg):
        "创建随机 NPC，也可指定职业: spawn [villager|merchant|blacksmith|guard|bandit|wildling]"
        try:
            npc=self.s.spawn(arg.strip() or None)
            print(f"生成 {npc.id} {npc.name} 位置={LOCATIONS[npc.location][0]} 装备={WEAPONS[npc.weapon][0]}")
        except ValueError as e:print(e)
    def do_npcs(self,arg):
        "查看所有 NPC: npcs"
        for npc in self.s.npcs.values():print(f"{npc.id} {npc.name} 家={npc.residence} 当前={LOCATIONS[npc.location][0]} HP={npc.hp} 学习v{npc.version} 记忆={len(npc.memories)}")
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
            self.s.remember_dialogue(self.selected, arg, answer)
        except AgentCallFailed as e:
            print(f"[未调用成功，非live] {e}")

    def do_talk(self,arg):
        "让两名同区NPC交流传闻: talk <发送者ID> <接收者ID> <内容>"
        try:
            a,b,text=arg.split(maxsplit=2)
            ev=self.s.interact(a,b,text)
            print(f"[local simulation] {ev['id']}: {ev['detail']}（接收者记为转述）")
        except (ValueError,KeyError) as e:print("需要两个NPC ID和消息；",e)
    def do_step(self,arg):
        "自动游走、资源再生、遇人交流/抢劫（本地规则模拟）：step [回合数]"
        try:
            count=int(arg.strip() or '1')
            if count<1 or count>20:raise ValueError('回合数限定1..20')
            start = perf_counter()
            events=self.s.step_world(count)
            elapsed_ms = (perf_counter() - start) * 1000
            for ev in events[-30:]:print(f"{ev['id']} {ev['kind']}: {ev['detail']}")
            print(f"[local simulation] {len(events)} 条事件，tick={self.s.tick}，"
                  f"{elapsed_ms:.1f} ms，模型请求=0")
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
            if self.s._last and self.s._last.npc_id != self.selected:
                raise RuntimeError("请先选择实际执行上一任务的 NPC")
            strategy,old,new,version=self.s.learn()
            evidence = ", ".join(event["id"] for event in self.s._last.source_events)
            print(f"[local simulation] {strategy} Q {old:.3f} → {new:.3f}，"
                  f"v{version - 1} → v{version}，来源 {evidence}")
        except RuntimeError as e:print(e)
    def do_rerun(self,arg):
        "相同初始身体/资源/随机种子+学习后认知复测: rerun"
        try:
            if self.s._last is None:
                raise RuntimeError("请先 run，然后 learn")
            tr=self.s.run(self.selected,self.s._last.goal,second=True)
            print("[本地模拟二跑]",self.s.summary(tr))
            print("[本地模拟首跑]",self.s.summary(self.s._last))
            for event in tr.source_events:
                print(" ", event["id"], event["detail"])
            print("说明：相同地点的遭遇使用同一局种子固定；路线不同意味着经历的地点不同。这是本地测试，不是正式评审分数")
        except (ValueError,RuntimeError) as e:print(e)
    def do_memory(self,arg):
        "仅查看指定 NPC 自己的记忆：memory [npc_id]"
        npc=self.s.npcs.get(arg.strip() or self.selected)
        if not npc:print("没有该 NPC");return
        for m in npc.memories[-20:]:print(f"{m.id} v{m.version} [{m.source_type},可信度{m.confidence}] {m.text} evidence={m.source_event_ids}")
        if not npc.memories:print("（目前没有记忆）")
    def do_profile(self,arg):
        "查看当前 NPC 的目标、信念和策略：profile"
        self.do_inspect(arg)

    def do_inspect(self, arg):
        "检查角色、当前位置、合法动作和私有认知：inspect [npc_id]"
        npc = self.s.npcs.get(arg.strip() or self.selected)
        if npc is None:
            print("没有该 NPC")
            return
        actions = []
        if npc.hp > 0:
            actions.extend(("WAIT", "MOVE"))
            if self.s.resources.get(npc.location, 0):
                actions.append("GATHER")
            if any(other.id != npc.id and other.hp > 0 and other.location == npc.location
                   for other in self.s.npcs.values()):
                actions.append("SHARE_INFO")
        print(f"{npc.id} {npc.name}｜{npc.organization}｜居所 {npc.residence}｜"
              f"当前位置 {LOCATIONS[npc.location][0]}｜{WEAPONS[npc.weapon][0]}｜HP {npc.hp}｜金币 {npc.gold}")
        print(f"性格 {npc.personality}")
        print(f"目标 {GOAL_NAMES.get(npc.goal, '返回住处')}｜可行动作 {', '.join(actions) or '无'}｜"
              f"库存 {npc.inventory}")
        print(f"策略 v{npc.version} {npc.q}｜信任 {npc.trust}")
        for memory in npc.memories[-4:]:
            print(f" {memory.source_type} {memory.text} {memory.source_event_ids}")
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
