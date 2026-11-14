# 发布目录 · D主责 / C提供后端构建

这里提交启动脚本、构建说明、运行说明、授权清单，不提交大二进制和录像。
产物放本机 release/builds/，录屏放 release/recordings/（均被Git忽略）。
D实现客户端导出和start_game启动器；C在Windows构建真实后端；双方完成另一台Windows冷启动。
尚未附带可运行游戏或后端发行包。不得把此仓库ZIP当作成品游戏提交。

当前 Godot 工程已接入 A/B/C 的真实 HTTP、战斗、任务、存档、运输评审和经济接口。启动：在根目录执行 `powershell -File release/start_game.ps1`，或 Godot F5 自动启动本地后端。

当前交付记录：[真实 NPC 对话与交互更新](LIVE_NPC_UPDATE.md)，全部 15 位 NPC 已验证 DeepSeek live 对话、独立记忆和自卫交互。合并过程见 [MERGE_BC_INTEGRATION.md](MERGE_BC_INTEGRATION.md)。此前地图与美术阶段记录见 [EXPLORATION.md](EXPLORATION.md)。尚未导出 Windows 发行包，也未在第二台电脑验证；本机源码冷启动已验证。
