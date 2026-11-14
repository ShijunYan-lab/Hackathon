# 大世界 Agent 与后续组装接口

当前提供可调用的 Python 边界、配置加载、触发判断、超时降级与建议校验。真实模型适配、世界持久化和建议执行仍待实现或组装。类型位于 `server/world/director.py`，可运行例子见 `tests/test_world_director.py`，其中模型输出和事件均为合成测试数据。

## 大世界如何发展

C 保存世界状态与按顺序发生的 Event。WorldMemory 保存带来源事件的历史摘要，StoryThread 保存尚在发展的矛盾或需求及其 open/resolved/abandoned 状态。剧情线索可从运输损失、组织变化或人物死亡中产生，解决状态以实际事件为依据。存档需要保存这些记录、随机数状态和导演上次执行的 tick；新世界分支只能读取本分支可见的历史。

WorldDirector 读取 C 提供的世界摘要、来源事件、世界记忆和剧情线索，提出后续关注方向。C 校验资源、存活、授权、地图位置和人口预算，再安排行动。实际执行产生新事件，后续再更新世界记忆和剧情线索。模型的语言摘要需保留来源，事实判断以事件账本为准。

例如药材运输损失被记入历史，导演建议关注商会缺货或允许新药师迁入。C 检查实际资源和迁入条件，通过后创建需求或新人物。人物的身份、目标和可执行能力交给已有角色与 NPC 系统处理。玩家后续帮助、拒绝或攻击都会继续产生事件。

## B 与 C 的模型接口

组装方将一个异步 callable 注入 `WorldDirector(config, provider)`。

```python
async def provider(context: DirectorContext) -> DirectorDecision:
    # B 的适配器通过已有模型调用器实现，并返回通过 DTO 校验的结果。
    ...
```

输入包含 state、events、memories、story_threads、locations、allowed_proposals。C 在调用前选择有限的相关记录并加载所引用的来源事件。该输入供世界导演使用；NPC 的 AgentContext 由独立的知情过滤生成。

输出包含 summary、source_event_ids、proposals。初期支持三类建议。

| kind | 含义 | 接入规则 |
| --- | --- | --- |
| FOLLOW_UP | 关注已有角色、组织或地点所关联的事件 | target_id 必须存在，后续行动复核存活与授权 |
| RESOURCE_NEED | 关注组织资源需求 | target_id 指向活跃组织，实际缺口由 C 的库存规则计算 |
| MIGRATION | 建议一个新人物进入世界 | location_id 指向配置中有 migration_entry 标签的地点，C 检查人口与具体生成条件 |

allowed_proposals 只包含已经接入执行器的类型。调用成功且结果合法时返回 mode=live、status=proposed；provider 必须仅在真实模型成功时正常返回，失败抛异常。无 provider、超时或故障返回明确的 fallback 和原因码。合成 provider 仅用于测试，测试结果不能作为实测运行记录。

## C 内部的调度与提交接口

```python
config = DirectorConfig.from_file("server/world/director_config.json")
director = WorldDirector(config, provider)
result = await director.assess(
    context,
    last_assessed_tick=last_tick,
    major_event=False,
    evaluation_active=False,
)
```

默认每 3 个世界回合或重要事件后调用一次，单次最多 8 秒、2 条建议、存活 NPC 上限 10。调度由现有 `/v1/worlds/{world_id}/advance` 的世界服务接入。调度服务负责全局 LLM 并发限制、合并触发与持久化上次调用 tick。

assess 在世界写锁外调用。返回的 world_id 与 expected_world_version 用于后续事务校验。提交方重验世界版本、当前任务及执行条件，原子保存决策记录、任务与事件，并用原请求 ID 去重。建议通过格式和引用校验后仍待世界规则审批。评审运行时 evaluation_active=True，导演跳过，以维护冻结的实验条件。

## D 与 C 的地图和展示接口

采用一张连续地图和统一格坐标。`director_config.json` 的 locations 留给组装方填入正式地图地点，默认空数组。每项包含 id、name、region_id、tile、tags。格大小沿用 32 像素；region_id 与 D 的正式地图描述一致。集市、翠林等名称作为地点显示名。地图几何与碰撞仍由 D 的地图配置提供。

迁入地点可加 migration_entry 标签，它表达允许进入世界的位置。C 再根据世界需求选择角色和物品来源。地点配置变更要进入世界存档及评审配置校验。

客户端通过现有 state 获取公开状态、events 获取玩家可知的编年史，commands 上报动作。导演全局记忆供后端使用。若界面需要新的剧情线索面板，再由 C/D 确认公开数据投影后扩展合同。迷雾绘制交 D，持久化探索记录的字段待其接线需求确认。

## 当前验证与待接入

`python -m pytest tests/test_world_director.py -q` 可验证边界行为。真实模型、SQLite 事件与记忆存储、故事线更新、建议执行器、HTTP advance 接线与 Godot 场景仍待完成。本轮接口可供后续组装者直接导入和配置。
