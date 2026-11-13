# 接口约定摘录

## 6. 统一接口原则：先定规矩再写代码

### 6.1 唯一事实来源

C 的数据库是最终事实来源。A 的画面可以先播放挥刀、闪避和受击动画，但最终血量、死亡、掉落以 C 确认的结果为准。客户端不提交“给自己加十把剑”或“直接把目标改成死亡”，只提交发生了哪种操作和必要证据。

这是单机可信客户端方案，不是网络对战防作弊系统：碰撞与实际命中由 Godot 负责，后端做存活、距离、冷却、道具归属等合理性检查，不能声称后端完整复现了物理判定。

### 6.2 编号、坐标、版本

| 约定 | 统一规则 |
| --- | --- |
| 字段和枚举 | JSON 字段 snake_case；动作大写；不要混用 npcId、npc_id |
| 稳定 ID | world_…、npc_…、org_…、item_…、evt_…、task_…；生成后不复用 |
| 区域 ID | market、greenwood、moonwood；中文名称只用于显示 |
| 地图坐标 | tile.x / tile.y 为格坐标，左上为原点，向右／下为正；角色处于格心时如 12.5、8.5 |
| 转像素 | Godot 本地像素位置 = 格坐标 × 32；跨区必须带 region_id |
| 世界版本 | world_version 每次持久化事务提交后递增；不是帧数，也不是游戏回合 |
| 世界时间 | tick 为离散世界回合，只由 /advance 增加；同回合可有多次战斗事件 |
| 幂等标识 | request_id 标记一次请求；重试同一个请求必须使用原 ID，避免重复执行 |
| 因果顺序 | event_seq 在单个世界内递增；caused_by 只能指向已存在的上游事件 |
| 空值 | 数组为空用 []；可选对象无值用 null；不返回字符串 "null" |

只用种子不足以保证 LLM 输出复现。规则随机数状态、实际模型输出、世界版本、事件和存档都需要保留。相同种子保证初始化规则数据相同；精确回放使用日志，不重新请求模型。

### 6.3 写入规则与并发

所有写请求带 expected_world_version；/worlds 新建和 /saves/{id}/load 不要求旧世界版本。C 先处理重复 request_id，再检查版本。版本过旧返回 409 VERSION_CONFLICT，D 拉取最新状态后重新判断操作是否仍有意义，不盲目重复已经过期的攻击。

C 使用单进程服务和统一写锁。不要在数据库事务或世界写锁里面等待 LLM。流程为：读取快照 → 锁外调用模型 → 重新加锁检查角色、资源和目标 → 合法才提交。模型思考时被杀死的 NPC，回来后不能复活或继续行动。

SQLite 的连接与线程使用有明确约束；本次将所有世界写入收敛到一个服务进程和串行提交路径，不共享一个连接给不受控线程，也不以多个 worker 并行写同一世界。[S6]

### 6.4 命令、计划、任务、事件不是一回事

**命令：** 玩家说“我拾取地上这把剑”。**计划：** NPC 决定“我要去矿点采集”。**任务：** 系统批准并安排这次移动和采集。**事件：** 实际发生了“抵达矿点、采到一份材料”。

B 输出的是计划；C 校验后生成任务；A 执行需要画面动作的部分；C 收到合法完成报告后才记事件。任务状态统一为 pending、running、succeeded、failed、cancelled。取消和失败也要留下原因。

## 7. 四个部分之间的内部接口

### 7.1 A 与 D：Godot 内部

| 接口 | 调用方向 | 内容与约束 |
| --- | --- | --- |
| apply_actor_state(actor) | D → A | 更新公开人物数据；默认不覆盖正在本地移动的玩家坐标，除非切图、重生或强制纠正 |
| execute_task(task) | D → A | 输入 task_id、actor_id、kind、target_id／target_tile；开始移动、追击或逃跑 |
| collect_checkpoint() | D → A | 返回当前区域实体位置、存活本地表现、未完成任务；不能自行修改最终血量 |
| hit_detected(payload) | A → D 信号 | attack_id、attacker_id、target_id、weapon_id、双方格坐标、region_id |
| task_reported(payload) | A → D 信号 | task_id、status、最终格坐标、failure_code；不附加自由指定的奖励 |
| interaction_requested(npc_id) | A → D 信号 | 玩家靠近并按 E；D 检查是否可打开对话 |

D 统一实现 GameAPI，A 不在任何角色脚本里自行 new HTTPRequest。D 为快速命令和较慢的 Agent 请求使用不同 HTTPRequest 节点；同一个节点只处理一个在途请求。[S2]

