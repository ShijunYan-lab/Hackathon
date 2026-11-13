# 步骤 05—08 接入说明

本轮复用 v1 commands、dialogue、advance 和 AgentContext/AgentDecision。模型适配由 B 提供，实际移动、碰撞与任务报告由 A/D 提供。默认服务没有模型时返回 fallback；测试中的合成 provider 只用于验证链路。

## 05 物品

PICKUP/EQUIP 使用 actor_id、item_id；GIVE 再提供 target_id。操作角色必须存活；拾取与赠送距离为同图 2 格。装备仅接受本人持有的剑/斧。换装先移除旧装备护甲再加入新装备护甲，赠送当前装备会自动卸下。最终 stats 由后端计算，客户端原样使用。

生成器支持 sword/axe、iron/steel/bronze、common/uncommon/rare，以及最多两个 sharp/swift/warding 词缀。旧物品使用已存储的属性。规则变化用于以后生成的物品。

## 06 历史、记忆与剧情

新增 GET /v1/worlds/{world_id}/story，返回 data.memories 和 data.story_threads，均带 source_event_ids。默认 view=player，仅显示玩家可知来源。view=debug 与已有 agents/{npc_id}/debug 需 ALLOW_DEBUG=true，或 create_app(allow_debug=True)。玩家公开状态不含 NPC 私有记忆。

所有数据按 world_id 隔离，事件、摘要、见闻索引和线索同事务提交。旧事件启动时补齐索引并保持幂等。NPC 只获得 witness_ids 授予的事件；speech/info_shared 形成 report/unverified 记忆。重复根来源不当作独立证据累加。世界摘要使用结构化事件记录生成，当前采用确定性规则摘要。

被攻击角色产生开放线索，死亡后标记 abandoned；任务产生开放线索，实际成功为 resolved，失败/取消为 abandoned。旧事件保留。尚未执行的计划只显示为任务。

## 07 对话和任务

B 可实现 server/agents/service.py 的 dialogue/plan，或组装时用 create_app(dialogue_provider=..., plan_provider=...) 注入异步函数，签名沿用 INTEGRATION。C 提供本人库存、附近 6 格内的已知实体、近期事件和最多 12 条可检索记忆。单次模型调用含排队最多 8 秒，并发上限 2。调用在数据库事务外进行，回来后严格重验世界版本和生死。

当前 allowed_actions 为 WAIT、MOVE、GATHER、TRANSFER、SHARE_INFO。

| 意图 | target_id | params | 结果 |
| --- | --- | --- | --- |
| WAIT | 可为空 | 空对象 | 等待 |
| MOVE | 已知角色或资源点 ID | 空对象 | 可达性检查后创建 Task.kind=MOVE |
| GATHER | 已知且有存量的资源点 ID | 空对象 | 创建 MOVE 任务，到达后采集一份材料 |
| TRANSFER | 已知接收角色 ID | item_id | 按 GIVE 规则立即转交 |
| SHARE_INFO | 已知接收角色 ID | memory_id | 转述本人可检索记忆，接收方获得带根来源的 report 事件 |

未知动作、越权记忆、不可达地点、无资源或已有占用任务均拒绝并记录 decision_rejected。普通策略当前提供 caution，范围 0—1，单次修改幅度最多 0.25，必须引用本人可检索记忆。评审学习由后续专用版本通道处理。

POST dialogue 先校验双方存活、同图距离 2 格和当前战斗状态。相同 request_id 在途返回 REQUEST_IN_PROGRESS，完成后返回原响应。模型期间发生其他世界写入，返回 VERSION_CONFLICT，由 D 刷新后判断操作。失败及超时返回 WAIT 和 mode=fallback。对话原文以 speech 事件记录，NPC 记为转述。

TASK_REPORT 使用既有字段。成功报告必须到达目标同图坐标 0.75 格以内；失败必须提供 failure_code。C 检查任务归属和状态。GATHER 在成功到达时再次检查资源并实际扣除一份，生成带来源材料。原报告重试不重复结算；同任务不同终态报告返回 TASK_ALREADY_FINISHED。NPC 死亡时任务取消，后续报告不能恢复任务。

