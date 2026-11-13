# B 模块：本地 NPC 认知与自学习沙盒

> **仅供开发验证**。本文件实现的“世界”“遭遇”“资源掉落”“HP”均为 B 的本地规则模拟替身，不是 A 的 Godot 战斗结果，不是 C 的权威世界状态，不得宣称为黑客松实测成绩。模拟器不会调用真实模型；`ask` 返回明确标注的 offline 规则答复。真实 LLM API 与 C 的函数接口属于下一阶段。

## 环境与启动

在已有 `Hackathon/` 根目录安装原项目依赖后：

```powershell
python -m server.agents.cli --seed 20261113
```

在命令行依次输入：

```text
world
npcs
ask 你知道遗迹吗？
# 配好本地 .env 后，可输入 asklive 你知道遗迹吗？
run woodcut
memory
profile
learn
profile
rerun
rollback
profile
spawn bandit
npcs
```

检查单元测试：

```powershell
python -m pytest tests/test_agents.py tests/test_learning.py -q
```

## 认知与自学习闭环

- `NPC`：身份、家庭、装备、当前状态、**私有** `memories`、`trust`、按情境索引的策略 `q` 和版本号。
- `Memory`：带事件来源和来源类型；自己亲见 `observation`，听别人说 `report`；听说不变成事实。
- `choose()`：相同算法用于全部 NPC，根据 `(goal,threat,hp_band)` 的离散情境选策略，同一 NPC 在不同村庄遇到类似危险也可检索已学到的策略；角色身份仍保留在个体属性中。**不读取 run_number。**
- `run()`：从 NPC 的地点出发，通过村间道路/遗迹或河流/森林路径完成砍树、采矿、交易、探索任务，模拟风险，形成实际模拟事件和反馈。
- `learn()`：只对实际尝试的策略按 `Q_new = Q_old + 0.8*(reward - Q_old)` 更新，并生成经验记忆。未尝试策略不被伪造为成功。
- `rerun()`：重置初始 HP、资源、位置、随机种子，**保留学习后状态**，调用同一个 `choose()`；不强制切换行为。
- `rollback()`：恢复学习前的 Q、记忆与版本，原审计日志仍在，旧 NPC 无法检索未来经验。
- `talk()`：同一区域的两名 NPC 可传递消息，受话人标记为 `report`，不会自动共享私人记忆。

## 本地世界范围

示例地图：东村、西村、道路、森林、河流、矿山、遗迹。五武器：战锤、弓、弩、短剑、法杖。角色类型示例：村民、商人、铁匠、守卫、强盗、野人。

这些地名、武器、资源属于 B **模拟器内部测试数据**，并不意味着共享 `shared/protocol.py` 已支持；实际游戏新增地区/武器及伤害规则需要 C/D/A 协调实现。

## 与真正 C 世界的大 Agent 分界

B 的生产函数继续遵循 `docs/INTEGRATION.md`：

- `dialogue(context, text)` / `plan(context, event_ids)` / `reflect(context, event_ids)`，输入 `AgentContext`，输出 `AgentDecision`。
- `choose_transport` / `learn_transport` 保持现有 `shared/evaluation_protocol.py` 的旧运输评审合同，不能私改。
- C 维护 WorldDirector 的全局资源、危险、血量、世界事件等，并向 B 传递 **该 NPC 真正已知** 的局部观察；C 权威结算，B 仅提出认知/行动/学习建议。
- 若拓展为多场景通用学习协议，请 C 提供经批准的 `SkillContext / ActionOutcome / LearningProfile` 等共享类型、事件来源与版本控制，先不要由 B 擅自更改 `shared/`。

## 已知限制

- 场景遇险概率和资源产出只用于本地策略单元测试；不是 Godot 命中、C 资源刷新或真实 NPC 自发行为。
- 旧版运输 `direct/escort` 仍是正式评审专项；本沙盒的 `shortcut/detour` **不是其替代实现**。
- `ask` 只用记忆规则；`asklive` 通过 `provider.py` 使用真实 LLM Chat Completions API（需要在本机配置 `.env` 和有效模型 ID），本交付未执行真实联网测试。尚未实现生产版 C 的 AgentDecision JSON 输出/校验。
- 复跑中不同行动路线消耗的随机抽样数量可能不同，不能据此宣称严格配对因果实验。
- 一次失败不保证第二次一定改善，应如实展示实际结果。
- 资源刷新、NPC 平时随机游走、交易/抢劫/战斗和世界大 Agent 将在 C/A 的实际系统中发生；本沙盒目前只展示任务中的随机遭遇及独立记忆。

## 可选的真实模型调用（本地 .env，不上传）

在仓库根目录从 `.env.example` 复制出 `.env`，并填：

```ini
LLM_BASE_URL=https://xlabapi.aitoken.credit/v1
LLM_API_KEY=
LLM_MODEL=
```

自行填入已授权的密钥与**平台实际支持的模型 ID**；该 URL 按 OpenAI 兼容 `/chat/completions` 请求测试，不能假定一定开放任何指定模型。启用后执行 `asklive 你怎么看遗迹`。Key 不会写入代码、回显到终端或写入日志。若 key 已公开过，先撤销并更换。
