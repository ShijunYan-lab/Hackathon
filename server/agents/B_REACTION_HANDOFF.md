# B 辅助升级：事件驱动反应与社会状态提案（不改共享协议）

本补丁基于 `feature/b-agents` 上传时的代码，不替换原有 NPC 沙盒、LLM 适配器、`transport_learning` 或三大正式服务接口。
目标是先补齐紧急场景下的 **低延迟自主反应**，并为玩家辱骂、威胁、道歉等行为留出可验证的社会状态变化建议。
**仍非完成的 A/B/C/D 游戏闭环**。严禁把这里的离线测试视为真实 Godot 运行结果。

## 1. 已接通的入口（B）

- 原有 `async def plan(context, trigger_event_ids)` 在确认本 NPC 遭遇物理袭击时，优先调用 `event_reactions.propose_emergency_reaction`，不等待 LLM；普通计划仍用原 LLM。
- 角色胆量 `identity.traits.courage`、攻击倾向 `identity.traits.aggression` 均建议在 `[0,1]`。没有数值时暂用中文 `identity.personality` 的保守默认值。
- 低血量时优先逃跑；好战且健康时优先反击；其他情况下可以寻找守卫求助。**这只是紧急反应的低延迟策略，不替代 NPC 的高层 Agent。**
- 行动从 C 给的 `identity.action_candidates` 中逐条选取；没有合法可选动作时只提议 `WAIT`（若被允许），不假装动作已经执行。
- 受袭产生可追溯的本人记忆提议；B 不写数据库，不改变实际 HP、仇恨、关系、奖励。
- 生产记忆去重支持同源谣言多级转述（仅当 C 提供可核验的事件来源链），避免“很多人说”被误当作独立证据。
- `server/agents/social_feedback.py` 提供一个 **独立的纯函数** `assess_social_event(context,event_id)`，根据 C 已归类且直接指向本角色的社交事件生成信任、愤怒、恐惧、敌意的变化建议，**不会自动写回世界或 AgentContext**。这不是自由文本的准确情绪分类器，不能声称 B 已完成全部辱骂响应系统。

## 2. 给 C 的精确对接示例（须团队确认事件类型）

以下 event type 与 `reaction_role` 是本次补丁**提出的内部约定**，不是已经合入 `shared` 的标准。请 C 确认后统一生产事件映射，避免事件名称不一致。

**攻击：** C 在真正批准 HIT 或袭击并生成世界事件后，向受害 NPC 的 `context.known_events` 放入：

```json
{
  "id":"evt_hit_01", "event_seq":1, "tick":1,
  "type":"hit_confirmed", "actor_id":"player_01", "target_id":"npc_merchant",
  "facts":{"damage":6}, "caused_by":["cmd_hit_01"], "witness_ids":["npc_merchant"]
}
```

C 然后调用 `await plan(context,["evt_hit_01"])`。本模块识别以下 **已确认物理袭击**的事件名：`hit_confirmed`、`attack_confirmed`、`damage_taken`、`combat_hit`、`assault`。未经核验的 `rumor` / 普通对话文本不能触发该防卫捷径。

由 C 在 `context.identity` 附带准确的行动候选（示例参数需改成 C 自己真正支持的 Task 描述，不可直接相信前端）：

```json
{
  "personality":"谨慎克制，会先周旋",
  "traits":{"courage":0.25,"aggression":0.2},
  "hp":18, "max_hp":30,
  "action_candidates":[
    {"action":"FLEE","params":{"safe_tile":{"x":17,"y":12}},"reaction_role":"escape"},
    {"action":"ATTACK","target_id":"player_01","params":{"weapon_id":"item_sword"}},
    {"action":"SHARE_INFO","target_id":"npc_guard","params":{"topic":"seek_help"},"reaction_role":"seek_help"}
  ]
}
```

