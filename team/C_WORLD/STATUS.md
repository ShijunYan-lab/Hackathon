# C｜世界规则、数据、接口与评测 · 工作记录

认领人：C 岗已认领，姓名待填写
分支：feature/c-world
最后更新：2026-11-13（UTC+8）
当前状态：C 分支已完成世界导演接口节点和可启动后端小切片；SQLite 世界、事件与位置保存已通过测试及本机 HTTP 验证。完整战斗、Agent 执行与评审待实现。

交付约定：用户已授权每完成一个节点及时测试、启动验证、更新记录、commit 并 push 到 feature/c-world。2026-11-13 首次 push 因 GitHub 账号权限返回 403，按用户指定登录 qirongbo 并配置当前仓库后，导演节点 da4a55a 已成功推送。当前分支跟踪 origin/feature/c-world。

## 本轮目标

用户反馈团队拟采用一张连续地图加探索迷雾，C 后续按此方向规划。集市、翠林、月林可作为同图地点；D 负责地图与迷雾显示，A 负责行走和碰撞，C 负责坐标校验、世界事实及知识权限。具体 region_id 与坐标对应关系待 C/D 对齐。

为《未定之境》实现一套供正常沙盒和评审共用的任务、战斗、物品和事件规则。正常游戏从种子生成 NPC、组织与装备，玩家可以探索、战斗和自由输入对话。所有已生成 NPC 都可受攻击，死亡后任务、装备归属、组织成员和代表随事实更新。NPC 只根据亲见或获知的信息行动，组织间合作有独立的双方授权。

评审从集市向翠林运送药材。评审会话负责控制初始条件、读取当前学习版本和收集真实成绩，运输仍由 Godot 中的角色实际移动与战斗。场景允许直接运送或付费雇佣护卫。第一轮的真实结果自动更新已执行策略，第二轮从同一初始世界条件重新选择，最后可恢复初始世界和整份初始学习状态。

## 已完成
- [x] WorldDirector 可注入模型接口、世界记忆与剧情线索 DTO、单地图地点配置、触发/超时/引用校验和独立测试
- [x] 创建并切换到本地 `feature/c-world`，核对 C 任务卡、A/B/D 交接、基础 v1 和 evaluation-v1 合同及现有样例
- [x] 在本机复跑脚手架检查
- [x] 第一轮小交付完成（真实入口、创建世界、state、CHECKPOINT、事件和持久化）
- [ ] 已按TASKS完成本岗P0
- [ ] 与相邻模块实际联调
- [ ] 已支持评审两次运行相关职责

## 修改的文件

本轮更新 `team/C_WORLD/STATUS.md`。远程分支待首次发布，届时用 `git push -u origin feature/c-world`。

按用户要求，其他岗位由后续同学组装对接。本轮新增 `server/world/director.py`、`server/world/director_config.json`、`docs/WORLD_DIRECTOR_CONTRACT.md`、`tests/test_world_director.py`。接口说明包含输入输出、模型异常语义、配置位置、事务接入条件和已有 HTTP 路由衔接。世界记忆、剧情线索的持久化及建议执行器待完成。

首个实现切片拟新增 `server/main.py`、`server/api/worlds.py`、`server/storage/sqlite.py`、`server/generation/initial_world.py`、`server/world/commands.py` 和 `tests/test_world.py`。先交真实入口、创建世界、读取状态、写入事件和一条真实 `CHECKPOINT`，可独立跑通。

实际首个服务切片新增 `server/main.py`、`server/storage/sqlite.py`、`server/generation/initial_world.py`、`server/world/commands.py`、`tests/test_world.py`、`server/api/smoke.py` 和 `docs/BACKEND_QUICKSTART.md`。当前五个路由直接在 main.py 组装。导演节点本地提交 da4a55a。

## 实际运行的测试与结果

在仓库根目录用现有 Windows Conda `pytorch` 环境的解释器复跑。Python 3.10.14、FastAPI 0.136.1、Pydantic 2.11.3、HTTPX 0.27.0、pytest 9.1.1。这是脚手架基线，交付目标为独立 Python 3.11 和仓库固定依赖。

