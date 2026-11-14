# D 的连续探索地图 · V2

Godot **4.5.2 Standard / Compatibility** 打开 `game/project.godot`，F5 运行联网大地图，必要时自动启动本地后端。入口 `network_main.gd`，A/B/C 接入说明见 [当前交付](../../release/MERGE_BC_INTEGRATION.md)。`backend_world.json` 使用唯一 `overworld` 全局坐标。以下 V2 地图、美术和旧分区说明保留作为布局记录；离线预览另见 `offline_preview.tscn`。

当前联网层使用世界碰撞 layer 1、角色 layer 2；玩家/NPC 脚部碰撞半径 10px、mask 3。NPC 按各自职业住处分布，完整说明见 [真实对话与交互更新](../../release/LIVE_NPC_UPDATE.md)。下方离线 V2 的替身、旧碰撞层和本地对白说明仅供历史参考。

## 当前地图

320×224 格，每格 32px，世界 10240×7168px，是上一版 160×112 的 **4 倍面积**。800×450 内部视口，默认 1600×900 整数放大。

灰橡镇、鸦渡镇各有 12 座服务/住宅建筑；北桥、南桥构成独立村间路线，西侧另有农田环路。包括自己的家、铁匠铺、酒馆、集市、仓库、教堂、磨坊、农田、果园、码头和船。森林道路止于林缘，内部不铺路；有密林、湖泊、猎营、暮钟修道院、断誓堡、寂鸦墓园等环境。

71,680 个地形格，7,369 个环境对象，15 个 NPC 实例，男女两种玩家外观。所有人物单帧 48×64。村庄 NPC 分布在两镇与渡口，森林/遗迹各五人。

**所有区域全屏可见，不创建圆形视野、战争迷雾或视线遮罩。** 保留树冠 Y 排序与近处淡化，角色经过树下仍可辨认。四面 StaticBody2D 空气墙加角色坐标防越界；水面不可步行，桥梁、码头可走。

操作：WASD / 方向键移动，Shift 奔跑，E 交谈/查看地点，M 地图，V 切换男女，Esc 关闭。对话支持自由中文文本、Enter/发送按钮、三个快捷话题，显示“离线对话”。回复目前来自每个 NPC 独立编写的本地内容，未接 LLM/HTTP；输入框支持中文，但本轮只自动验证中文字符串提交，没有手动验证 Windows 输入法候选窗口。

## 编辑与重建

主入口 `main.tscn → realm_main.gd`；地图 `realm.tscn` 的 Terrain 为原生 TileMapLayer，SoftTerrainEdges 为过渡层，Entities 中屋舍/树木/物件可单独编辑，InvisibleMapBoundary 为空气墙。NPC 在主入口按 catalog 生成。

构图源 `realm_layout_v2.gd`，`world_layout.gd` 维持既有引用入口。固定种子只用于植被、碎石等摆放。生成结果已经保存，正常 F5 不需要先运行生成器。

在仓库根目录运行；godot 替换成本机可执行文件：

```powershell
godot --headless --path game --script res://assets/build_reference_actors.gd
godot --headless --path game --script res://assets/build_environment.gd
godot --headless --editor --path game --import
godot --headless --path game --script res://maps/bake_world.gd
godot --headless --editor --path game --import
```

重建会覆盖生成的 PNG、realm.tscn、TileSet、world_manifest.json、shared/regions.json。编辑器手改应先存为副本或同步回构图源。源图导入器只在开发时运行，Image.load_from_file 的导出提示不影响运行时资源；游戏加载的是已导入的图集。

第一版 main.gd / field_of_view.gd / ui/exploration_hud.gd 留作历史参考，当前主场景不使用。旧 32×48 角色和圆形视野不在当前运行链上。

## A / C 接口

挂载点：`Main/World/Entities`，Y 排序。D 的 ExplorationPlayer 和 ExplorationNPC 是本地演示替身，A 可整体替换，不应把这些实体当作服务器权威对象。没有改 A/B/C 的业务目录。

层 1 WorldSolid，层 2 保留名 SightBlocker（当前不使用），层 3 Actors。玩家 layer=4/mask=5，NPC layer=4/mask=1。脚部胶囊约 18×14px，人物图在脚位上方 30px。

输入 move_left/right/up/down、sprint、interact、toggle_map、appearance、ui_cancel。身体接口 set_controls_locked(bool)、collect_checkpoint()；后者的 local_preview_player 必须换成真实服务器 actor_id。NPC appearance_key 与实例 id 分离。NPC 对话由 Hud.chat_submitted(npc_id,text) 暴露给后续网络层；当前没有发请求。

| region_id | 大小（格） | 世界原点（格） |
|---|---|---|
| market | 320×112 | (0,112) |
| greenwood | 160×112 | (0,0) |
| moonwood | 160×112 | (160,0) |

协议 tile 保持区域局部坐标：world_pixel = (offset + local_tile) × 32。shared/regions.json 同源导出障碍格、出生与双向出口，字段格式未增改；world_manifest.json 给出偏移。障碍格保守覆盖脚部碰撞，格级寻路比实际移动保守。C 的旧 NPC 出生/资源点/评审快照仍需按扩大坐标联调。

## 验证

```powershell
godot --headless --path game --script res://maps/qa/exploration_checks.gd
godot --path game --script res://maps/qa/capture_views.gd
godot --path game --script res://maps/qa/capture_actors.gd
```

86 项集成检查覆盖实际移动、双桥、河水、四边、对话锁定/中文提交、角色尺寸、出口和 NPC/地点连通；OpenGL 截图输出到 release/previews/v2_*.png。截图脚本换位仅用于 QA，正式游戏没有传送快捷键。日志见 release/validation/。

房屋目前为外景，船不可驾驶；无战斗结算、存档、后端 NPC 生成或评审学习。NPC 攻击帧已提取，但当前场景不会造成伤害。

## 已合并 A 分支（2026-11-14）

`feature/a-sprites-48x64` 的两个提交已合入本地 main，HEAD=d1bcf52。按 A 的接入约定，保留 D 的 main.tscn / project.godot 和上述地图布局。A 提供的 `seamless_world.tscn` / `seamless_world.gd` / `overworld_data.json` 是独立演示用的 96×60 地图，不覆盖 D 的 320×224 地图或共享区域坐标。

A 的 `tests/a_open_world_demo.tscn` 可 F6 单独运行；新增的 `actors/`、`combat/`、`controllers/` 和 `ui/equipment_panel.gd` 已在同一工程中。当前 D 主地图尚未替换为 A 的战斗 Actor；不得直接把 D 的四方向图集当成 A 默认的七行动作图集。进一步适配需使用 `actors/assets/sprite_sheet_layouts.json` 并核对动作与坐标。实际合并验证见 `release/MERGE_A_SPRITES.md`。
