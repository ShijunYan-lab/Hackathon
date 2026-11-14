# Godot Client — 《未定之境》

Godot 4.5.2 Standard / GDScript / Compatibility。当前 D 主场景为 800×450（窗口放大至 1600×900）。

**本地已合并 A / B / C，F5 进入联网大地图**：320×224 格、双村庄、森林、遗迹，保留原图 48×64 人物。A 负责移动/闪避/攻击/寻路，B 负责对话与决策，C 负责持久化结算。

A 的角色、战斗、装备、动画加载器和 MOCK 演示均已合入。要单独运行 A 的原型，在编辑器打开 `tests/a_open_world_demo.tscn` 后按 F6，可测试移动、战斗、NPC 路径、背包、钱币与掉落。它不连接真实 LLM 或后端，使用自己的 96×60 测试地图和旧演示贴图；没有覆盖 D 的正式地图、角色图片或 shared/regions.json。

本机已安装 `.venv`。在 Godot 打开 `project.godot` 后 F5，客户端会在需要时自动启动 `release/run_backend.py`（127.0.0.1:8765）。也可以从项目根目录运行 `powershell -File release/start_game.ps1`。正式世界保存在 `runtime/overworld.sqlite3`；F6 保存快照，F7 从快照恢复为独立世界分支。

WASD/方向键移动，Shift 跑，空格闪避，鼠标左键攻击，1/2 循环近战/远程武器，E 对话/拾取，Tab 背包，J/F2 手札，F3 状态，F4 运输评审，M 地图，V 外观，F9 重连。对话、背包期间禁止攻击。六类武器均经 C 的 EQUIP/HIT 确认；无本地扣血或虚构战利品。

全部 15 位 NPC 已验证真实 DeepSeek `live` 自由对话，并有按世界与人物隔离的持久记忆。受攻击时显示警告并实际反击；NPC 分布在各自的工作地点。箭矢渐隐且碰撞角色/场景实物，Tab 点击武器显示对应大图。旧评审会话会自动恢复普通旅途。详情和验证见 [本次更新](../release/LIVE_NPC_UPDATE.md)。测试夹具中的 `QA_MOVE` 只用于独立的 8766 测试服务，正式服务不识别这种测试命令。

入口：`main.tscn → maps/network_main.gd`。地图数据：`maps/backend_world.json`，统一 `overworld` 全局坐标；旧三分区 `shared/regions.json` 仅保留给历史离线预览。新启动器是正式大地图后端的组合入口，不要用旧默认地图服务替代。

分支、备份、兼容修正、验证与限制见 [B/C 接入记录](../release/MERGE_BC_INTEGRATION.md)。离线美术预览独立保留在 `maps/offline_preview.tscn`。

详见 [`INTEGRATION_V4.md`](INTEGRATION_V4.md)：控制方式、文件所有权、装备槽、单地图全局坐标、NPC 动态生成以及必须由 C 升级的协议。