D 的 UI 输入约定：E 交互、Enter 发送、Esc 关闭、Tab 背包、F2 编年史、F3 评委调试页。聊天输入框有焦点时锁定战斗与移动输入，使用中文输入法的 Enter 上屏不能误发空消息。F3 在发行配置中可关闭。

### 7.2 B 与 C：Python 内部

```python
async def dialogue(context: AgentContext, text: str) -> AgentDecision: ...
async def plan(context: AgentContext, trigger_event_ids: list[str]) -> AgentDecision: ...
async def reflect(context: AgentContext, outcome_event_ids: list[str]) -> AgentDecision: ...
```

context 由 C 创建，包含 npc_id、公开身份、当前目标、自己的库存、自己知道的地图与角色、已接收的事件、检索出的记忆、合法动作和策略参数。不得直接把完整 WorldState 传给 B。

AgentDecision 包含 reply、memory_proposals、intent、policy_patch、evidence_memory_ids、reason_summary。reason_summary 是用于解释行为的短摘要，不要求也不展示模型私有推理链。每次最多一个新行动意图，避免生成一串无法同步完成的事情。

C 检查 source_event_ids、evidence_memory_ids 是否真的属于该 NPC 可知集合；检查动作 ID、库存、角色存活、组织授权。拒绝的提议记录为 decision_rejected，B 下次能得知失败原因。

### 7.3 C 与 D：HTTP

D 只通过下节的 HTTP 接口访问后端，不读 SQLite。C 返回 StateView，也就是当前客户端需要显示的公开状态，不返回全部私有记忆。调试页使用独立受控接口。

**简化同步：本次不用复杂增量补丁。** 成功写请求返回完整的当前视图 data.state；D 按 ID 更新实体，按 world_version 拒绝旧视图。对话的文字仍可以显示，但较旧响应携带的 state 不能覆盖更新的画面状态。

### 7.4 D 与 C、A：地图与装备描述

shared/regions.json 由 D 维护：区域尺寸、不可走格子、入口、出口、资源点、出生点。C 用同一份数据检查路径与区域转换；A 用它或相同 TileSet 碰撞实现实际移动。坐标更改必须同步这份文件。

装备只有 C 生成。A 读取已计算好的 damage、cooldown_s、armor，D 显示 name、quality、material_id、affixes、origin_event_ids。不允许 A、D 根据“稀有”两个字再次乘一次攻击力。

## 8. HTTP 接口 v1：四人共同遵守

根地址固定为 http://127.0.0.1:8765。业务接口统一放在 /v1 下。health 不受世界版本限制。请求和响应使用 UTF-8 JSON。

### 8.1 统一响应与错误

```json
{
  "api_version": "v1",
  "request_id": "req_example_01",
  "ok": true,
  "world_id": "world_01",
  "world_version": 12,
  "data": {},
  "error": null
}
```

失败时 ok=false、data=null，error 包含 code、message、retryable。消息要能给人看，例如“目标已经死亡，不能继续交易”。HTTP 状态与错误一致：400 非法业务操作，404 不存在，409 版本或状态冲突，422 格式错误，503 服务不可用。C 必须把 FastAPI 自带的格式校验错误也转成统一外壳。

| 错误码 | 含义 | 客户端处理 |
| --- | --- | --- |
| VERSION_CONFLICT | 世界状态已变化 | 刷新状态，再判断是否仍执行 |
| NPC_DEAD | 目标已死亡 | 关闭对话或交易，更新画面 |
| OUT_OF_RANGE | 距离不够／不同区域 | 提示靠近目标，不自动传送 |
| ITEM_NOT_OWNED | 不拥有指定物品 | 刷新背包，不重复创建物品 |
| PRECONDITION_FAILED | 资源、身份或任务前提不满足 | 展示人类能读懂的原因 |
| REQUEST_IN_PROGRESS | 同一请求还在执行 | 不发新 ID 再执行一遍 |
| ACTION_NOT_SUPPORTED | 这版尚未实现此动作 | NPC 可说明做不到，不虚构执行结果 |
| BACKEND_UNAVAILABLE | 本地服务不可用 | 暂停持久化操作，提示重连 |

### 8.2 接口总表