```powershell
$backendCheckPython = 'C:/ProgramData/anaconda3/envs/pytorch/python.exe'
& $backendCheckPython -B -m pytest tests -q -p no:cacheprovider
& $backendCheckPython -B -m tools.check_contracts
& $backendCheckPython -B -m tools.check_evaluation_contracts
```

- pytest 34 项通过，覆盖现有 DTO 和基础 MOCK。
- 基础协议 9 份 JSON 样例通过，评审协议 6 份 JSON 样例通过。
- 本轮在上述环境复跑全部测试，45 项通过（含新增 11 项世界导演用例）；基础 9 份和评审 6 份样例检查通过，git diff --check 通过。新测试使用合成 provider，覆盖超时、缺失 provider、评审冻结、触发周期、非法来源/目标、未启用执行器以及未来记忆引用。
- 待验证 Python 3.11 固定环境、真实 SQLite 后端、Godot 联调、真实 LLM、完整两轮运输及第二台 Windows 冷启动。当前地图标记为 `fixture_only`，正式路线和碰撞仍待 D 交付。
- 服务节点全量测试 52 项通过，新增覆盖创建、确定性初始化、重启读取、持久化去重、并发重复请求、事务失败回滚、非法坐标和统一错误外壳。协议 9+6 份样例通过。临时服务使用现有 weclone 环境（Python 3.10.14 / FastAPI 0.112.0 / Pydantic 2.8.2 / Uvicorn 0.30.6），实际 HTTP smoke 通过，创建世界、移动一格、重放请求、读取两个真实事件。以上补充真实 SQLite 验证，Godot/LLM/两轮评审/固定目标环境仍待验收。

服务入口 http://127.0.0.1:8765/docs，能力与模式见 /health。数据库 runtime/worlds.sqlite3。复现运行 `python -m server.api.smoke`。当前地图采用现有 market 占位平面，正式单地图可由 D 通过地图配置接入。运行说明见 docs/BACKEND_QUICKSTART.md。

实际重启后再次读取首次演示世界 world_a7a5702207904ce8872862debb59ccee，版本仍为 1、玩家位置仍为 (9.5, 8.5)。新启动实例的 smoke 再次通过，/docs 返回 HTTP 200。

## 开发顺序与可验收产物

| 顺序 | C 岗交付 | 过关条件 |
| --- | --- | --- |
| 1 · C01/C02/C03 首个切片 | FastAPI、统一 `Envelope`（含 422）、SQLite、种子生成、`GET /health`、`POST /v1/worlds`、`GET /v1/worlds/{id}/state`、`CHECKPOINT` 和创建事件 | D 用真服务创建世界并读取动态 ID；提交新位置后重新查询及重启服务仍能读取；相同请求重放保留结果，过期版本返回 409；初始规则数据按种子复现 |
| 2 · C04/C05/C06 真执行闭环 | 实现 `HIT`、死亡/掉落与拾取换装，接 B 自由对话和可执行 MOVE 或 GATHER，经 `TASK_REPORT` 结算 | A 报同一次挥刀的同一目标两次只扣一次，多个合法目标分别结算；NPC 死亡取消任务并掉落同一物品 ID；对话产生的计划在真实到达后才产生效果；模型返回时复核生死、版本和权限 |
| 3 · CE1–CE2 评审接线 | 建 `transport_v1` 会话、冻结 S0/P0 和运行配置，按合法选项调用 B 选策，安排 MOVE / ESCORT、同图路径目标、已授权扣款和任务超时；用同一命令服务接收实报 | D 用现有评审路由创建会话、启动和轮询；A/D 带商人在同一地图上从集市出发点走到翠林接收点，护卫使用普通战斗逻辑；C 从到达、命中、扣款、死亡或超时事件封存首轮结果 |
| 4 · CE3–CE5 学习、对照、回退 | 首轮完成后自动调用 B 学习，校验并原子保存 P1；二跑从 S0 的新世界加载 P1；发布可追溯报告；回退恢复 S0/P0 并支持 `rollback_check` | 重试或服务重启后同一个 `source_run_id` 仍只提交一次学习；两轮敌人、货物、资金和冻结设置一致；报告显示交付率、费用、耗时与策略变化；回退作废旧写入、恢复经验可见性与缓存，历史记录仍可查 |
| 5 · C05–C09 普通世界与交付 | 补齐资源点、交易和组织提议/应答、见闻来源、保存/载入、离屏任务、世界回合、合法迁入和有边界的 WorldDirector；与 D 完成后端构建 | 有且只有一个物品持有人；组织合作有双方证据；目击与转述可区分；保存加载产生独立世界分支；正常探索与评审可分别重复运行；另一台 Windows 能冷启动 |

