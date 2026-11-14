# C 岗完整任务与进度总表

## 最新交付：真实 LLM + Godot 生成与反馈演示

已在 `codex/c-journal-trade` 完成真实调用验收，未合入 main。操作入口见 [GENERATIVE_DEMO.md](GENERATIVE_DEMO.md)。运行 `powershell -NoProfile -ExecutionPolicy Bypass -File server/start_generative_demo.ps1` 打开本机已验证的实验世界；加 `-Replay` 创建新世界重跑。8781 实验端口，原服务不受影响。

实际完整重跑：五次 NPC 调用均 live；Godot 执行两次采集；模型生成“松纹旅木牌”（5 金币）→购买反馈→“月牙木牌”（3 金币），余额 20→15→12，两个物品真实归玩家。反馈经模型提炼为持久记忆；加载反馈前快照恢复第一件物品和余额 15，第二件物品及月牙反馈记忆均不存在。最新手札章节已记录第二次交货。初始站位由脚本设置作为演示布景，任务成功报告由真实 Godot 客户端产生。

修复：真实 NPC 调用默认超时从 8 秒的 provider 默认值调整为本机启动时 25 秒（允许环境显式覆盖）；保留少量模型提炼记忆的检索位置，避免被新观察全部挤掉；手札提示明确已结算交易覆盖旧对白。演示客户端读取外部对话生成的新状态，避免闲置客户端看不到新任务。

验证：164 项后端测试通过；完整真实脚本通过；脚本启动已验证。早期实测曾出现模型超时、版本冲突、客户端未读取外部任务，已记录并据此修复重跑。最新追加的自然中文手札提示仅完成编译检查，未专门重跑文风验收。

范围：这是生成、行动、交易、反馈适应、记忆、手札、存档恢复的完整例子，不是所有自由世界能力已完成；不宣称量化运输成绩提升。物品图像仍复用现有客户端表现，没有动态贴图或任意饮用/魔法效果。模型输出并非确定性，演示失败会显示实际错误。

## 当前开发方向修正：生成式世界（新分支，未合入 main）

用户明确后续修改留在 `codex/c-journal-trade`，暂不合入 main。当前手札纳入亲历对话、已有物品报价候选的修复尚在验证，不代表动态世界能力已完成。

生成式内容不是只能从预置商品和剧情中选择。下一切片需要 C 提供结构化世界变更提案：模型提出新物品/配方/约定及来源，C 校验来源、代价、权限、数量与可执行效果后落库；以“对话提出一杯酒→核验库存或生产条件→生成有来源的物品与报价→玩家接受→实际付款交货→持久记忆”为验收。不能在聊天中直接宣称已交付，也不能以增加固定酒水条目代替生成式链路。

接口变更建议：新增内容提案及验证/提交结果结构；B 提案而不写库，C 决定是否可实现与实际结算，D 展示报价、物品及失败原因。动态名称/描述不意味着可以执行任意代码；机械效果仍走可组合且经过验证的规则。具体协议待 C 实现后提供给 B/D，不私自重写 B/D 模块。

## 2026-11-14 本机整合游戏启动

- 新增 `server/start_game.ps1`：自动查找 Downloads 下的 Godot，使用 C 的 Python 3.11 环境及本机加密凭据启动正式整合后端，等待健康检查后打开游戏。支持 `-GodotPath`；遇到其他地图占用端口时拒绝启动，不自动杀进程。
- 在仓库根目录运行 `powershell -NoProfile -ExecutionPolicy Bypass -File server/start_game.ps1`。后端保持运行，存档为 `runtime/overworld.sqlite3`，接口页 http://127.0.0.1:8765/docs。
- 已实际验证正式服务健康（overworld，320×224，导演配置已加载），独立游戏窗口 `The Unwritten Realm (DEBUG)` 打开且响应，客户端启动日志无报错。本次未重新执行完整游戏流程或真实模型请求；配置已加载不等同于模型调用成功。
- 启动器针对本机已有环境；其他机器需先安装 Python 依赖、Godot 和本地模型凭据。未修改 D 的发布启动器。

岗位已认领，姓名待填写。分支 feature/c-world，跟踪 origin/feature/c-world。

**步骤 01—13 的最小 C 后端已交付（世界导演已通过 DeepSeek 实测，NPC 模型与正式游戏待联调）；步骤 14 的 Python 3.11、本机 Windows 构建和接口验证已完成。步骤 15 等待 A/B/D 真实组装，步骤 16 按用户最新要求先于团队联调制作。**

2026-11-14：Python 3.11.11 + requirements.txt 固定版本完整测试 103 passed；基础与评审协议检查通过。服务已使用项目独立 runtime/venv311 环境运行于 http://127.0.0.1:8765/docs，当前模型 fallback。可运行 server.api.world_smoke 和 server.api.evaluation_smoke 查看实际接口流程；脚本动作报告明确为合成输入。