注意：共享 `Action` 枚举中没有 `SEEK_HELP` 或 `SPEAK`；当前以 `SHARE_INFO` 发出求助意图（只有守卫能响应且 C 批准时才成立），对话回复使用 `AgentDecision.reply`。不能未经商议自行在 B 新增公共枚举。

当没有 `identity.action_candidates` 字段时保留原有模型决策兼容方式；**若明确给出这个字段，即使是空数组，也不允许模型自己创造非 WAIT 的动作**。

**社会互动：** 玩家输入通过 D 送给 C，由 C 创建可见对话事件并负责判定/授权社交事件分类。只有这种 C 已确认事件才能让 `assess_social_event()` 返回状态变化提案，例如：

```json
{
  "id":"evt_insult_01", "event_seq":2, "tick":2,
  "type":"social_utterance", "actor_id":"player_01", "target_id":"npc_merchant",
  "facts":{"speech_act":"insult", "text":"你是个胆小鬼"},
  "caused_by":[], "witness_ids":["npc_merchant"]
}
```

支持的归类：`insult`, `threat`, `apology`, `thanks`，以及已确认的 `help_given` 事件。模糊、带反讽、引用别人的话、方言或上下文复杂的对话，仍需大模型/语义分类模块提供可信归类；当前模块**不会直接从任意中文文本准确识别侮辱**。

C 保存 `(npc_id,event_id)` 已应用标记，防止重复扣好感；对情绪和关系数值归一化/截断；在接下来的 `AgentContext.identity` 中提供最新状态供 B 的 LLM 决策。只有这条回写链路完成，玩家连续辱骂才会对 NPC 形成长期敌意。C 尚未完成前，本补丁只能计算提案，不能表示“游戏已实现持续仇恨”。

## 3. 给 A / D 的对接

- A 的 NPC 需要执行 C 实际下发的 `ATTACK`、`FLEE`、`MOVE` 和呼救相关任务；B 只有提案，没有瞬移、直接伤害或硬改仇恨。
- D 将玩家自然语言输入通过统一 HTTP 交给 C，不能把原始输入当作可执行指令，也不能在前端直接持久化情绪。
- NPC 之间的相互攻击按同一确认事件传播；有目击权的其他 NPC 可以做后续高层规划，但本次快速反击只对 **直接受袭 NPC** 起作用。
- A 的新版地图是连续 `overworld`；B 沙盒中 `east_village/west_village/forest/ruins` 是仅供单机演示的旧节点模拟，**请勿当成新版地图真实区域 ID**。NPC 位置和寻路由 C/A 联调。
- A 的武器槽及物品字段已扩展；B 沙盒中武器常量不等于 C 的正式装备协议。

## 4. 怎样自己跑

在 Python >=3.11 的项目根目录：

```powershell
python -m pytest tests/test_event_reactions.py tests/test_agents.py tests/test_learning.py -q
python -m pytest tests -q
python -m server.agents.reaction_demo
```

演示脚本使用 **模拟 C 事件**，不接 API Key，不做在线模型请求。现有自由对话仍由 `provider.py` 在有本地凭据时调用真实 LLM。改动后的测试数字以本地当次执行为准。

## 5. 尚待开发 / 不得误称完成

1. B 和 C 需要确认社会事件分类的可信来源、持久化关系图与情绪模型；目前只是数据提案，没有连续对话后的真实关系变化。
2. NPC 长期目标重排、求助后守卫是否接单、好友/同伴的反应，需要 C 的真实任务和组织规则。
3. Godot 里的 NPC 受袭 → C 批准 → B.plan → C 下发 → A 动画/寻路 → C 反馈 → B.reflect 还没有跑通。
4. 现有 `transport_learning` 的 Demo 本地有效，但正式同场景 V0/V1 两轮评测及回退需要 C 的后端完成。
5. 此次没有替 B 擅自修改 `shared`、`server/world`、`server/api`、`game` 或 D 的美术目录。