| 方法与路径 | 用途 | 返回 data 中的主要内容 |
| --- | --- | --- |
| GET /health | 检查后端和运行模式 | status、mode、api_version |
| POST /v1/worlds | 创建世界 | state |
| GET /v1/worlds/{world_id}/state | 获取公开视图 | state |
| POST /v1/worlds/{world_id}/commands | 移动记录、命中、拾取、转交等 | command_result、events、state |
| POST /v1/worlds/{world_id}/dialogue | 与指定 NPC 自由交流 | reply、mode、intent_status、task_ids、events、state |
| POST /v1/worlds/{world_id}/advance | 推进一次世界回合 | tick、decision_summaries、tasks、events、state |
| GET /v1/worlds/{world_id}/events | 翻页读取编年史 | events、next_after_seq、has_more |
| POST /v1/worlds/{world_id}/saves | 保存当前世界 | save_id、saved_world_version |
| POST /v1/saves/{save_id}/load | 从存档创建可继续游玩的世界分支 | new_world_id、parent_save_id、state |
| GET /v1/worlds/{world_id}/agents/{npc_id}/debug | 评委查看单个 NPC 的来源与策略 | memories、policy_history、decision_history |

GET events 支持 after_seq=0、limit=50、view=player。只有 ALLOW_DEBUG=true 才允许 view=debug 和 Agent 调试接口。每次返回按 event_seq 升序排列。无后续事件时 has_more=false，不反复请求同一页。

### 8.3 创建世界

```json
{
  "api_version": "v1",
  "request_id": "req_new_01",
  "seed": 20261113,
  "player_name": "旅人"
}
```

C 决定初始人数、组织与资源组合。客户端不得传入自定义攻击力或“必出神器”参数。新建响应中提供 state.world_id、seed、tick、player_id、current_region_id、actors、items、organizations、relations、tasks 和 sites。

新世界在第一次请求时生成并保存；重试同一 request_id 返回同一世界，不再创建一个新世界。

### 8.4 自由对话

```json
{
  "api_version": "v1",
  "request_id": "req_dialogue_01",
  "expected_world_version": 12,
  "npc_id": "npc_02",
  "text": "北边的路很危险。你愿意先找人护送再出发吗？"
}
```

```json
{
  "reply": "上次运货已经损失不少。我会先问问附近的护卫。",
  "mode": "live",
  "intent_status": "scheduled",
  "task_ids": ["task_07"],
  "events": [],
  "state": "实际返回 StateView 对象，不能返回这段说明文字"
}
```

上例只展示返回字段含义；附件 examples 中提供可通过校验的完整 JSON。intent_status 只取 none、scheduled、rejected。NPC 可以只聊天或拒绝行动。scheduled 代表已安排，不等于已经完成。

text 最长 500 个字符；回复建议控制在 150 个汉字以内。C 先确认角色存活、同区域、距离不超过 2 格且非战斗状态。对话窗口打开时，本地战斗与世界自动推进暂停；网络与 UI 继续运行。

### 8.5 玩家操作与动作报告

```json
{
  "api_version": "v1",
  "request_id": "req_hit_01",
  "expected_world_version": 13,
  "kind": "HIT",
  "payload": {
    "attack_id": "attack_009",
    "attacker_id": "player_01",
    "target_id": "npc_02",
    "weapon_id": "item_01",
    "region_id": "market",
    "attacker_tile": {"x": 12.5, "y": 8.5},
    "target_tile": {"x": 13.5, "y": 8.5}
  }
}
```

| kind | payload 必要字段 | 后端必须检查／产生什么 |
| --- | --- | --- |
| CHECKPOINT | region_id、positions 数组 | 有效实体与坐标；只同步位置，不允许写血量和库存 |
| HIT | attack_id、attacker_id、target_id、weapon_id、region_id、双方 tile | 存活、同区、攻击间隔、距离、武器归属；按 attack_id+target_id 去重 |
| PICKUP | actor_id、item_id | 物品在地面、距离合法；修改唯一 owner_id |
| EQUIP | actor_id、item_id | 拥有并可装备；换装不复制物品 |
| GIVE | actor_id、target_id、item_id | 双方存活同区；物品实际转移；不因对话承诺就转移 |
| ACCEPT_OFFER | actor_id、offer_id | 对方报价仍有效、双方物品／资金足够；同一事务完成交换 |
| CHANGE_REGION | actor_id、exit_id | 处于合法出口；新坐标来自地图描述，不由玩家随便指定 |
| TASK_REPORT | task_id、status、actor_id、region_id、tile、failure_code | 任务仍有效；到达目标／失败属实；不能自由附送奖励 |
| JOIN_ORG | actor_id、org_id、offer_id | 有有效邀请或入会条件，不能冒充代表修改组织 |
| LEAVE_ORG | actor_id、org_id | 确为成员；释放未执行的组织授权任务 |

普通命中只上传命中事实，由 C 计算基础伤害 max(1, weapon.damage - target.armor)。动画可以先播放，永久死亡和掉落等待确认。攻击间隔读 weapon.cooldown_s；同一挥刀命中多个目标可分别报告，但同目标不能重复扣血。