## 固定任务清单

编号固定。C 后端验证和真实游戏组装分别记录，测试替身仅用于开发验证。

| 步骤 | 工作内容 | C 后端状态 | 游戏组装状态 | 完成后支持的效果 |
| --- | --- | --- | --- | --- |
| 01 | C 分支、GitHub 账号与提交记录 | 已完成 | 无需组装 | 查看每节点的提交与代码增量 |
| 02 | 服务、世界创建、状态、位置与事件持久化、请求去重 | 已完成 | 待 D 接入 | 创建世界、更新位置、重启后继续读取 |
| 03 | 世界导演接口、世界记忆和剧情线索结构、配置 | 已接步骤 08 运行流程 | 待真实模型接入 | 用明确的输入输出接模型，校验导演建议 |
| 04 | 攻击、伤害、死亡及死亡清理 | 后端已验证 | 待 A/D 接入 | 真实扣血、单目标去重、死亡掉落、任务取消、组织代表继任 |
| 05 | 物品归属、拾取、装备、赠送和装备生成 | 后端已验证 | 待 A/D 接入 | 物品流转、装备属性生效，物品只有一个持有人 |
| 06 | 世界历史、记忆、剧情线索和 NPC 知情范围 | 后端已验证 | 待 B/D 接入 | 查询历史来源，保存摘要与未解决线索，NPC 按自身经历知情 |
| 07 | NPC 对话、计划、任务执行及结果结算 | DeepSeek 联调适配器实测采集，B 正式实现待接 | 待 A/B/D 接入 | 计划生成任务，到达后才结算采集等效果 |
| 08 | 世界回合与导演运行流程 | DeepSeek 实测，命中入队并调用 NPC 完成规划 | 待 B/D 接入 | 推进世界、导演读取历史、排队 NPC 后续评估、全程可追溯 |
| 09 | 完整存档、加载与世界分支 | 后端已验证 | 待 D 接入 | 保存完整世界，从相同存档开独立分支 |
| 10 | 完整运输与评审会话 | 后端已验证，客户端报告为合成输入 | 待 A/B/D 接入 | 同图运输、付费雇护卫、到站/死亡/超时结算 |
| 11 | 首轮自动学习与新版本保存 | 后端已验证，当前规则 fallback | 待 B/D 接入 | 展示策略变化和来源，同一轮只学习一次 |
| 12 | 同条件二跑、成绩对比与完整回退 | 后端已验证，动作报告为合成输入 | 待 A/B/D 接入 | 展示实测交付率/费用/耗时，恢复初始策略、记忆与世界 |
| 13 | 组织、交易、资源、制造与合法迁入 | 最小后端已验证 | 待 B/D 接入 | 双方授权合作、真实交易制造、有来源的新人物迁入 |
| 14 | 稳定性、Python 3.11、Windows 构建与交接 | 本机目标环境与构建已验证，跨机器待测 | 待 C/D 联测 | 按说明冷启动、断线重试安全、目标机器运行 |
| 15 | 真实游戏组装验收 | 交接清单已提供，真实验收未完成 | 待 A/B/D 实现与组装 | 画面内验证战斗、自由对话、世界变化、两轮学习与回退 |
| 16 | 模拟游戏客户端的 Demo 网页 | 已实现并接真实后端，浏览器交互待验证 | 先于团队联调演示 | 可视化操作流程、世界变化、运行配置与响应效果 |

先完成 04—09 的基础与 10—12 的评审，再补齐 13。复杂经济、组织分裂与内容扩充为 P1。采用一张连续地图加迷雾，正式地图由 D 配置，角色执行由 A 提供，模型通过 B 的函数接入。用户最新反馈场景为 2 个村庄、1 个森林、1 个遗迹；按单地图中的四处地点预留配置，地点 ID、正式坐标、玩家出生点和运输起终点待 D 提供。现有 market 为临时兼容配置。

## 每节点交付规则

用户已授权每完成一个节点及时测试、启动验证、更新记录、commit、push 到 feature/c-world。

1. 完成节点代码、接口/配置和调用示例。
2. 测试正常操作、非法输入、重复请求、并发和相关失败情况。
3. 启动或重启服务，用 HTTP 验证实际行为。
4. 更新本表的 C 状态、组装状态、效果和限制。
5. 单独提交并推送，确认远程分支包含本地提交。
6. 向用户汇报步骤号、操作入口、实际效果、测试、提交链接和下一步。

## 步骤 16 · 后续 Demo 网页

用户最新要求调整为：完成 14 后先实施 16，再等待 15 团队联调。网页作为本地后端的可视化演示与接口联调客户端，供用户和组装同学查看操作流程、实际效果与配置。

