# 四块系统如何接在一起

所有路径从仓库根目录算。公共字段参考 shared，不能各自按习惯改名。
身体属于 A，想法属于 B，世界事实属于 C，窗口和网络属于 D。

## 1. A 与 D：游戏内部，不用 HTTP 互调

A 的通用 Actor 至少提供：

| 接口 | 调用方 | 输入/输出 |
|---|---|---|
| apply_actor_state(actor: Dictionary) | D → A | 输入 shared.ActorState；血量/生死来自 C，不再次计算伤害 |
| execute_task(task: Dictionary) | D → A | 输入 shared.Task；同 task.id 不重复启动 |
| collect_checkpoint() -> Dictionary | D → A | 返回 region_id、positions[{actor_id,tile}]，对应 CheckpointPayload |
| set_controls_locked(locked: bool) | D → A | 聊天或加载时锁玩家操作，不阻塞 UI 和网络 |
| hit_detected(payload: Dictionary) | A → D 信号 | 完整 HitPayload，不带自定 damage、reward |
| task_reported(payload: Dictionary) | A → D 信号 | 完整 TaskReportPayload，成功或失败及实际位置 |
| interaction_requested(npc_id: String) | A → D 信号 | 靠近并按 E，D 打开对话 |
| pickup_requested(item_id: String) | A → D 信号 | D 组装 PICKUP；不本地先把物品永久入库 |

A 若在 Actor 上收集单个位置，D 汇总成全场景 CheckpointPayload。
格坐标×32=像素坐标；坐标含 region_id，不把像素值直接传给 C。
D 调用 GameAPI 提交命令，成功后使用返回 state 更新 A。
聊天框聚焦、载入存档、切换评审世界时，A 必须停止玩家新输入。
有碰撞动画不等于服务器确认；后端不可用时不能假装已掉落或已交易。

### 评审运输需要的最小追加
A 实现可复用 `ESCORT` 任务：护卫跟随目标 Actor，附近有敌人则用普通战斗逻辑保护。
这是 `Task.kind` 的约定，不是给模型随意添加新 Action。
C 负责创建 ESCORT 和商人的 MOVE 任务；B 选择运输方案，不能发“已送达”。
运输任务 Task.target_id 是实际商人 ID，不能写死 npc_02。
A 不设置 run1/run2 的不同伤害、血量或敌人 AI。
商人到站上报普通 TASK_REPORT，货物损失、费用、完成指标由 C 结算。

## 2. B 与 C：Python 函数交接

保留三个已有接口：
```python
async def dialogue(context: AgentContext, text: str) -> AgentDecision: ...
async def plan(context: AgentContext, trigger_event_ids: list[str]) -> AgentDecision: ...
async def reflect(context: AgentContext, outcome_event_ids: list[str]) -> AgentDecision: ...
```
实现位置 `server/agents/service.py`。C 用 `from server.agents.service import ...`，B 不建第二个 FastAPI 服务。
B 自己的 CLI 测试可放 `server/agents/cli.py`。其模型调用封装在 `server/agents/provider.py`。

### mode 和模型故障怎样传给 C
不要给 AgentDecision 私自增加 mode 字段（原模型禁止未知字段）。
B 在 `server/agents/errors.py` 定义 `AgentCallFailed`；正常 dialogue/plan/reflect 只有真实模型成功才返回。
超过预算或输出仍不合法时抛该异常；C 捕获后调用 B 提供的
`safe_fallback(context: AgentContext) -> AgentDecision`，返回明确的 WAIT/降级回复，HTTP 的 mode 填 fallback。
C 不向客户端泄漏原始异常里的请求头/密钥。基础 MOCK 本身固定 mode=mock。
评审的规则学习可以不依赖 LLM；应在报告明确“规则学习，未调用LLM”，不能因此伪装为模型推理。

所有 context 来自 C：身份、本人记忆、已知事件、合法动作、真实策略版本。
B 返回 memory_proposals / intent / policy_patch；C 验证并持久化。
B 不直接连 SQLite、不自行变更 inventory、不把完整世界作为所有人的上下文。

