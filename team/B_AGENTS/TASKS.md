# B｜NPC 对话、记忆与自动学习

## 你负责什么
你做 NPC 的认知：它知道什么、相信什么、打算怎么做；还要让它从第一次实际任务反馈里学到东西，第二次改变实际选择。

**工作分支：** `feature/b-agents`。
**可修改目录：** `server/agents/`、`server/prompts/`、`tests/test_agents.py`、`tests/test_learning.py`。另可更新本目录 STATUS.md。
**不要碰：** 不修改 SQLite、不直接修改物品/血量/组织关系、不替 C 打分、不改 shared 字段、不在 frontend 放 API Key。评审不要同时让普通 reflect 与 transport learner 两次改同一策略。

## 开工前读
- `AGENTS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/SETUP.md`
- `docs/INTEGRATION.md`
- `docs/EVOLUTION_REQUIREMENTS.md`
- `docs/EVALUATION_CONTRACT.md`
- `shared/protocol.py`
- `shared/evaluation_protocol.py`
- `examples/agent_decision.json`
- `examples/evaluation/profile_initial.json`

以上路径从仓库根目录算；不要把 docs/archive 旧手册当成新版任务。

## 任务清单

| 编号 | 优先级 | 你需要做的事 | 怎样算完成 |
|---|---|---|---|
| B01 | P0 | 接一个可用模型 API，统一 provider.py，读本地环境变量 | 能问中文并记录真实 model；不泄漏 key |
| B02 | P0 | 实现 service.py 中 dialogue/plan/reflect | 接 AgentContext，返回合格 AgentDecision |
| B03 | P0 | 只检索该 NPC 自己的经历；最近8条+相关4条先够用 | 未知秘密不凭空回答，转述不当事实 |
| B04 | P0 | 记忆提议带 source_event_ids；旧信念可被新证据修正 | 来源真实可查，不把同一谣言重复计证据 |
| B05 | P0 | 从 allowed_actions 选择一个意图与已有目标 ID | 无玩家命令也能提计划；不能直接宣称动作成功 |
| B06 | P0 | 非法 JSON 修复一次或 WAIT；超时明确 fallback | 不伪装成 live，不冻结世界 |
| B07 | P0 | 组织代表可同意/拒绝/提出条件 | 不是玩家一句话强制双方结盟 |
| BE1 | 新P0 | transport_learning.py 的 choose_transport | 当前合法动作和 Q 值决定，不能看运行次数 |
| BE2 | 新P0 | learn_transport：从真实 outcome 自动更新一个已执行策略 | 新旧值可核对，alpha不变；不替未试策略编造结果 |
| BE3 | 新P0 | 新增经验含来源run/event，完整 LearningUpdate 返回 C | 不能自己写库，C 可校验并保存整份profile |
| BE4 | 新P0 | 同一输入/结果单元测试、重复学习防护协作、回退可用测试 | 恢复V0时没有V1的进程内缓存或检索残留 |
| B08 | P1 | 简短 NPC 反思和编年史描述优化 | 只能总结已发生事件，不能编历史 |


## 第一轮交付与顺序
先用单个 JSON 上下文跑通 AgentDecision 校验；并把纯 Python 学习函数做成可测试模块，不等待地图。真实模型/API有问题时如实回退，仍保留学习规则的真实性。

## 预期代码位置
`server/agents/provider.py`、`service.py`、`memory.py`、`transport_learning.py`、`server/prompts/*.txt`、对应 tests。不要让学习函数依赖 Godot 或整套世界数据库。

## 和别人交接
交 C：`service.py` 三个 async 函数、`transport_learning.py` 两个纯函数、输入输出实例、单元测试。异常边界清楚。不要再开一个 B 专用 HTTP 服务。
共同字段和方法在 docs/INTEGRATION.md。自己的想法与协议冲突时找 C/D，不私自改。

## 怎么自测
运行 `python -m pytest tests/test_agents.py tests/test_learning.py -q`（文件由你实现）；真实 LLM 测试另标记是否实际调用，不能用固定回复混充。没有密钥时应跳过真实网络测试并说清。
公共基础检查：
```powershell
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
```
这些公共检查不能替代你自己的功能测试。尚未创建的岗位测试先实现，不能声称现成存在。

## 交付时更新 STATUS.md
记录完成项、修改文件、真实测试结果、未完成项和下一位同学需要怎样连接。
交付实际代码，不只把设计文字再输出一遍。未测Windows/Godot/LLM必须明说。
