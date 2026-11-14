# C 后端当前交付与操作

可启动的服务入口为 `server/main.py`。步骤 01—13 已实现：世界与位置、战斗死亡、物品归属和装备、知情范围与历史、NPC 对话任务、世界回合和导演调度、完整存档分支、运输学习回退与基础经济。默认未接模型，模式为 fallback。地图使用 shared/regions.json 中 market 的占位平面，后续由 D 提供含两村庄、森林、遗迹的正式单地图。固定 01—16 进度表位于 team/C_WORLD/STATUS.md 顶部。

## 启动与查看

在仓库根目录、已安装 requirements.txt 的 Python 环境运行，保持此终端开启。

```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

浏览器打开 http://127.0.0.1:8765/docs，可点击接口的 Try it out / Execute。/health 显示当前能力与模式。

POST /v1/worlds 输入如下。每次新操作使用新的 request_id，重试同一操作保留原 ID。

```json
{"request_id":"manual_new_001","seed":20261113,"player_name":"旅人"}
```

响应含 world_id，复制到 GET /v1/worlds/{world_id}/state 即可查看生成的人物、组织、物品和位置。GET /v1/worlds/{world_id}/events 查看实际事件。

另开终端运行自动演示，它创建独立演示世界，移动玩家一格，重复发送同一请求并检查事件只写一次。

```powershell
python -m server.api.smoke
```

默认数据库在仓库 `runtime/worlds.sqlite3`，被 Git 忽略。重启服务后，用原 world_id 可以读取世界。WORLD_DB_PATH 可指定数据库，WORLD_REGION_ID 可指定地图配置里的区域 ID。单个世界保留创建时的地图数据。当前支持 CHECKPOINT、HIT、PICKUP、EQUIP、GIVE、TASK_REPORT，以及 dialogue、advance、story。现已支持存档分支、运输评审、自动学习/回退、报价成交、组织与制造；Godot 展示待组装。

步骤 04 可运行 `python -m server.api.combat_smoke`，它创建新世界、报告命中直到一个 NPC 死亡、检查重复命中和原武器掉落，并打印可访问的状态及事件地址。该脚本使用合成碰撞报告验证真实 HTTP 后端。规则和 A/D 接入方法见 docs/COMBAT_API.md。

步骤 05—08 可运行 `python -m server.api.world_smoke`。它建立独立世界，用合成客户端位置检查赠送、装备、对话、三个世界回合、所有写入的原请求重试，以及历史查询，打印可打开的状态与历史地址。默认服务会如实显示对话 fallback、导演 PROVIDER_NOT_CONFIGURED；合成模型下的任务执行与导演建议另有自动测试。

手动推进：POST /v1/worlds/{world_id}/advance，输入以下 JSON。expected_world_version 改为最近响应的 world_version。每个新回合换 request_id，重试保留原请求。

```json
{"request_id":"manual_advance_001","expected_world_version":0,"reason":"debug_step","trigger_event_ids":[]}
```

返回的 tick 增一，state 显示最新状态；tasks 是本轮新任务，须由 A/D 执行后提交 TASK_REPORT 才结算资源。GET /story 显示玩家知道的历史。设置 ALLOW_DEBUG=true 后重启可访问 /story?view=debug、/agents/{npc_id}/debug、/director/debug。默认关闭调试视图。

详细参数、B 的模型注入与导演配置见 docs/WORLD_ACTIONS_CONTRACT.md。Demo 网页列为步骤 16，本轮交付的操作入口是 Swagger /docs。

## 当前机器的已用环境

已存在的 `C:/ProgramData/anaconda3/envs/weclone/python.exe` 可用于本次临时启动。启动命令中的 python 替换为下列完整调用即可。

```powershell
& 'C:/ProgramData/anaconda3/envs/weclone/python.exe' -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

此环境为 Python 3.10.14、FastAPI 0.112.0、Pydantic 2.8.2、Uvicorn 0.30.6。本轮另在 runtime/venv311 验证 Python 3.11.11 与 requirements.txt 全部固定版本，103 项测试通过。当前推荐使用该项目独立环境。

## 每节点交付

用户已授权每完成一个节点，及时测试、提交并推送到 feature/c-world。完成实现后先跑检查、启动服务验证实际行为，再更新 team/C_WORLD/STATUS.md，列出本节点文件、测试、未测范围和接入方法。

```powershell
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
git diff --check
git status --short
```

逐项暂存本节点文件，审查暂存内容后创建描述准确的提交，再发布到工作分支。

```powershell
git diff --cached --stat
git commit -m "feat(world): describe the completed milestone"
git push -u origin feature/c-world
git log -3 --oneline
```

提交记录用于查看每个节点的增量，STATUS 记录验证范围。后续同学获取该分支，根据接口说明组装，联调完成后再按团队流程合并。


## 步骤 09：存档与分支

POST /v1/worlds/{world_id}/saves，发送 request_id、expected_world_version、label。返回 save_id、saved_world_version 和 state；保存本身使版本增一。

POST /v1/saves/{save_id}/load，发送新的 request_id，返回 new_world_id、parent_save_id、state。同一请求重试返回同一分支；不同请求创建独立分支。实体 ID 保留，D 切换 world_id 后清空旧请求/动画队列，不把旧世界响应覆盖到新世界。后续命令使用返回的 world_version。分支保留存档前的命中和任务去重记录，未完成任务继续按原规则上报。不要恢复一半的攻击动画。


## 步骤 10—14 最新入口

完整运输/学习/回退见 EVALUATION_BACKEND.md；交易、组织、制造与迁入见 WORLD_ECONOMY.md。组装清单和 Windows 构建说明见 C_BACKEND_HANDOFF.md。

本机目标环境启动：& './runtime/venv311/Scripts/python.exe' -m server.launch。额外验证：python -m server.api.evaluation_smoke（明确使用合成客户端报告）。Windows 构建先安装 requirements-build.txt，再运行 python -m server.package_windows。交接源码包运行 python -m server.build_backend。
