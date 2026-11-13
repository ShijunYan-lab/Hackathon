# B｜NPC 对话、记忆与自动学习 · 工作记录（本地补丁草稿）

分支：`feature/b-agents`（**未执行 Git push**）
本次完成：**独立终端测试沙盒**，不是生产 Agent 服务。

## 已完成并执行测试

- [x] 新增 `server/agents/sandbox.py`：独立 NPC 身份、住处、武器、私有记忆、转述/亲见标签、事件 ID 与策略 Q 版本；两个村庄/森林/河流/矿山/遗迹的简单测试数据。
- [x] 新增 `server/agents/cli.py`：在仓库根目录启动互动终端，`spawn/npcs/world/step/ask/asklive/talk/run/learn/rerun/rollback/profile/memory/events`。
- [x] 新增 `server/agents/provider.py`：通过 **本地 .env** 可配置 OpenAI 兼容 Chat Completions 的 `asklive`；仅在成功真实调用时才显示 live。
- [x] 新增 `tests/test_agents.py`、`tests/test_learning.py`，覆盖记忆隔离、谣言来源、通用角色、策略更新、回退、单次反馈不可重复学习、相似任务跨村复用、自治游走/资源刷新。
- [x] 编写 `server/agents/B_SANDBOX_README.md`，明确本地规则模拟不等于 C 权威结算和正式评测。

## 实测结果

- 运行 `python -m pytest tests/test_agents.py tests/test_learning.py -q`（结果以用户本地实际复测为准）。
- `python -m server.agents.cli --seed 20261113` 可交互模拟；首跑绕遗迹、收到失败反馈、学习后改选河边绕行、可回退。
- 运行 `python -m pytest tests -q`，**42 项通过**；`python -m tools.check_contracts` 和 `python -m tools.check_evaluation_contracts` 均通过格式校验（2026-11-13，本地容器）。
- **未测试** Windows 11、Godot 4.5.2、真实第三方模型 API、C 的真实服务或正式评审。

## 未完成 / 生产主线任务

- [ ] `server/agents/service.py`：符合 `shared/protocol.py` 的 `dialogue/plan/reflect` 三个函数及结构化 JSON 校验。
- [ ] `server/agents/memory.py`：从 C 的 `AgentContext` 检索、反思与信念修正；可保存的记忆提议。
- [ ] 原固定运输评审 `server/agents/transport_learning.py`：基于现有 `shared/evaluation_protocol.py` 做 direct/escort 两动作的纯函数学习，保持旧合同。
- [ ] 真实 `asklive` API 联网验证、失败降级与性能记录；不可把本地 offline 模拟当作 live。
- [ ] 与 C/A/D 实际联调、真实动作事件、伤害和资源来源。

## 对 C/D 的公共变更申请（尚未修改 shared）

- C + D：区域从原三场景扩展为两个村庄（小卖铺、铁匠铺、集市、酒馆、房屋）+道路+森林+河流+矿山零散资源点+遗迹；请确认动态 ID/地图和共享协议。
- A + C：武器扩展为战锤、弓箭、弩箭、短剑、法杖；请确认基础形态、攻击范围、弹药/法力、伤害结算实现范围。
- C：World Director（世界大 Agent）拥有全局状态和事件；B 只读取该 NPC 合法可知的信息、返回行动/学习提议。若允许跨场景通用 Contextual Bandit，需要新的通用学习数据契约；在确认前 B 不改 `shared/`。
- C：评审原 transport_v1 不应被本沙盒的 shortcut/detour 替换。新增玩法与固定双轮验收平行进行。
