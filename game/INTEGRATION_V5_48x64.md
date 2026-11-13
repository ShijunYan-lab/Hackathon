# A → D、B、C：48×64 人物大图适配说明（2026-11-13）

## 本次改了什么

- 人物动画帧读取从写死的 `32x32` 改成按整张 PNG 识别 `48x64`（优先），旧 `32x32` 自动兼容。
- 所有角色默认动作仍为 idle/run/attack/hurt/death/dodge/sprint；默认每行一种动作、每行 4 格。具体映射在 `actors/assets/sprite_sheet_layouts.json`，**如果 D 的真实图片不遵循这一行顺序，请 D 修改映射**。
- 角色 Visual 的 Y 位置、手持武器挂点、血条与姓名、受击数字、攻击刀光和远程弹道的显示偏移已根据当前帧高调整。
- `CollisionShape2D`、32px 地图格子、角色在世界中的坐标、A* 路径、背包、武器逻辑、Hit payload 和任务接口都不变。
- 不含 D 的最终 48x64 图片；演示用旧图仍保留（会检测为 32x32）。

## 需要 D 做什么

1. 从 D 分支将新的 48x64 动作 PNG 合入 `game/actors/assets/sprites/`，例如覆盖 `knight.png` / `merchant.png` 等；如果新名字，在世界角色数据中设置相应 `appearance_key`。
2. 与 A 核对每张图是否为 **48x64 单帧、四列、七行动作、192x448 整图**。不是这个排布的，请改 `sprite_sheet_layouts.json` 的 `skins` 对应项；不必重写 A 的加载器。
3. 在 Godot F5 观察脚部、血条、装备挂点；如有透明留白，用人物场景中 `visual_foot_y`、`hand_offset_y` 修正。
4. 地图使用原 32x32 TileSet，角色大小与地图格子不同是正常情况。
5. UI、美术资源仍归 D；请不要同时和 A 修改 `actor.gd`、`player.gd` 或 `project.godot`。

## B、C 无需因角色图片修改接口

B 的 Agent 仍只操作身份/记忆/动作意图，不接触 SpriteFrames。
C 仍只根据 `entity_id`、`region_id`、tile 坐标、武器与物品等数据结算。这里没有更改 API 和 32px 单格比例。

## Git 协作建议

- A 在 `feature/a-sprites-48x64` 或已有 A 分支提交本补丁；D 在 `feature/d-integration` 上提交 PNG 和 UI。
- 独立分支**不会阻止同文件合并冲突**。最稳妥做法是 A 独占角色脚本，D 独占图片/动画配置，先合并 A 的补丁，再让 D 将自己分支更新到最新 main。
- 不在 A 分支打包或覆盖 D 的正式主场景，不强制推送 main。

## 引擎验证步骤

1. `python game/tests/check_spritesheets.py`
2. 用 Godot 4.5.2 打开 `game/project.godot`，执行 `F5`，确认原 32px 图可启动。
3. D 放入第一张 48x64 大图，再执行 `F5`，逐项看 idle/run/sprint/attack/hurt/death/dodge、武器、血条。
4. 更换 NPC 外观，确认动态 NPC 和玩家都用同一个加载器。
5. 完成后在 A 的 `STATUS.md` 更新“Godot F5 已通过”，未经实际测试时不能写已通过。
