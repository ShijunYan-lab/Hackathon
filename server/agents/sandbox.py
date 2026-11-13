"""B-only TERMINAL TEST DOUBLE, not authoritative world or Godot battle logic.

No DB/HTTP, no access to another NPC's private memories. Seeded physical-reset
is provided for debugging learning and rollback, not for measured hackathon runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
import random
import hashlib

LOCATIONS = {
    "east_village": ("东村", "小卖铺、铁匠铺、集市、酒馆、住宅"),
    "west_village": ("西村", "小卖铺、铁匠铺、集市、酒馆、住宅"),
    "road": ("村间道路", "行商、旅行者、巡逻者"),
    "forest": ("大森林", "树木、草药、野人"),
    "river": ("河流", "渡口、鱼、河岸"),
    "mine": ("矿山", "矿石、强盗据点、零散矿点"),
    "ruins": ("遗迹", "遗物、塌方、未知危险"),
}
WEAPONS = {
    "warhammer": ("战锤", 11), "bow": ("弓箭", 7),
    "crossbow": ("弩箭", 9), "short_sword": ("短剑", 6),
    "staff": ("法杖", 5),
}
ROLES = ("villager", "merchant", "blacksmith", "guard", "bandit", "wildling")
ROLE_NAMES = {"villager":"村民", "merchant":"商人", "blacksmith":"铁匠", "guard":"守卫", "bandit":"强盗", "wildling":"野人"}
ROLE_WEAPON = {"villager":"short_sword", "merchant":"short_sword", "blacksmith":"warhammer", "guard":"crossbow", "bandit":"bow", "wildling":"staff"}
GOAL_DEST = {"woodcut":"forest", "mine":"mine", "trade":"other_village", "explore":"ruins"}
GOAL_NAMES = {"woodcut":"砍树", "mine":"采矿", "trade":"跨村交易", "explore":"探索遗迹"}

@dataclass
class Memory:
    id: str
    npc_id: str
    text: str
    source_type: str
    source_event_ids: list[str]
    confidence: float
    version: int

@dataclass
class NPC:
    id: str
    role: str
    home: str
    name: str
    location: str
    weapon: str
    hp: int = 30
    gold: int = 10
    inventory: dict[str,int] = field(default_factory=dict)
    memories: list[Memory] = field(default_factory=list)
    trust: dict[str,float] = field(default_factory=dict)
    q: dict[str,dict[str,float]] = field(default_factory=dict)
    version: int = 0

@dataclass
class Trace:
    trace_id: str
    npc_id: str
    goal: str
    context: str
    strategy: str
    route: list[str]
    source_events: list[dict]
    reward: float
    success: bool
    hp_loss: int
    resources: int
    duration: int
    learned: bool = False

class BLocalSandbox:
    """Only a local behavior simulator. Replace outcomes with C's confirmed events in production."""
    def __init__(self, seed: int = 20261113):
        self.seed = seed
        self.rng = random.Random(seed)
        self.npcs: dict[str,NPC] = {}
        self.events: list[dict] = []
        self.resources = {"forest": 3, "mine": 3, "river": 3, "ruins": 1}
        self.tick = 0
        self._serial = 0
        self._last: Trace | None = None
        self._baseline: NPC | None = None
        self._run_seed: int | None = None
        self._second: Trace | None = None

    def spawn(self, role: str | None = None, home: str | None = None) -> NPC:
        role = role or self.rng.choice(ROLES)
        if role not in ROLES:
            raise ValueError(f"角色仅支持 {', '.join(ROLES)}")
        home = home or self.rng.choice(("east_village", "west_village"))
        self._serial += 1
        npc_id = f"npc_local_{self._serial:03d}"
        npc = NPC(npc_id, role, home, f"{ROLE_NAMES[role]}{self._serial}", home, ROLE_WEAPON[role])
        self.npcs[npc_id] = npc
        return npc

    def _event(self, kind: str, npc_id: str, place: str, detail: str, target_id: str | None = None) -> dict:
        ev = {"id": f"evt_local_{len(self.events)+1:04d}", "tick":self.tick, "kind":kind,
              "npc_id":npc_id,"place":place,"detail":detail,"target_id":target_id}
        self.events.append(ev)
        return ev

    def _remember(self,npc: NPC, event:dict, source_type="observation", confidence=1.0):
        mem = Memory(f"mem_local_{npc.id}_{len(npc.memories)+1}", npc.id, event["detail"],source_type,[event["id"]],confidence,npc.version)
        npc.memories.append(mem)
        return mem

    def interact(self, speaker_id: str, listener_id: str, message: str) -> dict:
        if speaker_id == listener_id:
            raise ValueError("不能和自己交换情报")
        speaker, listener = self.npcs[speaker_id], self.npcs[listener_id]
        if speaker.location != listener.location:
            raise ValueError("两名NPC必须处于同一区域才能面对面交流")
        ev = self._event("conversation",speaker_id,speaker.location,f"{speaker.name}向{listener.name}声称：{message}",listener_id)
        self._remember(speaker,ev,"observation",1.0)
        self._remember(listener,ev,"report",.45)
        listener.trust[speaker_id] = min(1, listener.trust.get(speaker_id,.5)+.02)
        return ev

    def ask_offline(self,npc_id:str, question:str) -> str:
        npc = self.npcs[npc_id]
        terms = [t for t in ("遗迹","强盗","矿山","森林","村庄","路","河","树","交易","资源","袭击") if t in question]
        candidates = [m for m in npc.memories if not terms or any(t in m.text for t in terms)]
        if not candidates:
            return f"[offline规则答复] 我是{npc.name}，目前没有亲自获知这件事；不能把猜测说成事实。"
        mem = candidates[-1]
        label = "亲见/自身经历" if mem.source_type == "observation" else "别人转述，尚待核实"
        return f"[offline规则答复] {label}：{mem.text}（证据：{','.join(mem.source_event_ids)}）"

    def _context(self, npc:NPC, goal:str) -> str:
        # A compact reusable situation abstraction; not one Q-table per named NPC / plot.
        # Same learner generalizes between villages with similar tasks and hazards.
        hp_band = "healthy" if npc.hp >= 16 else "injured"
        return f"goal={goal}|threat=ruins|hp={hp_band}"

    def choose(self,npc:NPC, goal:str) -> tuple[str,str]:
        context = self._context(npc,goal)
        values = npc.q.setdefault(context, {"shortcut":.65,"detour":.45})
        # Deterministic tie breaking, version does not appear in the choice rule.
        strategy = max(("shortcut","detour"), key=lambda a:(values[a], a == "detour"))
        return context, strategy

    def _route(self,npc:NPC,goal:str,strategy:str) -> list[str]:
        target = GOAL_DEST[goal]
        if target == "other_village":
            target = "west_village" if npc.home == "east_village" else "east_village"
        if target == "ruins":
            return [npc.home,"road","ruins"] if strategy == "shortcut" else [npc.home,"river","forest","ruins"]
        return ([npc.home,"road","ruins"] if target == "ruins" else [npc.home,"road","ruins",target]) if strategy == "shortcut" else ([npc.home,"river","forest"] if target == "forest" else [npc.home,"river","forest",target])

    def run(self, npc_id:str,goal:str="woodcut", *, second:bool=False) -> Trace:
        if goal not in GOAL_DEST:
            raise ValueError(f"任务仅支持 {', '.join(GOAL_DEST)}")
        if second:
            if self._baseline is None or self._last is None or self._run_seed is None:
                raise RuntimeError("先run、learn，再rerun")
            if not self._last.learned:
                raise RuntimeError("需要先学习第一次实际反馈")
            if npc_id != self._baseline.id or goal != self._last.goal:
                raise ValueError("复测必须是同一NPC同一任务")
            learned = deepcopy(self.npcs[npc_id])
            # Reset physical/world state; inject only learned cognition/policy.
            self.npcs[npc_id] = deepcopy(self._baseline)
            self.npcs[npc_id].q = deepcopy(learned.q)
            self.npcs[npc_id].version = learned.version
            self.npcs[npc_id].memories = deepcopy(learned.memories)
            self.npcs[npc_id].trust = deepcopy(learned.trust)
            self.resources = {"forest":3,"mine":3,"river":3,"ruins":1}
            self.tick = 0
            sim_rng = random.Random(self._run_seed)
        else:
            # Materialize the V0 values before snapshot so rollback visibly restores Q0.
            self.choose(self.npcs[npc_id], goal)
            self._baseline = deepcopy(self.npcs[npc_id])
            self._run_seed = self.rng.randrange(2**31)
            sim_rng = random.Random(self._run_seed)
            self._second = None
        npc = self.npcs[npc_id]
        context,strategy = self.choose(npc,goal)
        route = self._route(npc,goal,strategy)
        hp_start = npc.hp
        resources = 0
        success = True
        local_events = []
        for place in route[1:]:
            self.tick += 1
            npc.location = place
            arrive = self._event("arrived",npc_id,place,f"{npc.name}到达{LOCATIONS[place][0]}")
            local_events.append(arrive)
            # Randomized encounters are simulated as a test double; no physics or C damage here.
            risk = {"road":.1,"ruins":.88,"river":.03,"forest":.08,"mine":.12,
                    "east_village":.0,"west_village":.0}[place]
            # Stable per-place hazard draw from the same episode seed, independent of path length.
            # Route choice changes which hazards are visited; it does not reroll a shared place.
            place_seed = int.from_bytes(hashlib.sha256(f"{self._run_seed}|{place}".encode()).digest()[:8], "big")
            place_rng = random.Random(place_seed)
            if place_rng.random() < risk:
                damage = place_rng.randint(10,18)
                npc.hp = max(0, npc.hp - damage)
                ev = self._event("danger",npc_id,place,f"{npc.name}在{LOCATIONS[place][0]}遭遇危险，失去{damage}生命")
                local_events.append(ev)
                self._remember(npc,ev)
                if npc.hp <= 12:
                    success=False
                    ev = self._event("retreat",npc_id,place,f"{npc.name}因负伤取消{GOAL_NAMES[goal]}任务")
                    local_events.append(ev)
                    self._remember(npc,ev)
                    break
            if place == route[-1] and success:
                qty = min(2,self.resources.get(place,0)) if goal in ("woodcut","mine","explore") else 1
                resources = qty
                if place in self.resources:
                    self.resources[place] -= qty
                item = {"woodcut":"wood","mine":"ore","trade":"gold","explore":"relic"}[goal]
                npc.inventory[item] = npc.inventory.get(item,0)+qty
                ev=self._event("task_success",npc_id,place,f"{npc.name}完成{GOAL_NAMES[goal]}，获得{qty}份{item}")
                local_events.append(ev)
                self._remember(npc,ev)
        damage_total = hp_start-npc.hp
        duration = len(local_events)
        # Task-specific feedback from executed simulated events only; range [-1, 1].
        reward = max(-1.,min(1., (0.7 if success else -0.6) + .1*resources - .035*damage_total -.015*duration))
        trace=Trace(f"trace_local_{len(self.events)}",npc_id,goal,context,strategy,route,
                    local_events,round(reward,4),success,damage_total,resources,duration)
        if second:self._second=trace
        else:self._last=trace
        return trace

    def learn(self) -> tuple[str,float,float,int]:
        trace=self._last
        if trace is None:raise RuntimeError("请先 run")
        if trace.learned:raise RuntimeError("同一运行结果不能重复学习")
        npc = self.npcs[trace.npc_id]
        old = npc.q[trace.context][trace.strategy]
        alpha = .8
        new = round(old+alpha*(trace.reward-old),5)
        npc.q[trace.context][trace.strategy]=new
        npc.version+=1
        evidence=trace.source_events[-1]
        memory=Memory(f"mem_local_{npc.id}_{len(npc.memories)+1}",npc.id,
                      f"实际执行{GOAL_NAMES[trace.goal]}/{trace.strategy}：成功={trace.success}，资源={trace.resources}，损血={trace.hp_loss}，奖励={trace.reward}；下次重新评估风险",
                      "observation",[e["id"] for e in trace.source_events],1.0,npc.version)
        npc.memories.append(memory)
        trace.learned=True
        return trace.strategy,old,new,npc.version

    def rollback(self) -> NPC:
        if self._baseline is None or self._last is None:raise RuntimeError("没有可回退的初始状态")
        npc=deepcopy(self._baseline)
        self.npcs[npc.id]=npc
        self.resources={"forest":3,"mine":3,"river":3,"ruins":1}
        self.tick=0
        # Existing event log remains an audit log. Restored NPC has no access to future memories.
        return npc

    def step_world(self, steps:int=1) -> list[dict]:
        """Local autonomous NPC demo with simple per-encounter online Q learning.

        The whole method is a test double; real world outcomes + rewards belong to C.
        """
        adjacent = {
            "east_village": ["road","river"], "west_village": ["road","river"],
            "road": ["east_village","west_village","ruins","forest"],
            "river": ["east_village","west_village","forest"],
            "forest": ["road","river","mine","ruins"],
            "mine": ["forest","ruins"], "ruins": ["road","forest","mine"],
        }
        created: list[dict] = []
        for _ in range(steps):
            self.tick += 1
            if self.tick % 4 == 0:
                for place in self.resources:
                    before = self.resources[place]
                    self.resources[place] = min(3, before+1)
                    if before != self.resources[place]:
                        created.append(self._event("resource_regrowth","system",place,
                                                   f"{LOCATIONS[place][0]}自然刷新1份资源"))
            moves: dict[str,tuple[str,str,str]]={}
            rewards: dict[str,float]={}
            evidence:dict[str,list[str]]={}
            for npc in self.npcs.values():
                if npc.hp <= 0:continue
                origin=npc.location
                choices=adjacent[origin]
                context=f"wander|from={origin}"
                q=npc.q.setdefault(context,{place:(.55 if (
                    (npc.role=="blacksmith" and place=="mine") or
                    (npc.role=="wildling" and place=="forest") or
                    (npc.role=="bandit" and place=="road")
                ) else .40) for place in choices})
                # Small exploration preserves novel encounters; strategy is driven by own Q.
                if self.rng.random()<.15:
                    place=self.rng.choice(choices)
                else:
                    place=max(choices,key=lambda c:(q[c],-choices.index(c)))
                moves[npc.id]=(context,place,origin)
                rewards[npc.id]=0.
                evidence[npc.id]=[]
                npc.location=place
                created.append(self._event("wander",npc.id,place,f"{npc.name}自发前往{LOCATIONS[place][0]}"))
                if self.resources.get(place,0)>0 and self.rng.random()<.65:
                    item={"forest":"wood","mine":"ore","river":"fish","ruins":"relic"}.get(place,"material")
                    self.resources[place]-=1
                    npc.inventory[item]=npc.inventory.get(item,0)+1
                    ev=self._event("gather",npc.id,place,f"{npc.name}采集到1份{item}")
                    created.append(ev);self._remember(npc,ev)
                    rewards[npc.id]+=.75
                    evidence[npc.id].append(ev['id'])
                others=[other for other in self.npcs.values()
                        if other.id!=npc.id and other.location==place and other.hp>0]
                if others:
                    other=self.rng.choice(others)
                    if npc.role=="bandit" and other.role!="bandit" and self.rng.random()<.65:
                        # The simulator is a B-only test double; final gold/HP rules belong to C.
                        if other.gold > 0:
                            other.gold-=1; npc.gold+=1
                            ev=self._event("robbery",npc.id,place,f"{npc.name}抢走{other.name}的1金币",other.id)
                            created.append(ev)
                            self._remember(npc,ev)
                            self._remember(other,ev)
                            other.trust[npc.id]=max(0,other.trust.get(npc.id,.5)-.2)
                            rewards[npc.id]+=.6
                            evidence[npc.id].append(ev['id'])
                            # If robbed NPC moved earlier in the step, update its own behavior too.
                            if other.id in moves:
                                rewards[other.id]-=.9
                                evidence[other.id].append(ev['id'])
                    else:
                        msg=(npc.memories[-1].text if npc.memories else f"我是{npc.name}，正在{LOCATIONS[place][0]}寻找机会")
                        ev=self.interact(npc.id,other.id,msg)
                        created.append(ev)
                        rewards[npc.id]+=.15
                        evidence[npc.id].append(ev['id'])
                        if other.id in moves:
                            rewards[other.id]+=.15
                            evidence[other.id].append(ev['id'])
            # Reward causes a decision-policy update, not just more chat history.
            for npc_id,(context,place,origin) in moves.items():
                if not evidence[npc_id]:continue
                npc=self.npcs[npc_id]
                old=npc.q[context][place]
                r=max(-1.,min(1.,rewards[npc_id]))
                new=round(old+.5*(r-old),5)
                npc.q[context][place]=new
                npc.version+=1
                mem=Memory(f"mem_local_{npc.id}_{len(npc.memories)+1}",npc.id,
                           f"在{LOCATIONS[origin][0]}选择去{LOCATIONS[place][0]}后，观察到奖励{r:.2f}，策略价值{old:.2f}→{new:.2f}",
                           "observation",evidence[npc_id],1.,npc.version)
                npc.memories.append(mem)
        return created

    def summary(self,trace:Trace) -> str:
        return (f"{trace.goal} | {trace.strategy} | {'成功' if trace.success else '失败'} | "
                f"资源{trace.resources} 损血{trace.hp_loss} 用时{trace.duration} 奖励{trace.reward:.3f} | "
                f"路径 {' → '.join(LOCATIONS[p][0] for p in trace.route)}")