第 2 步开始即可推进第 3 步的快照、流程测试和 D 接线。独立测试使用明确标注的 B 测试替身与合成动作证据，评审验收走真实 A/B/D 模块。以团队 UTC+8 节点倒排，11/14 01:00 目标为首条真实交互闭环，12:00 目标为评审两轮链路，16:00 目标为实测报告和回退，18:00 冻结功能，22:00 目标为可提交版本，11/15 08:00 正式截止。复杂经济、组织分裂与内容扩充按 P1 排后。

### 落地时的状态边界

- 同一 SQLite 事务提交状态、事件和幂等结果。先检查 `request_id`，再检查 `expected_world_version`。命中另按世界、挥刀与目标去重，冷却按挥刀计算；相同挥刀对不同合法目标的命中单独结算。SQLite 事务与写锁之外等待 B，提交时重验条件。
- 区分 `world_version`、`evaluation_version`、`LearningProfile.version` 和离散 `tick`。评审暂停普通推进，任务超时独立于 `/advance`；明确区分实际任务超时与环境或服务故障。冻结快照含实体、资源、敌人生成时间表、随机数状态、地图内容和场景规则；日志记录代码、模型、固定提示词与预算版本。新一轮保留场景逻辑身份，用新 `world_id` 隔离状态和请求。
- 交付、扣款、货损由 C 从该轮已提交事件结算。场景结束只结算一次。C 校验 B 只更新已经执行的策略、来源属于首轮、学习率和身份保持一致；报告按条件与真实结果显示改善、持平、退步、不可比较或未测。规则学习应说明实际执行方式，MOCK 样例只用于展示接线。
- 场景预验收要分别测任务是否成功与策略是否改变。按样例初值 direct=0.6、escort=0.5、alpha=0.8，若 B 按最大 Q 选策，首轮执行 direct 后的更新值为 `0.12 + 0.8 × reward`，仅当 reward 小于 0.475 时它才低于 escort；刚好相等时依 B 约定的平局规则。使用冻结条件重复实测并保留全部结果，正式两轮之间沿用同一配置。
- 回退恢复初始 `LearningProfile`（含 Q 值、记忆与 `retrieval_epoch`）、检索摘要/缓存和 S0，递增 `evaluation_version`。旧轮写入与在途学习提议作废，已封存日志仍供审计。用回退检查运行验证实际选策读取到 P0。

## 需要别人接入什么

| 对接方 | C 给出的交付 | 对方交付及联测 |
| --- | --- | --- |
| A · 角色与战斗，经 D 转发 | `StateView`、真实 `Task`、命中与到达校验条件、服务端伤害和任务结算示例 | A 消费 `apply_actor_state`、`execute_task`，以 `Task.id` 去重执行，通过 `hit_detected`、`task_reported` 报告实际动作。报告里的 `task_id` 对应 `Task.id`。用动态 ID、32 像素格和服务端计算的装备属性联测多目标、重复命中、MOVE/ESCORT、死亡取消任务 |
| B · NPC 与学习 | 提供按 NPC 权限裁剪的 `AgentContext`、一组真实可知来源和允许动作样例；提供 `TransportContext`、P0/P1 和由 C 结算的 `TransportOutcome` | B 交 `dialogue/plan/reflect`、`AgentCallFailed`、`safe_fallback`、`choose_transport`、`learn_transport` 及测试。双方验证越权来源、无钱/护卫不可用、慢回复时死亡、已试策略单次学习、回退后读取 P0 |
| D · 地图、网络、UI | 交 `server.main:app` 启动命令、`/docs`、测试 seed、真实请求/响应和错误码；提供评审会话/报告/回退步骤 | D 交 `shared/regions.json` 正式地图、坐标范围/障碍/接收点/外观键和唯一 `GameAPI`。写入串行、重试保留 ID、409 刷新；按世界和版本筛旧状态。启动评审收到 202 后每 0.5–1 秒轮询会话，换世界清旧任务和信号，从服务端报告读取指标 |