新世界若地图配置提供 sites，直接读取；否则为联调生成一个靠近出生点的五份草药资源点。正式位置由 D 在地图配置提供。现有世界保留原有资源点数据。

## 自测

python -m pytest tests/test_items.py tests/test_knowledge.py tests/test_agent_runtime.py -q

HTTP 实际服务已验证物品操作和 fallback 对话，MOVE/GATHER 的 provider 选策与结算用 TestClient 和合成 provider 验证。真实 LLM 和 Godot 仍需组装验收。

## 08 · 世界回合和世界导演

POST /v1/worlds/{world_id}/advance 复用 AdvanceRequest，reason 为 idle_timer、major_event、rest 或 debug_step，trigger_event_ids 只能引用本世界已存在事件。tick 只由此接口加一；同一原请求重试返回原结果。响应提供 tick、decision_summaries、tasks、events、state，并增加 director 的 mode/status/reason_code/accepted_proposals 摘要。REQUEST_IN_PROGRESS 时稍后重试原请求；VERSION_CONFLICT 时重新读取状态并判断是否发起新回合。

每回合至多选一个存活且无任务的 NPC，优先处理导演待评估队列，否则按 ID 轮转。NPC plan 仍只接收自己的 AgentContext；触发事件也裁剪到其可知集合。任务结算复用步骤 07。导演拥有本世界的事件、持久化世界记忆、剧情线索和配置地点；这些全局信息不传给普通 NPC。

导演默认每 3 回合评估一次；major_event 带合法触发事件可提前评估。create_app(director_provider=async_callable) 注入 B 的适配器，其签名为 async def provider(context: DirectorContext) -> DirectorDecision。配置读取 server/world/director_config.json，可通过 DIRECTOR_CONFIG_PATH 替换，第一次推进时冻结到该世界，重启后继续使用。locations 由正式地图提供；目前为空，不编造两村庄、森林、遗迹坐标。

当前只开放 FOLLOW_UP，执行目标为存活 NPC：产生有因果来源的 director_follow_up_queued，下一可用回合优先调用该 NPC 自身的 plan。重复排队、死亡目标以及组织/资源点目标会被执行校验拒绝，并留下 director_proposal_rejected。处理队列产生 director_follow_up_processed，含义仅为已尝试规划；实际任务仍须另行完成。死亡对象的排队记录取消并审计。RESOURCE_NEED/MIGRATION 执行器留至步骤 13，当前不加入 allowed_proposals。

导演摘要以 interpretation 标识存入事件和世界记忆，建议、校验结果、执行事件、队列状态持久化。GET /v1/worlds/{world_id}/director/debug（需要 ALLOW_DEBUG=true）返回 runs 与 focus；公开回合事件只包含玩家目击内容。导演私有记录不会自动进入 NPC 记忆。

NPC 模型和导演共用最多 2 个并发调用槽；单次模型至多 8 秒，推进中的模型等待总预算最多 12 秒。超时或模型未接入有明确 fallback 结果，推进仍可完成。模型调用全程在数据库事务外，提交时重新校验版本、存活和评审冻结状态。为后续评审预留 C 内部 turns.set_evaluation_active(world_id, bool)；开启后暂停普通 advance，不提供客户端覆盖入口。评审完整生命周期尚在步骤 10—12。

/health 的 component_modes 显示 NPC 和导演最近一次实际调用模式，未调用时为 fallback；整体 mode/model_connected 表示是否有组件最近成功调用适配器，各次响应仍以自己的 mode 为准。测试注入的 provider 仅为合成测试替身；真实模型质量尚未验收。

最小 HTTP 演示：python -m server.api.world_smoke。自动验证：python -m pytest tests/test_advance.py -q，包含降级/超时、非法来源、去重与重启、导演排队和私有上下文、评审冻结、并发过期结果、真实任务结算规则。脚本中的位置/报告为合成客户端输入，不代表已完成 Godot 联测。
