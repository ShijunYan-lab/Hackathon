# B｜NPC 自主认知与学习交付

分支 `feature/b-agents`，基线提交 `4409d16`。本次代码在工作区，未提交或推送。

## 已交付

- `server/agents/cli.py`、`sandbox.py`：固定种子四场景 20 人开局，目标驱动移动、采集、返家、转述、有限资源、交战和交易测试替身；四类可执行任务与反馈学习。
- `provider.py`、`errors.py`：真实中文问答、异步 HTTP 调用、超时和并发限额、安全错误文本。
- `service.py`、`memory.py`、`server/prompts/npc_decision.txt`：生产 Python 入口、角色私有检索、来源和意图校验、修复一次、安全 WAIT 降级。
- `transport_learning.py`：基于共享 DTO 的纯函数 `choose_transport`、`learn_transport`。保留 `direct/escort`、原奖励、版本和来源。以结果版本和来源 run 校验重复学习。
- `tests/test_agents.py`、`tests/test_learning.py`：覆盖关键边界和复跑。

## Windows / hks 实测

- 当前本机使用 DeepSeek 官方接口的 `deepseek-flash`。按终端手册复测了开局回忆、受挑衅回应、回忆上一句玩家发言、石碑消息的转述归因，以及切换到西村角色后仅显示该角色的背景记忆。开局 20 名 NPC 各有带事件来源的背景记忆。回退恢复任务开始时可见的背景及对话记录。

- 固定 seed `20261113`，默认第 1 名 NPC 砍树：首轮走遗迹，取得 2 份木材，损血 17，奖励 0.260。已执行策略 Q 由 0.650 降到 0.338，v0 → v1。复跑走河边，取得 2 份木材，损血 0，奖励 0.870；`rollback` 恢复 v0 并保留审计。以上均为本地模拟。
- 切换 DeepSeek 前，使用赞助网关的 `gpt-6.1-sol` 验证手工 AgentContext 的 `dialogue`、`plan`（MOVE）、`reflect`（记忆提议）。当前 DeepSeek 的实机验证覆盖终端自由对话。
- B 定向测试 25 通过，全仓测试 59 通过（1 条 Starlette 依赖弃用警告）。基础及评审协议校验通过。20 名 NPC 的 `step 10` 产生 411 条本地事件，耗时约 3.4 ms，模型请求 0。
- 未实跑 C 的 HTTP 服务、Godot 或正式运输评审。

## C 接入

直接从 `server.agents.service` 导入 `dialogue(context, text)`、`plan(context, trigger_event_ids)`、`reflect(context, outcome_event_ids)`。三者接收 `AgentContext`、返回 `AgentDecision`。捕获 `server.agents.errors.AgentCallFailed` 后调用 `safe_fallback(context)`，由 HTTP 层记为 fallback。过期决策和事件可见性由 C 核验。示例可参照 `tests/test_agents.py`：

- 已知实体 `{"id":"mine","name":"矿山"}` 且 MOVE 合法时，NPC 可返回 `{"intent":{"action":"MOVE","target_id":"mine"}}`。
- 未知目标、未授权参数、私有证据或坏 JSON 连续两次失败时抛 `AgentCallFailed`。WAIT 合法时 fallback 提议 WAIT；死亡角色返回无行动。
- 记忆使用 `id/npc_id/statement/source_type/source_event_ids/confidence/status`。可附 `policy_version/entity_ids`。输入按旧到新；C 负责持久化、来源核验与已被修正记忆的状态更新。转述事件请附可见的 `facts.source_type=report` 和根来源 `facts.source_event_ids`。
- 通用学习的兼容约定待 C 确认：在 `identity.action_candidates` 提供 `action/target_id/params`，可附 `strategy_group/policy_key`，以便规划在同目标的合法候选中对照 Q。给 reflect 的可信 `agent_action_outcome` 事件需绑定本 NPC，facts 提供 `policy_key/reward/policy_version`。C 负责计算奖励、验证事件与版本、按结果事件幂等持久化。涉及多个结果时请逐个调用。共享 DTO 可后续明确上述字段和结构化记忆修订关系。
- 正式运输仅按 `transport_learning` 更新该 profile。C 执行两轮与回退并事务核验结果；同一个运输 profile 不应再通过普通 reflect 更新。

A/C/D 待确认生产四场景及区域 ID、20 人开局上限、五类武器的实际执行、对象与权限以及最终地图。B 沙盒动作和资源为测试数据。
