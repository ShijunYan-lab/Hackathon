# 《未定之境》人物整张动画图统一规范（A/D 对接，V5）

## 现在统一什么？

- **每帧人物图：48×64 像素。** 四列、七行动画的推荐整表尺寸为 **192×448**。
- **地图网格仍然 32×32 像素。** 人物视觉高度不影响地图坐标、碰撞圆半径（原 8 px）、NPC 的 A* 寻路或后端 `tile` 数据。
- 一张 PNG 包含同一角色的多个动作；默认从上到下依次是 `idle`（2 帧）、`run`（4）、`attack`（4）、`hurt`（2）、`death`（4）、`dodge`（4）、`sprint`（4）。每行最多四帧，帧格为 48×64。没有用到的格子可以透明。
- 动作图背景应为透明，单帧完整人物不要跨出自己的 48×64 帧格；不要在帧格间加像素间距。
- 角色仍仅通过左右翻转进行面向调整；如果 D 要做四向动作，需要额外确定方向与行映射（当前补丁不会自动推断方向）。

## D 如何把新贴图接入？

最简单：把 D 的角色图按原名字放到：

```
game/actors/assets/sprites/knight.png
game/actors/assets/sprites/merchant.png
game/actors/assets/sprites/healer.png
game/actors/assets/sprites/wanderer.png
```

替换对应文件即可。原有 32×32 图仍可继续运行测试；`sprite_sheet_profile.gd` 自动按图像尺寸检测是 48×64（优先）还是旧 32×32。

也可以给新角色取一个名字如 `ranger.png`，并让后端 `appearance_key = "ranger"`。无需新增 NPC 专用场景。

如果 D 的动画行顺序不同，或者某个动作不是 4 帧，只需修改：

```
game/actors/assets/sprite_sheet_layouts.json
```

例如：

```json
{
  "skins": {
    "knight": {
      "frame_size": [48, 64],
      "animations": {
        "idle": {"row": 0, "frames": 4},
        "attack": {"row": 3, "frames": 3},
        "dodge": {"row": 4, "frames": 4},
        "death": {"row": 6, "frames": 4}
      }
    }
  }
}
```

上面是**示例片段**：修改实际 JSON 时要保留原来的 `animations` 默认部分，并将上述 `skins` 字段合并进去。没有覆盖的动作继续使用默认行映射。假如美术资源路径不是 `sprites/角色名.png`，则可以在对应 `skins.角色名` 下配置 `"path": "res://.../xxx.png"`。

如果特殊资源更换后出现人物与地面不对齐，可在 `player.tscn` / `npc.tscn` 根节点的 Inspector 中微调 `visual_foot_y` 或 `hand_offset_y`。默认 `visual_foot_y=11`、`hand_offset_y=0` 时：

- 32×32：`Visual.y = -5`、`WeaponPivot.y = -6`；
- 48×64：`Visual.y = -21`、`WeaponPivot.y = -22`。

`Visual` 会自动根据图帧高度归位，血条、姓名、伤害数字也会向上移动；不需要调整玩家在地图上的坐标。

## 动态 NPC 和 Godot 程序的边界

- A 负责 `actor.gd` 与 `sprite_sheet_profile.gd`；D 负责实际 PNG 和 `sprite_sheet_layouts.json` 的角色美术行映射；任何改动请先确认映射，再提交 PR。
- 如果 A/D 分别在不同分支里开发，也**不能保证合并时不冲突**。更稳妥的职责划分是：A 不改 D 的贴图；D 不改 A 的角色控制和切帧逻辑，优先只改 PNG/JSON。
- 玩家的移动、战斗和闪避事件 API 没变；B 的 Agent 决策、C 的库存和持久化也无需因贴图尺寸而重写。
- **旧图只是兼容用的占位素材。** 当前仓库没有 D 的 48×64 真正美术图，必须由 D 在自己的分支添加，A 分支只能验证新加载器的正确性。

## 验证

1. 运行 `python game/tests/check_spritesheets.py` 检查 PNG 尺寸与布局。
2. 在 Godot 中 F5，旧版 32×32 图仍应正常显示。
3. 将一张 D 的 48×64 图替换后再 F5，观察待机、走路、攻击、受伤、死亡、闪避和奔跑。
4. 检查脚底与地面、武器挂点、血条和伤害数字的位置。
5. D 的行顺序、帧数或透明边距如果不同，修改 JSON 或 `visual_foot_y`，而不是复制并重写 `actor.gd`。

**注意**：本补丁只按已商定的 48×64 默认排布实现，并未看到 D 实际绘制的大图，最终行顺序仍以 D 提供的素材为准。

在 Godot 可执行程序已加入 PATH 的机器上，还可以使用真正的 Godot 脚本测试：

```powershell
godot --headless --path game --script res://tests/verify_sprite_profile.gd
```

这会使用引擎实际加载每个默认角色的动画帧，检查切帧是否越界；与静态 Python 检查是两回事。
