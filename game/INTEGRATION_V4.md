# A 模块 V4 / 连续世界、武器分类、通用角色背包（团队对接单）

> 注意：本次补丁只涉及 `game/`，没有修改 B/C 的 Python 代码，也没有改 `shared/protocol.py`。
> `main.tscn` 目前进入 **A 离线模拟演示**，不是真实的多智能体游戏；D 完成主游戏后应替换演示场景的入口。
> 尚未在 Godot 4.5.2 运行实测；代码与素材经过静态自检，**F5 真机运行是合并前的必要步骤**。

## 1. 怎么试

Godot 4.5.2 Standard → 导入仓库内 `game/project.godot` → F5。

- WASD：移动；Shift：奔跑；Space：闪避；鼠标左键：攻击（朝鼠标方向）。
- **1：切换近战装备槽**（剑/斧/锤）；**2：切换远程装备槽**（弓/弩/法杖）。
- 为测试所有六种贴图，**Z：在背包内循环装备近战武器，X：循环装备远程武器**。正式游戏这两个动作应由 D 的背包装备 UI 通过 C 的 `EQUIP` 操作完成。
- E：与最近 NPC 交互，或拾取地上装备/钱袋（**MOCK**）。
- Tab / I：查看玩家背包；F：查看附近 NPC 背包；N：即时生成一名通用 NPC（**MOCK**）；R：重置测试。
- 商人等 NPC 会定时接收 **MOCK** 移动/护卫任务，尝试穿越森林、过桥前往其他区域。不会切换场景。

## 2. 主要文件

| 文件 | 职责 |
| --- | --- |
| `maps/seamless_world.tscn`、`seamless_world.gd` | 一张连续地图、碰撞、Camera2D 边界、A* 寻路接口 |
| `maps/overworld_data.json` | **唯一地图坐标/障碍约定**；世界宽 96×60 格，32px/格，统一 `region_id=overworld` |
| `actors/actor.gd` | 玩家/NPC 公用的血量、表现用背包、金币和 11 个装备槽 |
| `actors/player.gd` | 玩家移动、奔跑、闪避；1/2 两个武器栏；近战范围或远程射弹 |
| `actors/npc.gd` | 接收任务，A* 跨区域移动，NPC 装备与攻击；不调用 LLM |
| `actors/npc_factory.gd` | 根据数据动态生成通用 NPC 实体，无需按职业创建场景 |
| `actors/weapon_catalog.gd` | 六种武器贴图路径、攻击节奏、分类与测试默认数值 |
| `combat/projectile.gd` | 弓箭、弩箭、法术弹，碰撞后发送原有格式的 HIT 候选事件 |
| `items_loot_pickup.gd` | MOCK 地面战利品袋：装备、材料、钱币 |
| `ui/equipment_panel.gd` | 通用人物装备槽与背包只读面板（D 可以替换视觉） |
| `tests/a_open_world_demo.tscn` | 完整离线测试入口，含可击杀 NPC、掉钱、随机加入 NPC |

## 3. 装备与背包的数据约定

- 全部 Actor（玩家/NPC）共用 `inventory_items: Array[Dictionary]`、`coins: int`、`equipment_slots: Dictionary`、`active_weapon_slot`。
- `equipment_slots` 键：`melee`、`ranged`、`offhand`、`head`、`chest`、`hands`、`legs`、`boots`、`accessory`、`ring_1`、`ring_2`。**槽里只存 item_id**，物品实体仍在背包里，不创建复制品。
- `base_type` 是具体类型：`sword`/`axe`/`hammer` → `melee`；`bow`/`crossbow`/`staff` → `ranged`。
- 在主游戏中，D 应将 C 返回的 **角色拥有的完整 ItemState 列表**和 `equipment` 映射传入：
  `actor.apply_inventory_snapshot(items, equipment, coins)`；交互界面读取 `actor.inventory_for_ui()`。
- `player.equip_weapon(item_state)` 是前端显示适配入口；只有 C 确认 `EQUIP` 成功后才调用。模拟场中的 `preview_equip_item`/`preview_add_item`/`receive_mock_loot` 不能放进联网逻辑。
- 同一个 NPC 被击杀后，本地测试会把他的装备、草药等物品和金币放进**同一个战利品袋**。正式版掉落/所有权转移必须经 C 事务确认，不能把 `mock_drops()` 当真实事件。

## 4. A / D 交接（保持现有团队信号）

