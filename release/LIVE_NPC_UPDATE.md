# 2026-11-14 · 真实 NPC 对话与交互更新

直接打开 `game/project.godot` 并 F5，或在仓库根目录执行：

```powershell
powershell -File release/start_game.ps1
```

本机 `.env` 已配置 DeepSeek，`APP_MODE=live`、`LLM_MODEL=deepseek-chat`，单次模型超时 30 秒、并发上限 2。密钥仅在被 Git 忽略的本地 `.env` 中，由 Python 后端读取；Godot、代码和本文不包含密钥。界面根据实际响应显示 `live` 或 `fallback`。

## 本次完成

- 全部 15 位 NPC 接入 B 的真实模型对话。E 靠近交谈，自由输入中文，Enter 发送；各自使用职业、住处、物品和可知事件。
- C 提供本人可见且可达的移动/采集目标，以及已收到的提议；B 从合法候选里提出动作。玩家提出近处的合理请求时 NPC 可以执行，也可基于性格和处境拒绝，不用固定台词假装执行。
- 完整对话保存在 SQLite 的 `npc_dialogue_turns`，按 `(world_id, npc_id)` 隔离。重启可恢复；存档复制到独立世界分支，后续对话互不影响。模型读取本人最近 8 轮对话和经 B/C 校验的独立记忆；界面回看最近 20 轮。没有向模型发送全体 NPC 的私聊记录。
- 修复 `EVALUATION_FROZEN`：普通世界 ID 单独保存；临时评审世界不再覆盖普通会话。遇到旧错误会话自动找回普通世界，不解除评审保护、不删除记录。
- 玩家武器按柄端定位到手部，近战挥动、远程朝向和身前/身后层次分别处理。NPC 使用参考图自带的武器动作，移除重复的悬浮武器图标。
- 箭矢在后段飞行中逐渐变淡，碰撞后短暂淡出；沿飞行轨迹连续检测，避免穿过薄墙。所有 NPC 有脚部实体碰撞，建筑、树干、水岸和其他地图实物沿用地图碰撞体。草、花等地面装饰仍可踩过。
- 15 位 NPC 分别驻留铁匠铺、集市、酒馆、民居、渡口、森林和遗迹。旧普通世界中聚集在出生点的存活闲置 NPC 可一次性迁回对应地点；死亡状态和个人记忆保留。
- Tab 打开行囊，点击剑、斧、锤、弓、弩、法杖可查看对应原生 Godot 像素大图与后端真实属性。
- 玩家攻击 NPC 后立即出现头顶批评对话框，并由 C 建立自卫任务，A 执行追击/攻击与命中上报。玩家离开约 260px 或追击超过 18 秒后停止追逐并寻路返回。即时警告是世界规则反应，不冒充模型输出；攻击事件进入该 NPC 的可知记忆，之后自由聊天可根据事实回应。普通动作仍使用 B 决策 → C 任务 → A 实际执行的链路。

## 验证结果

本机 Windows / Godot 4.5.2 / OpenGL 3.3。全部结果均来自实际执行：

| 检查 | 结果 |
| --- | --- |
| Python 全套 `pytest tests -q` | 160 passed |
| 基础 / 评审协议示例 | 9 + 6 通过 |
| Godot `network_checks.gd` | 24 passed，包括真实 HTTP、射击伤害、死亡掉落、存读档、两次运输、回退 |
| Godot `live_features.gd` | 14 passed，包括全部 15 类 NPC 命中、人物阻挡、渐隐、薄障碍、自卫伤害、返回住处、大图选择、冻结恢复后可存档 |
| `live_npc_probe.py`，真实 DeepSeek | 15/15 NPC `live`；重启后回忆暗号成功；另一 NPC 未读到该私聊 |
| Godot `live_action.gd`，真实 DeepSeek | 商贩决定走近玩家 → 实际移动 41.25px → C 确认任务成功；无 API 错误 |
| 正式 8765 会话恢复 | connected=true / actors=16 / ordinary=true |
| OpenGL 画面检查 | 真实 `live` 中文对话、六种大图、六种手持武器、受击对话框 |

结果：`release/validation/live-npc-results.json`、`live-action-result.json`、`live-features-results.json`、`network-results.json`、`resume-result.json`。截图：`release/previews/v4_*.png`，`v4_04_bubble_layout.png` 为最终两行警告框排版。运行日志在本地 `runtime/v4-*.log`。

自动测试使用独立 SQLite；8766 是明确标注的确定性测试服务，8767 是真实模型画面验证服务，均不会替换正式 8765 世界。普通 Python 测试屏蔽真实密钥；只有单独运行 live probe 才会调用付费模型。

## 修改与备份

主要修改 `game/maps/network_*.gd`、`game/net/game_api.gd`、`game/ui/network_hud.gd`、`weapon_portrait.gd`、`game/combat/projectile.gd`；按用户本次接入与修复要求补齐 B/C 的模型请求、私有对话存储/快照、NPC 自卫任务、旧世界位置修复及评审恢复信息。未改 B 的运输学习算法。

工作区修改前备份：`D:\DBIS\_backups\Hackathon-before-live-npc-20261114-133606`。正式数据库升级前备份：该目录下 `overworld-before-upgrade.sqlite3`。未重置仓库、未删除存档、未 push。

网络服务不可用时仍会如实显示 fallback；原始对话全部持久保存，但模型上下文是有限窗口，并非无限逐字记忆。当前交付为本机 Godot 源码工程；独立 EXE、第二台电脑冷启动和人工中文输入法候选窗仍属于后续发行验收。
