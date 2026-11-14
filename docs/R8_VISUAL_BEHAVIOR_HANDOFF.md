# R8 视觉与怪物行为对接说明

## 已实现文件和接口

| 功能 | 代码与资源 | 对接要求 |
|---|---|---|
| 所有物品图标 | `game/assets/item_art.gd`, `game/assets/r7/*.png` | 输入真实 `ItemState` 字典（base_type、material_id、quality、name）；新增物品在 `item_key()` 映射 |
| 地面掉落 | `game/maps/world_item.gd` | 只绘制，不修改世界物品归属 |
| 资源与告示 | `game/maps/world_resource.gd` | 从后端 `StateView.sites`, `StateView.notices` 读取，枯竭由 remaining 判断 |
| 宝箱与商人容器 | `game/maps/world_container.gd` | 从后端容器得到 kind/quality/opened；不能客户端创造奖励 |
| 地图装饰 | `game/maps/world_prop.gd`, `game/maps/scene_props.json` | 23 个只读世界地点提示；E 查看，无物品奖励，不占后端实体 ID |
| 守卫动画 | `game/maps/network_npc.gd`, `game/assets/r7/guard_*.png` | 5 种守卫，每种待机 3、行走 4、攻击 5、死亡 4；角色帧 48×64 |
| 生物动画 | `game/assets/r7/animations/*.png`, `game/maps/network_npc.gd` | 12 种普通/精英怪 + 5 种敌对人类外观，动作代理图 80×80；后续可替换独立 PNG |
| 怪物生态 | `server/world/monster_ecology.py` | 12 个物种条目，视觉 key/HP/护甲/伤害/冷却；R7 `living_world` 和 `continuity` 使用该注册表 |

## 关键逻辑

- **外观 key**：`wolf`, `boar`, `spider`, `ghoul`, `swamp`, `raven`, `wisp`, `hostile_0`...`hostile_4`, `elite_<species>`，守卫 `guard_0`...`guard_4`。
- **生物动画资源**：普通怪 `wolf`→`r7/animations/wolf_0_<action>_<frame>.png`；精英怪 `elite_wolf`→`wolf_1`；敌对人类按 `hostile_<index>`。
- **守卫独立动作帧**：`guard_0_0_0.png`（待机第 0 帧）等，四行映射 `idle/run/attack/death`。这是用户素材已抽出的真正独立 PNG，而非合并图。
- **地图坐标**：场景物件配置的 tile 需在 `320×224` 地图内；世界坐标 `tile*32px`。
- **后端仍是唯一事实来源**：客户端根据目标计算可视移动/攻击提案；服务器 HIT 负责真实伤害，不能在 Godot 本地增加物品或金币。
- **安全区**：怪物生成端由 `continuity.inside_safe` 筛查，Godot 客户端追击时也不主动选择安全区内人物为目标（城镇围攻事件仍可能另有规则）。
- **当前限制**：单帧立绘生成的代理动作不足以表现挥剑换姿/复杂 AI；完整人类对话、武器损坏、组织关系等继续由 B/C 端负责。场景物件尚非独立动态可开关交互系统。

## 目前未验证的部分

当前环境**没有 Godot Linux 可执行程序，也不能运行打包内的 Windows Godot**。只能做 Python/API/PNG 和脚本文本检查；必须在 D 的 Windows + Godot 4.5.2 环境里做首次导入、F5、动画、碰撞、商店和存档验收。不要将 Python 测试成功等价为游戏引擎已经可以无报错启动。