`hit_detected(payload)`：A 发给 D，字段仍是 `attack_id`, `attacker_id`, `target_id`, `weapon_id`, `region_id`, `attacker_tile`, `target_tile`。**远程射弹命中后同样只发一个 HIT**。

`interaction_requested(npc_id)`：D 打开自由输入框；`pickup_requested(loot_id)`：D 提交相应 PICKUP / 取钱事件。

`task_reported(payload)`：NPC MOVE/ESCORT/ATTACK/FLEE 完成或失败后交 C；`execute_task(task)` 可在同一大地图跨生物群系执行。

`apply_actor_state(actor)`：C 的生命与位置为权威；`apply_inventory_snapshot(...)` 只同步装备/物品可见状态；`set_controls_locked(true)` 在背包和对话时暂停玩家操作。

Godot 角色实际全局位置以**像素**表示；HTTP 中 `tile={x,y}` 为**世界格坐标**（允许 `.5` 表示格心）；转换方式 `pixel = tile*32`。不再发送场景切换操作。

## 5. 特别重要：C 端需要调整的协议（本补丁没有擅自修改）

当前 `shared/protocol.py` 的 `ItemState.base_type` 只允许 `sword`、`axe`、`material`、`consumable`。要想正式把更多武器写入后端，C 至少需要：

1. 增加 `hammer`、`bow`、`crossbow`、`staff` 和必要材料类别；验证装备槽合法性。
2. 给 `ActorState` 增加 `coins: int` 与 `equipment: dict[str,str]` 或等价统一角色装备快照（保留旧 `equipped_item_id` 作为兼容字段）。
3. 钱币掉落和拾取的事务：钱币可作为 `currency` 独立余额或带数量的特殊物品，**不能复制或出现负数**。
4. `HIT` 要校验真实装备归属、射击间隔和不同的近/远攻击范围，必要时追加带来源的 projectile_id / ammo 消耗；当前测试中射弹只验证客户端命中，不能代表真实 C 端验证成功。
5. 将世界的统一地理 ID 更新为 `overworld`，按 `maps/overworld_data.json` 的全局坐标与 `blocked_cells` 校验路径；原 `shared/regions.json` 的三个独立地图 ID 不能与新世界混用。双方约定后才升级共享协议。
6. NPC 可用同一 `NPC` 场景实例化，后端传 `id`、`name`、`appearance_key`、`tile`、装备、钱币、组织和目标；不需要创建每人专有 `.tscn`。

**请 C 和 D 在合并正式主线前确认以上 6 项。** 仅复制 A 补丁并不能让后端自动理解新世界坐标与武器。

## 6. B / C 如何设计动态 NPC 与 Agent 通信

建议世界初始按 `seed` 生成 5–8 个具名 NPC，之后依据资源、职业缺口、迁徙条件动态增加；42 小时演示版本限制同时活跃有名 NPC 约 12 名，技术上没有固定名单。

NPC 身份不是逐个手写：以 `身份/技能/性格/目标/所属组织/资源/初始记忆/外观` 为数据字段动态组合。怪物使用普通战斗逻辑，不需要逐个接 LLM。

- **近处、正在对话或面临重大抉择的 NPC**：B 使用 LLM，加载其有限、私有、可溯源记忆，输出结构化意图。
- **普通活跃 NPC**：C 用经济/任务/位置规则自动推进；需要重大决策再叫 B。
- **远处 NPC**：C 以世界回合推进位置和物资，不进行每帧移动与模型调用。

NPC 之间不直接互相发 Prompt。甲提出 `SHARE_INFO` / `TRADE` / `PROPOSE_RELATION` 等意图；C 检查双方存活、距离、通信渠道和权限，创建可溯源 `Event`，只把事件发给实际听到或收到消息的乙；B 在乙下次决策时读取它的私有记忆。玩家的谎话不会自动变成世界事实。

## 7. 本次未完成

- A 测试场景是 **MOCK**，没有连 B 的真实 Agent、C 的数据库；金币、背包/掉落、远程弹药与实际生死尚未服务端持久化。
- 装备的头部/胸甲/护腿/靴子/饰品暂是**结构和展示预留**，未制作每个装备的纸娃娃外观或真实后端护甲结算。
- 导航只能绕**静态地图障碍**，不含多人动态避让；未运行真实 Godot 4.5.2 引擎验证。正式演示前必须 F5 检查动画、射弹、CPU 消耗及路径任务。