- 展示一张地图中的两个村庄、森林和遗迹，以及角色位置、血量、物品、任务和事件变化。正式坐标来自地图配置。
- 通过既有 HTTP 接口操作世界创建、移动报告、攻击、拾取、对话、世界推进、存档与加载；以返回状态更新画面。
- 展示世界导演建议、世界记忆和剧情线索的来源，以及运输首轮、自动学习、第二轮对比和回退流程。
- 显示当前服务地址、运行模式、场景/规则配置、世界及策略版本、请求耗时、处理中状态与错误，方便观察流畅度和排查接口问题。配置以读取展示为基础，支持的修改仅在新建普通演示世界前使用后端明确提供的配置入口。
- 页面明确标注模拟客户端与合成动作报告；真实 Godot 验收单独记录。评审参数在首轮前冻结，分数从后端真实记录读取。
- 验收操作后页面与后端状态一致，重复点击或重试无重复结算，旧响应不会覆盖新状态，断线可恢复，加载/回退清理旧世界展示。完成后提供访问地址、使用步骤、测试结果和独立提交。

## 步骤 04 本轮记录

修改文件包括 server/world/combat.py、server/world/combat_rules.json、server/storage/sqlite.py、server/main.py、server/generation/initial_world.py、server/api/combat_smoke.py、tests/test_combat.py、docs/COMBAT_API.md、docs/BACKEND_QUICKSTART.md 和本记录。

### 实现效果

- 复用 v1 HIT，检查存活、同图、近战距离、障碍、武器归属与当前装备，按 max(1, weapon.damage - armor) 结算。
- 同 request_id 返回原响应；新请求 ID 重报相同命中返回 already_applied。同一挥刀允许多个目标，单目标去重；冷却、窗口、身份绑定和伤害快照持久化。
- NPC/怪物死亡保留档案，取消相关未完成任务、释放任务引用、原物品落地、移除组织成员、选存活代表或将空组织置为 inactive。
- 玩家倒下后恢复满血回到配置出生点，掉落按物品 ID 排序的一半材料（向上取整），保留武器和组织身份。
- 按同图距离近似记录目击者；后果生成带 caused_by 的事件。状态、事件、去重结果和冷却在同一事务中提交，失败全部回滚。
- 新建世界的 NPC 携带基础武器，已有世界沿用原物品。旧数据库通过新增表兼容；新世界创建时冻结战斗配置，旧世界首次成功命中时冻结。

### 默认配置与接入

近战距离 2 格、目击距离 6 格、材料损失比例 0.5，位于 server/world/combat_rules.json，可用 COMBAT_RULES_PATH 指定文件。这些是本轮实现默认值，供 A/D 联测对齐。后续目标须在首个合法命中后的武器 cooldown_s 内到达后端，过期返回 ATTACK_EXPIRED。

A/D 按 docs/COMBAT_API.md 发送真实碰撞报告，D 应用返回 state。32 像素一格。当前使用占位 market 平面，正式单地图及出生点由 D 提供。

### 测试与限制

Windows 现有 pytorch 环境（Python 3.10.14）运行 python -B -m pytest tests -q -p no:cacheprovider，71 项通过，新增 19 项战斗用例。覆盖正常/最小伤害、重复/并发命中、多目标、冷却/过期、非法输入、死亡/玩家恢复、任务/组织清理、事件来源、失败回滚、重启、旧世界与规则冻结。

Godot 碰撞、动画和真实 LLM 尚未联测。任务/材料测试通过临时数据库准备，报价系统待 13，任务报告和对话路由待 07。当前见闻按距离近似；位置报告来自可信客户端，后端验证地图与距离。网络延迟与挥刀窗口需 A/D 实测。Python 3.11 固定环境和第二台 Windows 待验证。

HTTP 合成命中演示已通过：世界 world_efa65d5a75ef432480fd2095a1b71510 中 NPC 经 7 次合法命中从 45 HP 降至 0，每次重复报告都未重复扣血，原武器掉落、组织成员移除通过。再次重启后死亡、原掉落、攻击去重与旧世界读取全部通过。该结果验证后端接口，Godot 联测仍待完成。

## 运行与查看

