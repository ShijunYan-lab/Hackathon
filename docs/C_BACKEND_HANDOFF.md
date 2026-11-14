# C 后端交接与真实游戏验收入口

工作分支 feature/c-world。C 的实现和测试覆盖步骤 01—13；进度以 team/C_WORLD/STATUS.md 为准。后端端口 8765，单进程单 worker，坐标为 32 像素格。默认无真实模型，显示 fallback。

## 运行

源码方式：Python 3.11 独立环境安装 requirements.txt，仓库根目录运行 python -m server.launch。默认数据库为当前工作目录 runtime/worlds.sqlite3，不随源码重建而删除。--db 可指定外部存档位置。接口页 http://127.0.0.1:8765/docs。

Windows 包方式：解压整个 CWorldBackend 目录，运行 CWorldBackend.exe（保留旁边的 _internal）。默认端口与数据库位置同上。可从 PowerShell 指定 CWorldBackend.exe --db D:/game-data/worlds.sqlite3。不要在仍有服务占用 8765 时重复启动。

源码交接包通过 python -m server.build_backend 生成。Windows 包通过安装构建依赖后 python -m server.package_windows 生成，每次输出独立 dist/c-world-win-时间戳，避免覆盖旧运行目录。二进制及 runtime 数据按仓库约定不提交 Git；构建脚本与说明随代码提交。

## 对接责任

| 同学 | 读取与执行 | 回传 |
| --- | --- | --- |
| A | ActorState、装备最终属性、MOVE/ESCORT Task | 碰撞 HIT、到达/失败 TASK_REPORT；不自行改最终血量和资源 |
| B | 本 NPC AgentContext；导演 DirectorContext；评审 TransportContext/LearningProfile | dialogue/plan、director_provider、choose_transport/learn_transport 的明确 DTO；不能写世界库 |
| D | 统一 HTTP、完整 state、world_version、模式与错误；切换分支清理旧请求和动画 | request_id 重试不变；真实位置；正式单地图与出生/资源/运输/迁入点配置 |

详细接口：COMBAT_API.md、WORLD_ACTIONS_CONTRACT.md、WORLD_ECONOMY.md、EVALUATION_BACKEND.md。旧 API_CONTRACT 的多地图描述按用户最新要求采用一张连续地图，四处地点坐标由 D 配置；C 未改 D 的 shared/regions.json。

## 可重复后端检查

先启动服务，再分别运行：

```powershell
python -m server.api.smoke
python -m server.api.combat_smoke
python -m server.api.world_smoke
python -m server.api.evaluation_smoke
```

这些脚本创建独立测试世界，不删除已有存档。位置、命中和到达均为合成客户端报告；不能当成 Godot 画面、实际碰撞或现场学习改善的验收证据。

## 步骤 15 待真实组装验收

本分支 game/actors、combat、controllers、net、ui、maps 目前只有占位说明，缺少真实 A/D 执行与网络脚本。C 不代写其他岗位模块，也不把接口测试标成游戏验收。模型适配器仍未提供。

组装后按以下顺序记录结果、失败原因及提交版本：

1. 单地图探索、迷雾、四处地点，位置同步、断线原请求恢复。
2. 真实碰撞攻击任意生成 NPC，死亡/掉落/组织变化与画面一致。
3. 自由输入对话，模型模式正确；任务走到目标才得到资源。
4. 物品拾取/赠送/装备、金币交易、合作与入会同意、制造材料消耗。
5. 导演读取世界历史，NPC 不泄漏未知见闻，新迁入人物保留死亡后果。
6. 同一场景完整运输首轮→真实结算→自动学习→第二轮；记录交付率、费用和耗时，不预定第二轮胜出。
7. 回退后实际恢复原策略、经验与世界；旧 HTTP 响应不覆盖新分支。

用户最新调整：步骤 16 先于团队联调。网页入口 /demo/ 已提供，浏览器交互尚待人工核验；Swagger 与命令行演示仍可用于接口检查。


## 本机构建产物

2026-11-14，Python 3.11.11 与固定依赖通过 103 项测试。Windows 包：dist/c-world-win-20261114T013430Z.zip；SHA256 84f48548f0ff06a1d025e904e839df4298fb48cd61bf14a2e77c47a6f62d8fee.

源码与 EXE 的世界操作、学习回退及重启通过；尚未跨机器验收。源码包包含运行代码和说明，完整自动测试请使用 Git 仓库。
