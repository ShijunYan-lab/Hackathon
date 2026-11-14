"""B-only TERMINAL TEST DOUBLE, not authoritative world or Godot battle logic.

No DB/HTTP, no access to another NPC's private memories. Seeded physical-reset
is provided for debugging learning and rollback, not for measured hackathon runs.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from copy import deepcopy
from collections import deque
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
SCENES = {
    "east_village": ("villager", "merchant", "guard", "blacksmith"),
    "west_village": ("merchant", "villager", "blacksmith", "guard"),
    "forest": ("wildling", "villager", "guard", "bandit"),
    "ruins": ("bandit", "guard", "blacksmith", "wildling"),
}
ADJACENT = {
    "east_village": ("road", "river"), "west_village": ("road", "river"),
    "road": ("east_village", "west_village", "ruins", "forest"),
    "river": ("east_village", "west_village", "forest"),
    "forest": ("road", "river", "mine", "ruins"),
    "mine": ("forest", "ruins"), "ruins": ("road", "forest", "mine"),
}
CAPACITY = {"forest": 3, "mine": 3, "river": 3, "ruins": 1}
ITEMS = {"woodcut": "wood", "mine": "ore", "trade": "gold", "explore": "relic"}
ROLE_GOAL = dict(zip(ROLES, ("woodcut", "trade", "mine", "explore", "trade", "woodcut")))
PERSONALITIES = (
    "谨慎克制，会先周旋，受到威胁时优先寻找退路",
    "嘴硬好胜，被挑衅时容易回嘴，遇危险敢于防卫",
    "随和但有原则，愿意先听对方解释",
    "冷淡务实，遇到无理挑衅会划清界线",
)
BACKGROUND = {
    "villager": "为屋顶备过一捆木料",
    "merchant": "曾在落雨前把一批货收回屋内",
    "blacksmith": "曾修好一把断柄的锤子",
    "guard": "巡夜时听见风吹松动的窗板",
    "bandit": "曾在夜里丢失一袋干粮",
    "wildling": "曾在雨后辨认出野兽留下的脚印",
}


def path_between(start: str, end: str, *, avoid_ruins: bool = False) -> list[str]:
    queue = deque([[start]])
    visited = {start}
    while queue:
        path = queue.popleft()
        if path[-1] == end:
            return path
        for neighbor in ADJACENT[path[-1]]:
            if neighbor in visited or (avoid_ruins and neighbor == "ruins" and end != "ruins"):
                continue
            visited.add(neighbor)
            queue.append([*path, neighbor])
    raise ValueError("没有可用的路线")

@dataclass
class Memory:
    id: str
    npc_id: str
    text: str
    source_type: str
    source_event_ids: list[str]
    confidence: float
    version: int
    created_tick: int = 0
    status: str = "supported"

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
    residence: str = ""
    organization: str = ""
    goal: str = "woodcut"
    personality: str = ""

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
    def __init__(self, seed: int = 20261113, *, populate: bool = False):
        self.seed = seed
        self.rng = random.Random(seed)
        self.npcs: dict[str,NPC] = {}
        self.events: list[dict] = []
        self.resources = dict(CAPACITY)
        self.tick = 0
        self._serial = 0
        self._last: Trace | None = None
        self._baseline: NPC | None = None
        self._run_seed: int | None = None
        self._second: Trace | None = None
        self._snapshot = None
        self._learned_npc: NPC | None = None
        self.market_gold = {"east_village": 12, "west_village": 12}
        self._seed_backgrounds = populate
        if populate:
            for scene, roles in SCENES.items():
                for _ in range(5):
                    self.spawn(self.rng.choice(roles), scene)

    def spawn(self, role: str | None = None, home: str | None = None) -> NPC:
        role = role or self.rng.choice(ROLES)
        if role not in ROLES:
            raise ValueError(f"角色仅支持 {', '.join(ROLES)}")
        home = home or self.rng.choice(("east_village", "west_village"))
        self._serial += 1
        npc_id = f"npc_local_{self._serial:03d}"
        name = self.rng.choice(("阿岚", "洛恩", "伊芙", "米拉", "赛恩", "小羽"))
        npc = NPC(npc_id, role, home, f"{name}·{ROLE_NAMES[role]}{self._serial}", home, ROLE_WEAPON[role])
        npc.residence = f"{LOCATIONS[home][0]}{'营地' if home in ('forest', 'ruins') else '住宅'}-{self._serial:02d}"
        npc.organization = {"guard": "巡防队", "merchant": "行商会", "bandit": "游匪团"}.get(role, "无")
        npc.goal = ROLE_GOAL[role]
        # Keep characterization independent of the RNG used by task encounters.
        npc.personality = random.Random(f"{self.seed}:{npc.id}").choice(PERSONALITIES)
        # One unit of local goods to let a fresh actor try the trade task.
        npc.inventory["trade_goods"] = 1
        self.npcs[npc_id] = npc
        if self._seed_backgrounds:
            background = self._event(
                "backstory", npc.id, home,
                f"{npc.name}记得自己在{LOCATIONS[home][0]}{BACKGROUND[role]}。",
            )
            self._remember(npc, background)
        return npc

    def remember_dialogue(self, npc_id: str, text: str, reply: str) -> None:
        npc = self.npcs[npc_id]
        event = self._event(
            "player_dialogue", npc_id, npc.location,
            f"玩家对我说「{text[:500]}」，我回答「{reply[:500]}」。",
        )
        memory = self._remember(npc, event, "report", .45)
        memory.status = "unverified"

    def _event(self, kind: str, npc_id: str, place: str, detail: str, target_id: str | None = None) -> dict:
        ev = {"id": f"evt_local_{len(self.events)+1:04d}", "tick":self.tick, "kind":kind,
              "npc_id":npc_id,"place":place,"detail":detail,"target_id":target_id}
        self.events.append(ev)
        return ev

    def _remember(self,npc: NPC, event:dict, source_type="observation", confidence=1.0):
        mem = Memory(f"mem_local_{npc.id}_{event['id']}", npc.id, event["detail"],
                     source_type, [event["id"]], confidence, npc.version, self.tick)
        npc.memories.append(mem)
        return mem

    def interact(self, speaker_id: str, listener_id: str, message: str) -> dict:
        if speaker_id == listener_id:
            raise ValueError("不能和自己交换情报")
        speaker, listener = self.npcs[speaker_id], self.npcs[listener_id]
        if min(speaker.hp, listener.hp) <= 0:
            raise ValueError("已死亡的 NPC 无法交谈")
        if not message.strip():
            raise ValueError("请输入交流内容")
        if speaker.location != listener.location:
            raise ValueError("两名NPC必须处于同一区域才能面对面交流")
        ev = self._event("conversation",speaker_id,speaker.location,f"{speaker.name}向{listener.name}声称：{message}",listener_id)
        prior = next((memory for memory in reversed(speaker.memories) if memory.text == message), None)
        if prior:
            ev["source_event_ids"] = prior.source_event_ids[-1:]
        origins = ev.get("source_event_ids", [ev["id"]])
        reports = [memory for memory in listener.memories if memory.source_type == "report"]
        if not any(
            origins == memory.source_event_ids[-1:]
            or memory.text == ev["detail"]
            for memory in reports
        ):
            report = self._remember(listener,ev,"report",.45)
            report.source_event_ids.extend(ev.get("source_event_ids", []))
            report.status = "unverified"
            listener.trust.setdefault(speaker_id, .5)
        return ev

    def ask_offline(self,npc_id:str, question:str) -> str:
        npc = self.npcs[npc_id]
        if npc.hp <= 0:
            return "[offline规则答复] 该 NPC 已死亡。"
        if any(word in question for word in ("叫什么", "你是谁", "职业", "住哪", "住在")):
            return f"[offline规则答复] 我是{npc.name}，住在{npc.residence}。"
        if any(word in question for word in ("目标", "打算", "想做")):
            return f"[offline规则答复] 我打算{GOAL_NAMES.get(npc.goal, '回家')}。"
        if any(word in question for word in ("经历", "记得", "过去")) and npc.memories:
            memory = npc.memories[-1]
            label = "听说" if memory.source_type == "report" else "我记得"
            return f"[offline规则答复] {label}：{memory.text}（{', '.join(memory.source_event_ids)}）"
        if any(word in question for word in ("怎么走", "怎么去", "在哪")):
            for place in (npc.home, npc.location):
                label = LOCATIONS[place][0]
                if label in question:
                    directions = " → ".join(LOCATIONS[node][0] for node in path_between(npc.location, place))
                    return f"[offline规则答复] 我知道这条路：{directions}。"
        terms = [t for t in ("遗迹","强盗","矿山","森林","村庄","路","河","树","交易","资源","袭击") if t in question]
        candidates = [m for m in npc.memories if terms and any(t in m.text for t in terms)]
        if not candidates:
            return f"[offline规则答复] 我是{npc.name}，目前没有亲自获知这件事；不能把猜测说成事实。"
        mem = candidates[-1]
        label = "亲见/自身经历" if mem.source_type == "observation" else "别人转述，尚待核实"
        return f"[offline规则答复] {label}：{mem.text}（证据：{','.join(mem.source_event_ids)}）"

    def _context(self, npc:NPC, goal:str) -> str:
        # A compact reusable situation abstraction; not one Q-table per named NPC / plot.
        # Same learner generalizes between villages with similar tasks and hazards.
        hp_band = "healthy" if npc.hp >= 16 else "injured"
        return f"goal={goal}|threat=high|hp={hp_band}|gear={npc.weapon}"

    def choose(self,npc:NPC, goal:str) -> tuple[str,str]:
        context = self._context(npc,goal)
        values = npc.q.setdefault(context, {"shortcut":.65,"detour":.45})
        # Deterministic tie breaking, version does not appear in the choice rule.
        strategy = max(("shortcut","detour"), key=lambda a:(values[a], a == "detour"))
        return context, strategy

    def _destination(self, npc: NPC, goal: str) -> str:
        target = GOAL_DEST[goal]
        if target == "other_village":
            target = "west_village" if npc.home == "east_village" else "east_village"
        return target

    def _route(self,npc:NPC,goal:str,strategy:str) -> list[str]:
        target = self._destination(npc, goal)
        waypoint = "ruins" if strategy == "shortcut" else "river"
        approach = path_between(npc.location, waypoint, avoid_ruins=strategy == "detour")
        arrival = path_between(waypoint, target, avoid_ruins=strategy == "detour")
        return approach + arrival[1:]

    def _restore_world(self):
        actors, resources, market_gold, tick, random_state, serial = self._snapshot
        self.npcs = deepcopy(actors)
        self.resources = resources.copy()
        self.market_gold = market_gold.copy()
        self.tick = tick
        self.rng.setstate(random_state)
        self._serial = serial

    def run(self, npc_id:str,goal:str="woodcut", *, second:bool=False) -> Trace:
        if goal not in GOAL_DEST:
            raise ValueError(f"任务仅支持 {', '.join(GOAL_DEST)}")
        if second:
            if self._baseline is None or self._last is None or self._run_seed is None:
                raise RuntimeError("先run、learn，再rerun")
            if self._learned_npc is None:
                raise RuntimeError("需要先学习第一次实际反馈")
            if npc_id != self._baseline.id or goal != self._last.goal:
                raise ValueError("复测必须是同一NPC同一任务")
            learned = self._learned_npc
            # Reset physical/world state; inject only learned cognition/policy.
            self._restore_world()
            self.npcs[npc_id].q = deepcopy(learned.q)
            self.npcs[npc_id].version = learned.version
            self.npcs[npc_id].memories = deepcopy(learned.memories)
            self.npcs[npc_id].trust = deepcopy(learned.trust)
        else:
            if self.npcs[npc_id].hp <= 0:
                raise ValueError("已死亡的 NPC 无法执行任务")
            # Materialize the V0 values before snapshot so rollback visibly restores Q0.
            self.choose(self.npcs[npc_id], goal)
            self._baseline = deepcopy(self.npcs[npc_id])
            self._snapshot = (deepcopy(self.npcs), self.resources.copy(), self.market_gold.copy(),
                              self.tick, self.rng.getstate(), self._serial)
            self._run_seed = self.rng.randrange(2**31)
            self._second = None
            self._learned_npc = None
        npc = self.npcs[npc_id]
        context,strategy = self.choose(npc,goal)
        route = self._route(npc,goal,strategy)
        hp_start = npc.hp
        resources = 0
        success = False
        local_events = []
        start_tick = self.tick
        visited = [route[0]]
        stops = route[1:] or route
        for index, place in enumerate(stops, start=1):
            self.tick += 1
            npc.location = place
            if len(route) > 1:
                visited.append(place)
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
                damage = min(npc.hp, place_rng.randint(10,18))
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
            if index == len(stops):
                if goal == "trade":
                    qty = min(1, npc.inventory.get("trade_goods", 0), self.market_gold[place])
                else:
                    qty = min(2, self.resources.get(place, 0))
                resources = qty
                success = qty > 0
                item = ITEMS[goal]
                if success and goal == "trade":
                    npc.inventory["trade_goods"] -= qty
                    self.market_gold[place] -= qty
                    npc.gold += qty
                elif success:
                    self.resources[place] -= qty
                    npc.inventory[item] = npc.inventory.get(item,0)+qty
                ev = self._event(
                    "task_success" if success else "task_failure", npc_id, place,
                    f"{npc.name}完成{GOAL_NAMES[goal]}，获得{qty}份{item}" if success
                    else f"{npc.name}尝试{GOAL_NAMES[goal]}失败：可用资源或交易预算不足",
                )
                local_events.append(ev)
                self._remember(npc,ev)
        damage_total = hp_start-npc.hp
        duration = self.tick - start_tick
        # Task-specific feedback from executed simulated events only; range [-1, 1].
        reward = max(-1.,min(1., (0.7 if success else -0.6) + .1*resources - .035*damage_total -.015*duration))
        trace=Trace(f"trace_local_{len(self.events)}",npc_id,goal,context,strategy,visited,
                    local_events,round(reward,4),success,damage_total,resources,duration)
        if second:self._second=trace
        else:self._last=trace
        return trace

    def learn(self) -> tuple[str,float,float,int]:
        trace=self._last
        if trace is None:raise RuntimeError("请先 run")
        if trace.learned:raise RuntimeError("同一运行结果不能重复学习")
        npc = self.npcs[trace.npc_id]
        if npc.hp <= 0:
            raise RuntimeError("已死亡的 NPC 无法学习")
        old = npc.q[trace.context][trace.strategy]
        alpha = .8
        new = round(old+alpha*(trace.reward-old),5)
        npc.q[trace.context][trace.strategy]=new
        npc.version+=1
        memory=Memory(f"mem_{trace.trace_id}",npc.id,
                      f"实际执行{GOAL_NAMES[trace.goal]}/{trace.strategy}：成功={trace.success}，资源={trace.resources}，损血={trace.hp_loss}，奖励={trace.reward}；下次重新评估风险",
                      "observation",[e["id"] for e in trace.source_events],1.0,npc.version,self.tick)
        npc.memories.append(memory)
        trace.learned=True
        self._learned_npc = deepcopy(npc)
        return trace.strategy,old,new,npc.version

    def rollback(self) -> NPC:
        if self._baseline is None or self._last is None:raise RuntimeError("没有可回退的初始状态")
        self._restore_world()
        self._learned_npc = None
        # Existing event log remains an audit log. Restored NPC has no access to future memories.
        return self.npcs[self._baseline.id]

    def step_world(self, steps:int=1) -> list[dict]:
        """Local autonomous NPC demo with simple per-encounter online Q learning.

        The whole method is a test double; real world outcomes + rewards belong to C.
        """
        created: list[dict] = []
        for _ in range(steps):
            self.tick += 1
            if self.tick % 4 == 0:
                for place in self.resources:
                    before = self.resources[place]
                    self.resources[place] = min(CAPACITY[place], before+1)
                    if before != self.resources[place]:
                        created.append(self._event("resource_regrowth","system",place,
                                                   f"{LOCATIONS[place][0]}自然刷新1份资源"))
            moves: dict[str,tuple[str,str,str]]={}
            rewards: dict[str,float]={}
            evidence:dict[str,list[str]]={}
            for npc in self.npcs.values():
                if npc.hp <= 0:continue
                origin=npc.location
                choices=(*ADJACENT[origin], origin)
                destination = npc.home if npc.goal == "return_home" else self._destination(npc, npc.goal)
                path = path_between(origin, destination)
                preferred = path[min(1, len(path) - 1)]
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
                    place=max(choices,key=lambda c:(q[c] + (.25 if c == preferred else 0), -choices.index(c)))
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
                if place == destination:
                    if npc.goal == "return_home":
                        npc.goal = ROLE_GOAL[npc.role]
                    elif npc.goal == "trade" or ITEMS[npc.goal] in npc.inventory:
                        npc.goal = "return_home"
                others=[other for other in self.npcs.values()
                        if other.id!=npc.id and other.location==place and other.hp>0]
                if others:
                    other=self.rng.choice(others)
                    if npc.role == "bandit" and other.role == "guard":
                        damage = min(npc.hp, WEAPONS[other.weapon][1])
                        npc.hp -= damage
                        ev = self._event("defense", other.id, place,
                                         f"{other.name}击退{npc.name}，造成{damage}伤害", npc.id)
                        created.append(ev)
                        self._remember(other, ev)
                        self._remember(npc, ev)
                        rewards[npc.id] -= .9
                        evidence[npc.id].append(ev["id"])
                    elif npc.role=="bandit" and other.role!="bandit" and self.rng.random()<.65:
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
                    elif npc.role == "merchant" and npc.gold and other.inventory.get("wood", 0):
                        other.inventory["wood"] -= 1
                        npc.inventory["wood"] = npc.inventory.get("wood", 0) + 1
                        npc.gold -= 1
                        other.gold += 1
                        ev = self._event("trade", npc.id, place, f"{npc.name}向{other.name}支付1金币购买木材", other.id)
                        created.append(ev)
                        self._remember(npc, ev)
                        self._remember(other, ev)
                        rewards[npc.id] += .5
                        evidence[npc.id].append(ev["id"])
                    else:
                        shareable = next(
                            (memory for memory in reversed(npc.memories)
                             if memory.source_type == "observation"
                             and any(word in memory.text for word in ("采集到", "危险", "被袭击"))),
                            None,
                        )
                        msg = shareable.text if shareable else f"请问去{LOCATIONS[destination][0]}怎么走？"
                        ev=self.interact(npc.id,other.id,msg)
                        created.append(ev)
                        rewards[npc.id]+=.15
                        evidence[npc.id].append(ev['id'])
                        if other.id in moves:
                            rewards[other.id]+=.15
                            evidence[other.id].append(ev['id'])
            # Reward causes a decision-policy update, not just more chat history.
            for npc_id,(context,place,origin) in moves.items():
                npc=self.npcs[npc_id]
                if not evidence[npc_id] or npc.hp <= 0:continue
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