接口页面 http://127.0.0.1:8765/docs，服务状态 /health。

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
python -m server.api.combat_smoke
```

本机临时启动解释器为 C:/ProgramData/anaconda3/envs/weclone/python.exe。combat_smoke 创建独立世界、提交合成碰撞报告，通过真实 HTTP 检查扣血、死亡、去重、掉落与组织更新。输出 state/events 地址，记录到被 Git 忽略的 runtime/combat_demo.json。数据库为 runtime/worlds.sqlite3。

## 历史节点

| 提交 | 节点 | 已验证内容 |
| --- | --- | --- |
| da4a55a | 03 世界导演接口 | 全量 45 项测试通过，含 11 项合成 provider 测试；模型和建议执行待接入 |
| 2e53229 | 02 可运行基础服务 | 全量 52 项测试通过，9+6 份协议样例通过；HTTP 创建、移动、重试、重启保留通过 |

两提交已推送，当前仓库 GitHub 账号为 qirongbo。历史演示世界 world_a7a5702207904ce8872862debb59ccee 作为旧世界兼容检查对象。

## 下一步

步骤 04 验收并推送后，进入步骤 05 的 PICKUP、EQUIP、GIVE 和装备属性规则。每步继续更新同一张表；游戏组装状态按实际联测结果记录。

## 步骤 05 交付

PICKUP/EQUIP/GIVE 已接现有 commands，校验存活、距离和归属；装备护甲按旧装备移除再应用，赠送已装备武器会卸下。生成剑/斧、三种材料、品质和最多两个词缀。旧装备继续使用已有 stats。全量 74 项测试通过，HTTP 赠送、装备、重试验证通过（world_68706dcb97794a7a8841012c866b8ba9）。Godot 接入待 A/D。

## 步骤 06 交付

世界摘要、剧情线索、NPC 事件可见性和来源记忆已按 world_id 持久化。历史事件自动补索引；玩家 story 只返回其可知来源；调试入口受保护。任务实际结果推进线索状态，未试行动不记成功。全量 76 项测试通过，服务重启后既有战斗世界的摘要和死亡线索 HTTP 查询通过。新增 GET /v1/worlds/{id}/story（view=player/debug），B 记忆接口采用 server.storage.knowledge，真实 LLM 摘要待 B 接入。

## 步骤 07 交付

接入 dialogue 与 TASK_REPORT，校验上下文、记忆来源、策略幅度与意图；支持 WAIT/MOVE/GATHER/TRANSFER/SHARE_INFO。慢调用锁外执行、在途请求去重、回来重验版本。采集到达后才给材料，重复报告只结算一次。全量 80 项测试通过，真实 HTTP fallback 对话及重试通过（world_eef9c07dc8c5431ebaaf4fd57f13d304）。模型选策/任务执行链路使用明确标注的合成 provider 验证，B/A/D 后续组装。新接口与参数见 docs/WORLD_ACTIONS_CONTRACT.md。


## 步骤 08 本轮记录

修改 server/world/advance.py、server/world/agent_runtime.py、server/main.py、server/api/world_smoke.py、tests/test_advance.py、docs/WORLD_ACTIONS_CONTRACT.md、docs/BACKEND_QUICKSTART.md 和本记录。

- 增加 POST advance；每次最多一个 NPC 规划，tick 和 world_version 原子递增，重试返回原结果。在途请求去重，锁外调用模型，版本冲突拒绝旧结果。
- 导演从持久化历史、世界记忆与剧情线索读取背景，配置按世界冻结，默认每三回合运行。FOLLOW_UP 可排队存活 NPC 下一次评估；NPC 只用自身上下文，导演全局记录不授予普通 NPC。
- 导演摘要标注 interpretation，建议来源、拒绝、队列消费和死亡取消均可审计。组织目标、资源干预与迁入执行器未启用，留至 13；已处理评估不代表实际任务成功。
- NPC/导演共用并发上限 2，模型单次等待不超过 8 秒，推进模型等待总预算 12 秒。未接入和超时明确 fallback。C 评审生命周期可调用 set_evaluation_active 暂停普通 advance，完整评审仍待 10—12。
- 新增受 ALLOW_DEBUG 控制的 /director/debug；/health 列出能力和最近的各组件模式。服务默认无模型，当前为 fallback。

验证：Python 3.10.14 pytorch 环境完整 tests 为 85 passed；基础 9 项样例及评审 6 项样例格式检查通过，git diff --check 通过。新增回合测试涵盖重复/非法触发、持久化与重启、导演私有上下文和队列、超时与非法建议、评审冻结、模型期间并发更新，以及 GATHER 任务只在合法到达后发资源。provider 为明确的测试替身，不代表真实 LLM 已验收。

实际 HTTP：python -m server.api.world_smoke 在 8765 创建 world_ffdf684f74024656a64a661975791463；GIVE/EQUIP 生效、对话 fallback、三次回合推进到 tick=3、导演 PROVIDER_NOT_CONFIGURED、所有原请求重复返回一致、story 可读。再次重启后状态与 tick 保留，同 advance 请求仍返回原响应。脚本使用合成位置；真实角色动作和网络体验待 A/D。

交接：A/D 按既有 Task 执行后上报 TASK_REPORT；B 接 dialogue/plan 和 director_provider，签名与参数见 WORLD_ACTIONS_CONTRACT。D 提供一张地图中两村庄、森林、遗迹的 ID、坐标、出生点及资源配置。Python 3.11 固定环境、Godot 与真实模型未验证，列于 14/15。

本轮已推送的节点：05 e3ec8a3、06 a783fe6、07 ee90ca0；08 与本记录同一提交。用户无需中途介入。后续节点 09—15 仍按表推进，16 Demo 网页在原计划完成后实施。


## 步骤 09 本轮记录

新增 server/storage/snapshots.py、tests/test_snapshots.py，更新 server/main.py 和操作文档。POST /worlds/{id}/saves 保存完整边界，POST /saves/{id}/load 创建独立世界，原存档不覆盖。保存使 world_version 增一，让在途模型结果过期。快照含状态、地图、随机状态、任务效果与结算记录、物品、事件与因果、私人记忆/策略、导演配置/队列/审计和已完成请求；不复制在途模型租约。实体 ID 在分支中保留，world_id 隔离。部分挥刀不恢复有效命中窗口，冷却按存档相对时间恢复。SHA256 校验存档。

87 项测试通过：含两个独立分支、分支采集不影响原世界、完整记忆与 RNG、加载并发重试、重启、错误版本/ID复用/存档校验失败。真实 8765 HTTP 创建 save_cebe57cc32e34cafb8fe175464ba8a97，两次不同加载产生不同世界，原请求重试一致。测试未涉及 Godot 保存 UI。下一节点 10 复用快照做运输评审。


## 步骤 10 本轮记录

新增 server/evaluation/scenario.py、service.py、tests/test_transport.py，接入 main 路由与维护循环、WorldStore 命令前后事务钩子；评审暂停普通对话/存档/推进。会话冻结单地图地点、货物/金币/护卫费用/同意、敌人武器、损失/超时/成功阈值、S0/P0与代码hash。默认起终点为占位配置，待 D 对齐正式地图。首轮创建新的 S0 分支，真实扣款后发护卫 ESCORT 和商人 MOVE；A 执行，D 报 HIT/TASK_REPORT，C 算结果。命中去重沿用普通战斗，货物随实际命中减少；到站、死亡或超时只终结一次，迟到命令不能改成绩。报告不能提交自选分数。

全套 91 项测试通过。真实 8765 HTTP 创建会话、202 开跑、原请求去重、合成到达报告结算 10/10 交付通过。合成报告只验证后端，不代表实测游戏运输效果。B 模块尚未提供，选策使用明示 fallback 的合法策略 Q 值最大规则；步骤 11 继续接自动学习。实际 Godot 护卫/怪物动作待 A/D。


## 步骤 11 本轮记录

新增 C 的 evaluation/learning.py 校验与规则降级，接 learn_transport(profile, outcome) 纯函数；不修改 B 文件。自动后台学习与任务超时维护分开运行，模型等待在锁外；持久化租约和评审版本防止重复或过期提交。只改本次执行策略，验证 Q 更新公式、alpha、身份、上下文、来源、版本、完整旧记忆与检索 epoch。非法提议记原因后用公开规则 fallback，新增经验只陈述实际尝试。学习事件唯一提交，完整 profile 与差异持久化。

94 项测试通过。失败首轮 direct=0.6→0.12、escort=0.5 不变；成功首轮 direct→0.92，不强制换策略；重启不重复学习，非法改未执行策略被拒绝并审计。实际 HTTP evaluation_cee6012d4d814915965a99954a56cdc8 合成到达后自动 ready_for_second，值为 direct=0.92、escort=0.5。实际使用 fallback 规则，无真实 LLM。两轮对比/回退接着在 12 完成。


## 步骤 12 本轮记录

实现同 S0 二轮与原始成绩比较；冻结快照/场景/代码/适配器标识，变更拒绝继续，相同实测模式才允许比较。新增 rollback 和只读 profile 接口。回退恢复整个 P0（Q、版本、记忆、retrieval_epoch），创建新 S0，取消旧运行任务，保留审计；旧世界命令和在途学习不能改变新分支。rollback_check 重新走同一选策函数且不再学习。

97 项测试通过：含首轮超时后二轮同预算雇佣、角色/装备/位置恢复、交付率与费用同时展示、回退原策略和空经验、重启保持、延迟学习被回退作废、冻结条件变化拒绝。真实 HTTP evaluation_8088f53568e5401db97f0d85090f4a8c 的合成失败→自动学习→二轮合成到达→回退通过，active_profile 回到 V0。该输入仅验证接口，不作为 Godot 实际表现证据。完整用法见 docs/EVALUATION_BACKEND.md，演示 python -m server.api.evaluation_smoke。


## 步骤 13 接口增补建议（C 负责实现）

保留现有 ACCEPT_OFFER/JOIN_ORG/LEAVE_ORG 命令，新增 POST /offers、POST /craft 与 GET /economy；请求 DTO 放 shared/world_protocol.py，不改 A/D 已使用的字段。新增世界表（钱包、报价、冻结经济规则、资源需求、迁入来源）加入完整快照清单。PROPOSE_RELATION/RESPOND_PROPOSAL/CRAFT 等 B 意图复用同一规则，接入参数将在 WORLD_ECONOMY.md 明确。允许导演 RESOURCE_NEED/MIGRATION 需在事务内二次校验；迁入要求配置 migration_entry、可走位置、死亡来源未复用及人口上限。默认 locations 为空时无法迁入，待 D 提供正式地点配置。


## 步骤 13 本轮记录

新增 shared/world_protocol.py、server/world/economy.py、director_execution.py、tests/test_economy.py、WORLD_ECONOMY.md；接入已有命令、B 意图、导演和快照。报价不等于成交：接受时二次检查双方、代表、过期、库存与资金，原子付款转移；入会需邀请，退出维护代表。制造实际消耗材料并产生可装备铁剑。新开发世界提供铁、木、药草资源点，已有世界不重生资源。导演需求只建待办，迁入受有效入口、死亡来源唯一使用、人口上限约束；生成新身份，原死人不复活。钱包与报价等全部纳入快照；评审护卫费同步实际钱包。

103 项自动测试通过，基础与评审协议检查通过。新增覆盖并发交易去重、余额不足无部分执行、错误接受者、双边关系与邀请、代表退出、材料消耗与装备、分支经济快照、无死亡来源拒绝迁入/有来源新身份/来源不重复、非法模型价格安全拒绝。真实 HTTP world_e04d2ca1a58142e2bc15af50c35be9f8 完成 7 金币交易与重试，卖方 20→27，买方 20→13，物品归属改变一次。

限制与接入：D 提供正式地点及 migration_entry；默认 locations 为空，不能迁入。组织需求自动采购/履约、复杂经济/组织分裂仍为扩展。药草包目前仅制造，未实现使用效果。A/D 与 B 按 WORLD_ECONOMY.md 接入，未做真实游戏联测。下一步 14 目标环境与交接包。


## 步骤 14 本轮记录（2026-11-14）

已在项目 runtime 中安装独立 Python 3.11.11，不修改系统 Python。requirements.txt 固定依赖安装成功，103 项测试通过，基础 9 项及评审 6 项样例检查通过；有一条 Starlette/AnyIO 弃用提示，无失败。测试覆盖同请求并发、重复命中/任务/学习、事务回滚、版本冲突、模型期间世界变化、回退作废旧结果、存档分支及重启。实际 HTTP 额外验证收到响应头后丢弃响应体、再用原 request_id 重试仍返回同一世界。

新增 server/launch.py（源码和 EXE 统一启动，数据库在外部可写路径）、server/build_backend.py（白名单源码包和 SHA256 清单）、server/package_windows.py（独立时间戳目录，不覆盖旧数据）与 requirements-build.txt。PyInstaller 6.22.3 在本机 Windows 构建成功；EXE 独立启动 8766、世界操作、运输自动学习/两轮/回退与重启数据保留通过。最终包路径/哈希记于 C_BACKEND_HANDOFF.md。二进制及本地数据库按仓库约定不入 Git；构建代码与交接说明入 Git。

8765 当前使用 Python 3.11 独立环境，四个 HTTP smoke 均通过：基础位置、8 次合成命中死亡与去重、物品/对话/三个回合、运输两轮与完整回退。近期样例世界 world_cf5f277a470a48c0b5df1e2f17db966a（死亡）及 world_c247eb22b67d44889723f89091ca38b9（世界流程），评审 evaluation_d60d828ffc3d4f2f912f07a11ca51e60（已回退）。

限制：仅本机 Windows 验证，未在第二台干净 Windows 机器运行；没有真实 LLM、Godot 碰撞与实际运输表现验收。构建包当前提供 fallback 模式，B 模块和正式提示词接入后需重新打包验证。复杂经济和组织分裂不在本阶段范围。

## 步骤 15/16 交接边界

检查当前分支 game 目录，actors/combat/controllers/net/ui/maps 仍是占位说明，没有可供组装验收的真实脚本。真实游戏验收依赖 A 的角色和任务执行、B 的模型适配器、D 的 HTTP/UI/正式单地图。C 未跨岗改写这些文件，已在 docs/C_BACKEND_HANDOFF.md 列出接口、操作、验收顺序和待联测事项。步骤 15 不标完成；用户最新调整：完成 14 后先做 16 演示网页，再进行 15 团队联调。

本轮节点提交：09 317ebb6；10 614e850；11 a8e7258；12 e841376；13 a197b12；14 与本记录同一提交。每节点均完成对应测试、HTTP 验证并独立推送 feature/c-world。


## 步骤 16 · 本地演示网页

按用户最新授权提前到 15 之前。新增 server/api/demo 的 HTML/CSS/JS，挂载 /demo/，与真实后端同源。提供地图示意与人物、回合、战斗、对话、物品、任务到达/失败、世界记忆、存档分支、运输首轮/自动学习/第二轮/回退、策略和成绩、模式与请求耗时/错误。按钮写操作串行；网络结果不确定时保留原请求重试；业务错误不盲目重复提交。动态文字转义。场景四处地点、迷雾和客户端动作明确标注为模拟，不冒充 Godot。

新增页面资源与 API 同源测试，JavaScript 语法检查通过，HTTP /demo/ 返回 200。当前聊天 CUA 工具报告 Local browser access is unavailable，未完成可视化截图及浏览器点击验收；不能把网页交互标为已实测。104 项后端/页面资源测试结果见本轮交付。步骤 15 仍待真实 A/B/D 联调。入口 http://127.0.0.1:8765/demo/。


## Demo 修复：评审轮询闪烁与操作指引

用户报告建立评审后界面闪烁、按钮难以操作。原因是 1.5 秒轮询调用 action(refresh)，每次都会禁用所有按钮并重绘多个区域。现改为仅在运行/学习阶段静默轮询会话，未变化不绘制，防重入且丢弃切换世界后的旧响应；ready/complete/rolled_back 停止轮询。新增中文阶段、操作说明、中心区域下一步按钮，按阶段禁用不适用的操作，明确模拟任务需手动报告，45 秒未完成会超时。

验证：Node 前端逻辑测试通过（ready 不轮询、按钮状态、未变数据不重绘、单在途、过期响应隔离）；11 项页面/运输/学习/回退测试通过；JavaScript 语法检查通过。页面脚本版本参数更新，刷新浏览器即可生效。尚未补做真实浏览器视觉验收。

## 步骤 06、08、13、16 · 世界导演与长局数据

本轮修改 C 所有权文件：server/world/model_gateway.py、director.py、director_context.py、director_execution.py、advance.py、agent_runtime.py、economy.py、tasks.py、server/storage/knowledge.py、server/main.py、shared/world_protocol.py；增加相关后端测试、模型启动脚本、API 文档和 Demo 导演面板。
接口增量：RESOURCE_NEED 新增 resource/quantity、MIGRATION 新增 npc_name；POST /v1/worlds/{id}/supply 按实际物品交付，保持旧字段默认兼容。模型只建议，C 校验来源、人口、地点、真实库存、版本和请求去重后执行。正式地图仍由 D 提供。

- Windows 当前账户可用 `pwsh -NoProfile -File server/start_world_model.ps1 -DebugViews` 启动 DeepSeek 导演。默认只监听本机。凭据保存在忽略的 runtime/director-key.dpapi，换机器或账户需重新安全输入。进入 /demo/ 创建世界并推进三次，查看导演模式、摘要来源和执行记录。B 的 NPC provider 和 D 的正式地点、迁入入口仍待组装。
- 真实 DeepSeek 普通评估约 3.8 秒返回有来源的摘要。最新版本实际 HTTP 模拟命中触发评估约 3.2 秒，引用命中事件，对受击 NPC 的 FOLLOW_UP 被接受并入队。同 ID 重试返回原响应。B 的实际规划与行动尚待联调。需求、迁入、材料履约和剧情线索闭合由后端测试替身验证。
- CHECKPOINT 只更新当前位置，最近 64 次保留原响应。历史旧记录继续可读。导演按近期事实、未解决线索、记忆和需求读取来源；NPC 读取自身最近 8 个事件和最多 12 条记忆，记忆来源最多 24 个。模型上下文超过 96 KiB 时进入 fallback。战斗、剧情、任务等实际历史及人工存档仍会增长，长期归档另行设计。
- Python 3.11 完整测试 111 项通过，Node Demo 回归通过。1,000 次位置同步后仍只有 1 条初始事件、1 条初始记忆、64 条位置重试响应。涉及 storage/sqlite.py、storage/snapshots.py、storage/knowledge.py、world/advance.py、world/agent_runtime.py 和 API 合同。正式 Godot 移动、联调和 Windows 新包尚未验证。

## 步骤 07、08、14、16 · NPC 跟进和长期运行复查

- 导演跟进把 NPC 已知的来源交给规划器；超时保留队列并重试，死亡取消，成功规划才完成队列。导演和 NPC 可在同一请求内并行评估同一份快照，事务内检查版本。
- 真 DeepSeek HTTP 实测两条流程。模拟命中触发导演建议并成功入队，下一回合 NPC 真实返回规划，本次未建任务。另一次自由对话触发采集，模拟抵达之前库存未增加，抵达之后实际发放一份药草。正式 Godot 执行和 B 学习仍待步骤 15。
- 长期运行复查：不再为跳过的导演回合写评估行，NPC 回退空转不创建决策记录；内部回合和审计记录不再派生世界记忆。剧情和导演调试响应有限额。导演请求只携带未完成任务，长线索取首条和最近七条来源，完整来源仍在库内。
- 仍增长的表包括有效事件、完成的任务、请求去重与手动存档。旧存档和正式审计保留。长期归档与分段快照需要独立验证去重、旧分支、运输评审来源和回退，再实施。
- 文件：server/world/{advance,agent_runtime,director_context,model_gateway}.py、server/storage/knowledge.py、server/main.py、server/start_world_model.ps1、server/api/director_smoke.py、Demo 页面、WORLD_ACTIONS_CONTRACT.md 与 tests/test_advance.py。Python 3.11 测试 112 项通过，Node Demo 回归通过。

## 步骤 06、08、09、16 · 玩家章节与自动推进

新增章节存储、可分页玩家章节接口、DeepSeek 写作入口和导演历史回忆；存档分支保留章节与来源。按亲历转折事件生成，不把全局导演私有摘要交给玩家或 NPC。回忆优先留开篇并按人物、重要性和时间选择章节，相关旧事件可以跨过近期窗口。章节是解释文本，事件用于裁决。

Demo 默认每 20 秒自动推进，报告命中后提前评估，可关闭自动并手动调试。正式 Godot 定时器仍由 D 组装。涉及 server/world/{chronicle,advance,director,director_context,model_gateway,tasks}.py、server/main.py、server/storage/snapshots.py、Demo 和测试。

真实 DeepSeek 验证：同种子模拟命中与药草采集写出不同章节；最终采集正文与实际材料及数量相符。一次命中导演评估接受 1 条跟进。章回分页、老证据保留、玩家知情约束、重复请求、加载分支及自动定时器暂停均有回归检查。114 项 Python 测试和 Node Demo 回归通过。

导演先独立校验摘要和每条建议。部分有效时记录 PARTIAL_DECISION，保留有效内容；正常无行动记录 NO_ACTION_PROPOSED。无效 ID、地点、目标或格式显示对应 issues。旧审计中的 INVALID_DECISION 原样保留。

## 步骤 08、16 · 模型超时恢复

本机审计确认回合 2 的 MODEL_TIMEOUT 是响应超时。导演在同回合优先取得共享模型槽，输出预算从 1200 降到 750，普通新世界配置给导演 9 秒预算，已冻结世界沿用其预算。暂时性超时或连接错误会保留原始触发事件，下一回合提前重试一次；Demo 空闲约 4 秒自动推进重试。真实 HTTP 实测首次超时、下一回合使用同一事件恢复 live，并接受一个跟进建议。115 项 Python 测试和 Node Demo 回归通过。

## main 整合后 C 修正

基线 1e2d84c。使用 Windows 本机命令 `pwsh -NoProfile -File server/start_world_model.ps1 -Integrated -NpcDemo` 走正式地图入口；-NpcDemo 在这个模式下把同一 DeepSeek 模型凭据传给 B，省略则使用 B 的独立配置。支持 -Port 和 -Db，验证实例使用独立数据库。

C 给已获知补给需求、携带正确材料且靠近组织代表的 NPC 提供合法 TRANSFER 候选。导演只从事件读取装备后果，避免每轮加载全地图库存清单。正式地图 HTTP 实测 B 自由对话 live；裁剪后导演 live 返回暂无新行动。真实 Godot 两轮运输及回退继续联调。

## 生成式世界第一切片：动态加工与交易

- 修改 shared/protocol.py：AgentDecision 新增可选 creation_proposal（名称、描述、材料实例 ID、来源事件、报价），旧调用兼容。B 现有 service 从该类型生成 JSON Schema；C 在 identity.creation_rules 给出能力边界，未修改 B 文件。
- 新增 server/world/creation.py，复用决策保存点和交易结算。只允许消耗本人实际持有的材料；动态生成普通物品并建立报价，不自动扣玩家金币。新内容及材料来源写入事件，可进入手札、记忆检索与现有存档。
- 当前不能把描述变成任意机械效果。普通加工立即完成；酿造等待、动态任务、动态配方保存、饮用效果与场景变更仍未实现。材料是否符合描述目前依赖模型指令，尚无完整材料性质验证器，不应宣称任意生成内容均物理合理。
- 修复手札忽略所有对话的问题：只纳入玩家亲自参与的非空对话，保留知情隔离与每批 12 条上限。未改 D 界面。
- 新增 tests/test_creation.py，通过 TestClient 验证动态名称、原料消耗、报价、真实付款与交货、重复请求、缺料拒绝；模型使用明确的测试替身。真实 DeepSeek 生成和 Godot 完整交互尚未验证，当前运行中的服务未自动切换至此实验版本。
- 接入：对话返回 creation_proposal 时 intent 为空或 WAIT；创建成功仍需调用现有 ACCEPT_OFFER，不能把报价当成交。D 可读取 content_created 事件的 description、ingredient_ids、mechanical_effects；目前机械效果为空。
- 本次完整后端回归：164 passed（31.91 秒）；未进行真实模型或游戏窗口验收。
