# R6 整合交接：四人都先读这里

**基线**：用户上传 main ZIP，提交标记 `1e2d84c5a01d2a11454364d398cabd6306449029`。
这不是对后来 main 的远程读取；之后的提交需要正常合并。

## 变更总览

A：不重写原始 actor/player/npc 战斗模块。修改 D 的 network_npc 适配器，使死亡对象淡出、
停止碰撞，保留 C 的死亡档案。怪物复用已有 wolf/wisp 资源；动态人体仍用 D 的人物表。
D：新增 play_windows 标题/设置/读档/商店/箱子/手札 UI，world_container 箱子实体；
network_main 连接操作与事件、暂停/自动保存/后台推进；隐藏头顶姓名、职业和固定对话按钮。
B：AgentDecision 新增 social_signal；合法意图增加 OPEN_TRADE、BARGAIN、ASK_WORK、
ACCEPT_QUEST、GUIDE_HOME。service 仍返回提议，不直接改钱/物品。game_fallback 明确是规则。
C：living_world、play_service、ambient 实现真实库存/任务/人口/关系/快速世界回合；
sqlite 保证同一请求重复发送不会重复发物品或扣钱。StateView 增加可兼容默认字段。
所有变更放同一个整合 PR，由 D、C 重点审查，不允许彼此继续使用旧字段单独“猜接口”。

## 数据和权限

StateView 新增 appearance、containers、quests、known_npc_ids。
ActorState 新增 equipped_slots。ItemState 支持 armor 与 equipment_slot。
名字/性格/目标仍存在后端；NPC 原有私人记忆接口不直接进入普通玩家 HUD。
world_life 是本轮的组织/个人关系、人格快速策略、任务托管、生成时间与钱袋记录，
纳入完整存档快照。旧世界不自动凭空获得新箱子/装备，测试时建新世界。

C 对真实受击先采用人格/血量驱动的即时逃跑、反击、求助，不等待模型。
在线 B 根据私人上下文作更慢的社会和行动决策；不得把这一快速策略说成每帧都调用 LLM。

## 新 HTTP 接口

沿用原 Envelope、request_id、expected_world_version 和错误格式。
客户端 POST 自行附加 request_id；所有世界写入还带 expected_world_version。

| 接口 | 含义 |
|---|---|
| GET /v1/local/model | 配置状态；不返回 API key |
| POST /v1/local/model | 本机运行内存中的模型配置；请求类型 ModelConfig |
| GET /v1/saves | 最近保存点目录 |
| GET /v1/worlds/{id}/shops/{npc} | 真实报价、库存、钱包和 quote_id |
| POST /v1/worlds/{id}/shops/{npc}/buy | item_id + quote_id；不能提交价格 |
| GET /v1/worlds/{id}/containers/{box} | 可接近、可开启箱子的真实内容 |
| POST /v1/worlds/{id}/containers/{box}/take | item_id 可空、take_gold；重复请求不重复领取 |
| POST /v1/worlds/{id}/consume | item_id；实际消耗药剂并恢复生命 |
| POST /v1/worlds/{id}/quests/accept | quest_id；检查接受条件、实际取出托管包裹 |
| GET /v1/worlds/{id}/journal | after_seq / limit；亲历事件、已知任务、编年章节 |
| POST /v1/worlds/{id}/heartbeat | AdvanceRequest；快速规则推进和消费已完成的模型提议 |

基础 /advance 和运输 evaluation 接口保留。不要把 heartbeat 接进评测世界改变对照条件。
shared/play_protocol.py / .schema.json 是新请求格式；/docs 由实际 FastAPI 生成。

## 对话不是只显示回复

NPC dialogue 返回中可携带：
`ui_actions = [{kind: "open_trade", merchant_id: "..."}]`
或 `{kind: "show_quests"}`。
只在 C 校验成功并记录真实事件后返回。D 据此发起查询并打开窗口。
商人说“我愿意九折”不是可信价格来源；价格由后端按结构化关系和性格重算，
反复议价不无限叠加，高敌意可以拒售。聊天记忆是来源，物品和钱由 C 管。

## 异步世界回合

原来客户端串行 HTTP 等同步 /advance 模型返回，会拖住战斗。现在普通世界用 heartbeat：
当前请求只做规则结算，再启动有上限的模型提议计算；后台绝不直接修改世界。
下一次 heartbeat 用当时真实状态重新验证提议，已死/忙碌/条件失效的 NPC 不能继续行动。
这不能消除模型本身的网络延迟，但不应让普通世界回合一直占着攻击请求队列。
对话期间游戏暂停；后台提议只在后续实际世界推进时提交。

## 任务不是自动判成功

送货：商人确有商品和 5 金币才托管报酬；有空闲游荡同伴时创建取货任务，再创建送达任务。
抵达必须走 A 的 TASK_REPORT；实际 GIVE 后才发工资。玩家也可接受尚未分配的任务。
救助：已有游荡人物进入 lost 状态；玩家获知并交谈后安排其回到委托人附近；
实际到达才完成。本版不是“全程跟随玩家”的 escort AI。
人物死亡/中断/超时均有失败记录与托管资金处理。
可用事件提案种类仍有限，不支持模型任意生成未实现的任务代码。

## 合并检查与责任

A 检查死亡淡出、怪物与武器命中；B 检查新动作枚举和 live 输出；C 检查事务、
真实库存、读档、任务来源链；D 检查 Godot 解析、菜单布局、中文输入、热键、启动器。
不要用 Python 单元测试通过替代 Godot 现场验收。
模型 Key 不提交；runtime/.venv 不提交；旧 README 的启动方式以 README_R6.md 为准。