### 新的可学习运输策略
在 `server/agents/transport_learning.py` 实现：
```python
def choose_transport(context: TransportContext, profile: LearningProfile) -> TransportChoice: ...
def learn_transport(profile: LearningProfile, outcome: TransportOutcome) -> LearningUpdate: ...
```
类型来自 `shared/evaluation_protocol.py`。两个函数不写库、不读 run_number、不访问全局运行次数。
choose 根据合法策略、当前 Q 值及已保存经验选 direct 或 escort；
learn 只用 C 传来的真实 outcome 更新已选择策略并产生带来源的学习记忆。
学习率由场景配置在首跑前冻结，作为 profile.alpha 传入，不能演示中人工调整。
回退由 C 恢复 profile，B 不维持另一份会泄漏 V1 经验的隐藏全局缓存。

C 调用顺序：
1. 从固定 snapshot 创建任务实例；读取当前 profile 和合法选项。
2. 调 B.choose_transport，检查所选方案是否合法。
3. direct：创建商人 MOVE；escort：检查预算与护卫权限，真实付款，创建护卫 ESCORT + 商人 MOVE。
4. C 从已确认命中、到达、库存和任务事件计算 outcome。
5. 第一轮完成后锁外调用 B.learn_transport；核对依据和版本后保存 V1。
6. 第二轮重置初始世界但读取 V1，再调用同一个 choose_transport。
评审期间不并行调用其他 reflect 去修改该 profile，避免有两套学习逻辑互相覆盖。

`AgentDecision.policy_patch` 保留给普通世界；评审任务使用 LearningUpdate 是唯一策略写入渠道。
V0/V1 的 model、系统提示词、任务参数、alpha 固定，新增记忆是自动学习数据而不是人工改提示词。

## 3. C 与 D：HTTP

端口 8765；基础接口和响应 Envelope 原样保留。
D 的 `game/net/game_api.gd` 是唯一网络入口；A 不另写 HTTPRequest。
新评审接口详见 EVALUATION_CONTRACT；不要继续使用聊天里旧的概念路径 `/evaluation/start`。

D 负责：
- 每次新操作一个 request_id，超时重试同一请求保留 ID。
- 写请求串行；对话等慢调用不能阻塞 Godot 主线程。
- state 只在 world_id 匹配当前世界且 world_version 不落后时应用。
- 切换世界/回退时增加本地会话代号、清空旧角色和任务，忽略旧会话迟到响应。
- 收到 409 刷新状态并判断操作是否仍有效，不盲目重放攻击。
- 自动推进世界只用一个定时器。对话、战斗、评审运行或加载时按约定暂停。
- HTTP 成功不等于业务成功，检查 Envelope.ok 和 data 中的 mode/applied。
C 负责：
- 状态更新与事件写入一起提交；先 request 去重再版本检查。
- 不在世界锁或数据库事务里等待模型；回来后再查 NPC 生死与权限。
- 每轮评审用不同 world_id，但共同的 snapshot 内容和 scenario_hash。
- 旧轮后台请求、迟到任务报告不得写进新轮世界。

## 4. 地图、装备、素材

D 唯一修改 shared/regions.json；A 做相符的碰撞/移动；C 用同文件做区域和目标校验。
状态里的 appearance_key 使用 D 的外观注册表；未知键显示占位角色，不能崩溃。
初始地图 ID 保留 market / greenwood / moonwood，不各自叫 forest_1。
装备只有 C 生成和计算最终 stats，A 读取，D 展示；不得因品质再乘一次伤害。
源素材与许可证由 D 入仓，不能把本机绝对路径写入 tscn。

## 5. 每次对接给对方什么

| 交付方 | 交给谁 | 最少交付 |
|---|---|---|
| A | D | 通用 Actor 场景、方法/信号、独立测试场景、实际运行说明 |
| B | C | 上述函数、通过校验的实例、测试命令、失败/超时策略 |
| C | D | 真服务命令、/docs、样例和错误码、可创建的测试世界 |
| D | A/C | 固定地图描述、可运行主场景、GameAPI、联调复现步骤 |
| B/C | D | 实测 run/report、学习差异、回退结果；不是一张手填对比表 |

## 6. 公共协议要改怎么办
在本人 STATUS 记录：需要什么字段、为什么、影响哪两端、怎样兼容旧样例。
C 更新共享模型与 API 文档、样例、测试一起提交；A/D/B随后适配。
最终功能冻结后，不为美术或方便临时改接口。
