# 未定之境 · 四人协作开发仓库

协作包版本：v2；基础 HTTP/API 仍为 v1，新增评审合同 evaluation-v1。

**当前已集成可运行的 Godot 游戏源码工程。** A/B/C 已接入 D 的连续大地图：双村庄、森林与遗迹、48×64 人物、战斗与装备、独立 NPC 记忆、持久存档、两轮运输评审与回退。

本机验证：160 项 Python 测试、38 项 Godot 联调检查通过；15 位 NPC 真实 DeepSeek 对话、记忆隔离及模型驱动移动已验证。详情见 [最新功能与验证记录](release/LIVE_NPC_UPDATE.md)。独立 Windows 发行包和第二台电脑验收尚未完成。

运行：安装 Godot 4.5.2，在仓库根目录创建 `.venv` 并安装 `requirements.txt`；按 `.env.example` 在本机配置模型。打开 `game/project.godot` 按 F5，或执行 `powershell -File release/start_game.ps1 -GodotPath '你的Godot可执行文件路径'`。模型密钥、个人存档与运行数据库不随仓库上传。控制与启动细节见 [客户端说明](game/README.md)。

下方保留团队任务分工及初始协作说明；当前完成状态以上述更新记录为准。

**提交截止：2026-11-15 08:00，UTC+8。**
目标是可演示的中世纪奇幻像素沙盒 RPG，并证明 NPC 能从第一次任务的反馈中学习，第二次完成同一任务时表现更好。

## 现在怎么开始

1. 群里每人认领 A/B/C/D 一个岗位，在 `docs/TEAM_BOARD.md` 填姓名。
2. 所有人先读 `AGENTS.md`、`docs/PROJECT_BRIEF.md`、`docs/SETUP.md`。
3. 打开自己目录中的 `TASKS.md`，把同目录 `PROMPT.md` 的内容交给能访问本仓库的大模型。
4. 每人只改自己的文件；需要改公共接口时由 C 统一处理。
5. 先做一个能连接起来的小版本，再增加功能。模型的口头解释不算交付，真实代码和可重复测试才算。

| 岗位 | 人话职责 | 任务卡 | 给大模型的提示词 | 首次交付 |
|---|---|---|---|---|
| A：角色与战斗 | 做角色的身体和实际动作 | [TASKS](team/A_GAMEPLAY/TASKS.md) | [PROMPT](team/A_GAMEPLAY/PROMPT.md) | 占位角色能走、能打、能上报动作 |
| B：NPC 与学习 | 做 NPC 的记忆、决定和学习 | [TASKS](team/B_AGENTS/TASKS.md) | [PROMPT](team/B_AGENTS/PROMPT.md) | 校验合格的 Agent 输出与学习单测 |
| C：世界与后端 | 做账本、裁判、接口和评测 | [TASKS](team/C_WORLD/TASKS.md) | [PROMPT](team/C_WORLD/PROMPT.md) | 真后端基础接口、事件写入 |
| D：地图与集成 | 做舞台、界面、联网和交付 | [TASKS](team/D_INTEGRATION/TASKS.md) | [PROMPT](team/D_INTEGRATION/PROMPT.md) | 地图、中文对话框、MOCK 连通 |

## 文件怎么找

- `docs/INDEX.md`：按工作需要阅读，不必一次看完所有材料。
- `shared/protocol.py` + `docs/API_CONTRACT.md`：保留的基础 v1 接口。
- `shared/evaluation_protocol.py` + `docs/EVALUATION_CONTRACT.md`：新增评审/学习接口约定，**还不是实现**。
- `docs/EVOLUTION_REQUIREMENTS.md`：最新赛道要求如何落到代码和现场演示。
- `docs/INTEGRATION.md`：A↔D、B↔C、C↔D 的交接细节。
- `docs/ACCEPTANCE.md`：验收，不用“我觉得能用”代替测试。
- `docs/GIT_GUIDE.md`：上传、分支、合并、密钥和不能提交的文件。
- `docs/MIGRATION.md`：原压缩包文件去了哪里，哪些更新覆盖旧文档。
- `docs/archive/`：只留历史，不作为本轮大模型开工输入。

## 可以现在运行的部分

在 Python 3.11 独立环境、仓库根目录执行：

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
python -m uvicorn tools.mock_api:app --host 127.0.0.1 --port 8765
```

`http://127.0.0.1:8765/docs` 是原基础 MOCK 的接口页面。
这个 MOCK **不运行战斗或 LLM，也不提供真实评审学习接口**。
新增评审界面可先用 `examples/evaluation/` 的标注为 `mock` 的样例做展示开发，C 再实现真接口。

`game/project.godot` 是最小空工程，尚无玩法。A/D 可以导入，但须在本机验证 Godot。
完整后端的约定入口是 `server.main:app`，由 C 实现；目前不要把这个命令当成已可用。

## 必须遵守

不把 `mode=mock` 的样例当实测；不在两次演示间人工改代码、参数、模型或提示词。
第二次恢复相同的世界任务条件，只保留自动学到的策略和经验。回退恢复整份学习状态，不只是改版本号。

这里没有附带 `.git` 历史，也没有向任何远程仓库上传。首次 push 前读 `docs/GIT_GUIDE.md`。