对可见 NPC 的移动任务，A 报告抵达后 C 才完成采集、调查等后续效果。地图切换前 D 提交 CHECKPOINT；C 接管离屏任务，按同一地点图和耗时规则继续，回到地图时再同步。不可让客户端与后端同时模拟同一个角色的战斗。

### 8.6 世界推进

```json
{
  "api_version": "v1",
  "request_id": "req_advance_01",
  "expected_world_version": 18,
  "reason": "idle_timer",
  "trigger_event_ids": ["evt_12"]
}
```

reason 只取 idle_timer、major_event、rest、debug_step。D 统一拥有推进定时器：可自由探索且不在战斗／对话／加载时，约每 20 秒请求一次。重要事件只标记“待推进”，不让 A、B、C 各自重复 tick。

每回合最多调度 1 名需要决策的 NPC；总 LLM 并发上限 2。世界大 Agent 每 3 回合或重要社会事件后评估一次，不每帧调用。忙时合并触发，不无限积压。调试页的“推进一步”仍走同一接口，不直接改数据。

### 8.7 保存与载入

保存请求包含 request_id、expected_world_version、label。保存前 D 停止新操作，等待已发出的写请求完成，并提交 CHECKPOINT。C 存储世界、事件、NPC 记忆、任务、组织关系、物品归属、策略版本和随机数状态。

加载请求包含 api_version、request_id，响应创建新的 world_id，并保留 parent_save_id。原始存档不覆盖，便于从同一点展示两种玩法。相同请求不能重复创建分支。

不要在本地攻击动画进行到一半时存档。恢复时重新检查 running 任务；目标已死亡则取消，不能为了恢复剧情而复活目标。

## 9. 共同数据字典

### 9.1 必须持久保存的对象

| 对象 | 必要字段 | 人话解释 |
| --- | --- | --- |
| World | id、seed、tick、world_version、rng_state | 这一个存档及其随机状态 |
| Actor | id、name、alive、hp、max_hp、region_id、tile、skill_tags、org_ids、inventory、equipped_item_id | 玩家、NPC、怪物的身体和物品 |
| NPCPrivate | actor_id、identity、goals、beliefs、policy、policy_version | 人物自己的看法和行为倾向，不给所有 NPC 共用 |
| Organization | id、name、function_tags、member_ids、representative_id、resources | 组织能做什么、谁能代表组织签协议 |
| Relation | from_org_id、to_org_id、stance、trust、source_event_ids | 有方向的关系；一方敌视不代表另一方自动报复 |
| Proposal | id、kind、proposer_id、target_id、terms、status、expires_tick | 未成立的交易或合作提议 |
| Item | id、name、base_type、quality、material_id、affixes、stats、owner_id、origin_event_ids | 装备唯一实体，不只是物品名字 |
| Task | id、actor_id、kind、target、status、started_tick、source_event_ids | 已获准执行的一件事 |
| Event | id、event_seq、tick、type、actor_id、target_id、facts、caused_by、witness_ids | 实际发生过的事情与来源 |
| Memory | id、npc_id、statement、source_type、source_event_ids、confidence、status | 某个 NPC 知道或相信的内容 |
| Decision | id、npc_id、intent、evidence_memory_ids、reason_summary、result_event_ids | 为什么提出这个行动，以及实际结果 |

confidence 是用于排序的主观信任分值，不宣称是统计校准后的“真相概率”。事实、转述和推测分开；更新记忆时标记旧记忆被修正，而不是删除历史。

### 9.2 Agent 可提出的动作

| action | 作用 | 主要限制 |
| --- | --- | --- |
| WAIT | 暂不行动 | 安全降级；不产生虚构奖励 |
| MOVE | 前往已知区域或地点 | 路径、存活、任务占用检查 |
| GATHER | 在资源点采集 | 抵达后扣资源点存量，再增加库存 |
| TRANSFER | 赠送物品或提出交换 | 赠送自有物品；交换须双方接受 |
| SHARE_INFO | 向特定人物传递消息 | 只能传自己知道的内容，保留转述来源 |
| PROPOSE_RELATION | 提议贸易、联盟、停战，或宣布敌对 | 只有组织代表有权限；互惠关系需要对方接受 |
| RESPOND_PROPOSAL | 接受或拒绝提议 | 提议未过期、资源足够、本人有授权 |
| ATTACK | 攻击一个有效目标 | 真实战斗结算；不能用 LLM 决定“直接秒杀” |
| FLEE | 逃向已知安全点 | 需要可行走路径；不是瞬移 |
| CRAFT | 使用材料制作装备 | 已实现配方、技能、材料与地点条件满足 |
| JOIN_ORG | 加入组织 | 有邀请或可满足入会条件 |
| LEAVE_ORG | 离开组织 | 取消相关授权；个人物品不凭空消失 |

