# 玩家与 NPC 公用组件（A V4）

`actor.gd` 负责外观、HP 表现、背包、金币、装备槽；`player.gd`、`npc.gd` 继承它。`npc_factory.gd` 接收动态人物数据实例化通用 NPC，不依赖写死角色名单。

十一件装备槽位：`melee`, `ranged`, `offhand`, `head`, `chest`, `hands`, `legs`, `boots`, `accessory`, `ring_1`, `ring_2`。武器种类：`sword`, `axe`, `hammer`（近战）和 `bow`, `crossbow`, `staff`（远程）。按 1/2 切换武器大类，示例用 Z/X 循环各类具体武器。

- `apply_actor_state(actor)`：生命、位置、死亡等公开世界数据。
- `apply_inventory_snapshot(items, equipped, coins)`：C 已确认的物品、装备 ID 和钱币快照。
- `inventory_for_ui()`：D 的背包/装备界面展示。
- `execute_task(task)`：移动、护卫、攻击、逃跑；真正 AI 意图由 B/C 生成并合法化。
- `hit_detected(payload)`、`task_reported(payload)`：D 转发给 C 的信号，A 本身不持久化数据库。

**重要：** 测试里的 `preview_*`、`receive_mock_loot`、`mock_drops()` 只属于离线模拟，不能在正式联网版写入真实世界。
