# A 模块 V3：奔跑、闪避、攻击动画和剑/斧贴图 — 集成说明

更新时间：2026-11-13。这个包基于用户提供的 `UnwrittenRealm_A_Starter_v2(1).zip` 改造，已经按团队工作区的 `/v1` 协议整理。**尚未在 Godot 4.5.2 真机运行检查；仅能声明文件、图片与协议静态验证。**

## 现在新增的功能

- 玩家按住 **Shift + WASD** 奔跑。走路 `run`、奔跑 `sprint` 分别使用不同帧。
- **Space** 方向闪避：移动输入存在时朝对应方向，否则沿上次行进方向，短时冲刺和 850ms 冷却。
- **鼠标左键** 根据鼠标指向攻击。剑与斧拥有不同的 `cooldown_s`、`swing_ms` 和挥砍特效。
- `knight.png` 新增 `dodge` / `sprint` 预设帧；`attack` 有独立预设帧并配合武器 Tween。
- `actors/assets/weapons/sword.png` 和 `axe.png` 是两张独立生成的透明像素贴图，武器装备时会变更角色手中的外观，HUD 也会变。
- NPC 支持 `MOVE` / `ESCORT` / `ATTACK` / `FLEE` 的 Task 表现和任务结束回报；护卫会追击附近怪物，商人行为的原型由测试关卡发出 MOCK 任务。

## 与团队 4 块的对接

| 谁 | 调用什么 | 具体约束 |
|---|---|---|
| D → A | `player.apply_actor_state(actor)` / `npc.apply_actor_state(actor)` | `actor` 来自 C 的 `StateView.actors[]`，不可自行决定永久生死 |
| D → A | `npc.execute_task(task)` | `task` 来自 C 的 `Task`（`id`, `kind`, `target_tile`, `target_id`）；相同任务 ID 不重新开始 |
| D → A | `player.equip_weapon(item)` | `item` 是 C 的 `ItemState`，只读 `base_type` 与 `stats`，**不按品质重复增加攻击力** |
| A → D | `player.hit_detected(payload)` / `npc.hit_detected(payload)` | `payload` 直接与 `shared.protocol.HitPayload` 匹配；D 包装为 `/v1/worlds/{id}/commands` 的 `kind="HIT"` |
| A → D | `npc.task_reported(payload)` | `payload` 与 `TaskReportPayload` 匹配；D 包装为 `kind="TASK_REPORT"` |
| A → D | `player.interaction_requested(npc_id)` | D 展示真正的自然语言输入框并通过 C/B 获取对话 |
| D → A | `player.set_controls_locked(true/false)` | 对话框、背包、读档、评审演示时暂停战斗和移动输入 |
| D → A | `actor.collect_checkpoint()` | D 合并同区域所有角色位置交给 C；tile 坐标已经是格坐标（32px/格） |

**重要：** 用户上传的旧 A 原型曾使用 `COMBAT_HIT` / `START_DODGE` / `REPORT_INTENT` / `expected_revision`。这些不属于当前工作区 `/v1` CommandRequest。V3 的正式信号不再发送旧字段，不建议把旧的 `command_requested` 接进真实网络层。

**闪避与后端关系：** 当前闪避是客户端本地的物理动作与预设动画；MOCK 测试时通过 `is_dodging()` 忽略命中。`shared/protocol.py` 的 v1 命中接口尚没有服务端闪避状态，真实联调必须由 A/C/D 明确何时认定闪避成功，不能声称已经实现服务端权威无敌时间。

## 怎么把当前游戏跑起来

1. `Godot → Import → 选仓库内 game/project.godot`，使用团队约定的 4.5.2 Standard。
2. 按 F5，演示版 `game/main.tscn` 会实例化 A 测试关卡；或者选 `game/tests/a_combat_demo.tscn` 按 F6。
3. WASD、Shift、Space、鼠标左键、1/2、E、T、R。
4. 该测试场不使用后端；如果希望连接真正 NPC 决策，不要修改测试场的假 Agent 定时器，而应由 D 在地图中加载 `game/actors/npc.tscn` 并调用 `execute_task`。

## 和 D 模块发生冲突时

D 拥有 `game/main.tscn` / `project.godot`，A 拥有 `game/actors/`、`game/combat/` 和 `game/tests/`。当前提供的 `game/main.tscn` 仅用于空白 main 的临时演示。**若 D 已经写了正式 main，保留 D 的 main，按 F6 运行 A 的场景即可。** 不要复制替换 `game/project.godot`，本次没有修改引擎配置。

## 尚未实现，不得虚称

- B 的真实 LLM 决策、NPC 记忆和策略学习。
- C 的永久血量/死亡、装备所有权、真实交易和评审两次运行回退。
- 正式地图绕障碍导航（当前同图直线移动，受阻会上报失败）。
- 高质量商业级动作美术和完整客户端服务端交互回归。

正式演示需真实联调后再确认相应能力。