C 在上下文中只给 B 当前可用动作；尚未完成的动作不要提供给模型。P0 先完整做 WAIT、MOVE、GATHER、TRANSFER、SHARE_INFO、关系提议与响应；ATTACK/FLEE 接 A 的战斗逻辑；CRAFT 用一个通用配方。不能把模型输出中没实现的动作默默当作成功。

### 9.3 装备生成规则

基础形态先做剑、斧，两者复用近战逻辑。材料、品质和词缀在数值预算内组合；词缀先做锋利、迅捷、护身，分别影响伤害、攻击间隔、防护。每件装备最多 2 个词缀。

建议初始数值范围：基础伤害 4–12，攻击间隔 0.35–0.80 秒，护甲 0–3。这些是本次平衡初值，不是引擎限制。C 算出最终 stats，A 原样使用。

掉落只在真实死亡事件后生成或转移。NPC 的已持有武器使用原 item_id 掉落，不重新抽一把。制造消耗材料；新 NPC 入场携带的物品属于明确的迁入资源来源。稀有名称由规则或 LLM 命名都可以，但不能命名后自动产生没实现的技能。

## 10. Agent 如何真正改变世界

### 10.1 “自进化”要落在后续行为上

采用三层闭环：经历成为可溯源记忆；记忆改变目标和策略参数；新的参数影响下一次实际行动。例如某商人连续遇到损失，护送偏好提高，下次不再独自出发，而是提出雇佣或改道。

最小实现保留 policy_version、旧参数、新参数、依据事件、下一次实际选择。B 提修改建议，C 对变化幅度和依据进行检查后保存。不要只展示“NPC 感到难过”的新台词，也不要声称底层模型参数已训练。

策略变化不要求每次都随机。相同证据可以产生相同决定；重玩差异来自种子、人物目标、玩家行为和真实事件，而不是靠随意跳剧情制造不可预测性。

### 10.2 知情、谣言与溯源

C 判断目击者：至少同区域、合理距离；能做遮挡判定就使用 A 的视野报告。没做遮挡时在实现说明中写清采用距离近似。未目击者不会因为后台知道凶手就突然知道。

玩家说“某工坊杀了人”形成 speech 事件；NPC 可以怀疑、转述、调查，但不会直接生成 murder 事实。甲、乙重复同一条传闻不构成两份独立证据，source_event_ids 应追到同一个最初来源。

玩家面板只展示已发现内容；评委调试页可以展开完整来源，但这些调试数据不能进入 NPC 的提示词。编年史的因果连接表示系统记录的依赖关系，不声称从语言解释中证明了严格统计因果。

### 10.3 世界大 Agent 的边界

C 维护 WorldDirector，使用 B 的通用模型调用器。它读取世界真实摘要，提出“哪个已有矛盾值得响应、是否有合理的新人物迁入、哪个组织产生资源需求”。规则层再验证人口上限、入口、可用资源和已实现能力。

迁入必须包含来源、入场地点和原因，例如集市出现药品需求，外地药师来寻找工作；新人物使用通用 Actor。没有合法生成条件时不生成。不能为追求戏剧性凭空让两个组织宣战。

远处角色只按简化地点与耗时规则执行；关键战斗使用规则结算并记录输入与结果，不由 LLM 口述胜负。人物一旦进入当前区域，模拟所有权转交给 A 的客户端，C 不同时推进其位置和战斗。

### 10.4 死亡和世界继续运行

NPC 死亡后：标记 alive=false；取消未完成任务和无效报价；转移可掉落物品；移除组织成员身份；已有记忆、事件和历史关系保留。组织代表死亡时从存活成员中选择合法继任者；没有成员则组织进入 inactive，不强行生成替身。

所有 NPC 都被杀死时游戏仍可探索和战斗，之后只有满足迁入规则才出现新人。原 NPC 不复活。玩家死亡采用“倒下后返回集市、损失一部分随身材料”的简单规则；这与 NPC 永久死亡明确区分。

### 10.5 模型故障与安全界限

每次模型调用硬超时 8 秒，单次业务请求总预算建议不超过 12 秒。仅格式错误允许一次小范围修复；连续两次服务失败进入 fallback。UI 显示当前模式，不把规则台词冒充实时 AI。

对话内容是不可信输入，不能成为系统指令。模型没有运行终端、改数据库、访问密钥或任意联网权限。模型只能选择已授权动作，不能返回代码让游戏执行。日志要脱敏，公开包不附带真实密钥。