第一轮交付后，联调人从仓库根目录用独立 Python 3.11 启动 `python -m uvicorn server.main:app --host 127.0.0.1 --port 8765`，打开 `/docs`。用 `examples/new_world_request.json` 的结构创建 seed `20261113` 的世界，读取实际 `world_id`、`player_id` 与版本，用它们提交 `CHECKPOINT`，再读 state 和重试同一请求。基础 MOCK 当前可用同端口另行启动 `python -m uvicorn tools.mock_api:app --host 127.0.0.1 --port 8765`。评审页面可先校验 `examples/evaluation/` 的形状。

## 阻塞与公共接口变更请求

以下是接线前待确认的语义，优先沿用现有 v1 字段。若仍缺字段，由 C 与受影响岗位确认后同步 DTO、Schema、文档、样例和测试。

1. **单地图与区域字段 · C/D。** 当前协议仍有 region_id，现有样例按三个局部坐标区域组织。建议同一连续地图使用统一坐标，集市、翠林、月林作为地点。C/D 确认区域 ID 的具体兼容映射后同步文档和样例。D 提供地图尺寸、障碍、出发点、接收点与威胁位置。首个运输验收为同图起点至终点的实际移动、战斗和交付。迷雾由 D 绘制；若探索记录需要随存档保存，D/C 再约定最小数据。NPC 知情与事件来源由 C/B 按各自感知处理。
2. **战斗、交互与位置 · A/C/D。** HIT 自带双方格坐标，DialogueRequest 和 PICKUP 没有实时坐标。D 在对话、存档或拾取等需要最新位置的操作前按约定提交位置。A/C 统一近战距离、格心与到达容差、时间来源、attack_id 的生成与多目标含义。迷雾遮住或镜头外的角色，其执行归属需 A/C 对齐，确保每个角色由一方推进。
3. **行动目标与知识形状 · B/C。** `Intent.params`、`known_entities` 和 `memories` 内部结构在 DTO 中较宽松。先交一份可直接运行的 MOVE/GATHER 上下文和输出实例，约定目标 ID、动作参数、记忆 ID 和来源事件；交易与组织同意再按实际操作补例。B 的自由文本和 C 接受的结构化动作分别展示。
4. **评审写入和历史来源 · C/D。** 确认 D 在两轮冻结相同的客户端构建、地图、运行配置及观战输入约束。D 只通过会话流程启停，用活动世界提交真实执行事件；跨轮或回退后忽略旧响应。C 保留旧世界供审计读取，确认如何凭 `RunView.world_id` 和来源事件 ID 展开证据，并校验普通玩家视图与 `ALLOW_DEBUG` 的可见性。空成绩保持 `not_measured`，规则学习模式和实际 LLM 调用状态如实显示。

## 下一步

后续节点补充真实 HIT、死亡与物品归属，并将 WorldMemory 与 StoryThread 持久化接入已运行的世界服务，再接导演建议执行。地图位置由配置注入，模型由 callable 注入；后续组装者按 docs/WORLD_DIRECTOR_CONTRACT.md 接入。单地图区域映射和 B/C 输入输出语义记录为交接项，C 可先用清楚标注的测试替身开发本岗逻辑。每节点完成测试和启动验证后及时提交、推送并报告 commit。
