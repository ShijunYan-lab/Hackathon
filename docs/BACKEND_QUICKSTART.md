# C 后端当前交付与操作

世界导演接口位于 `server/world/director.py`。可启动的服务入口为 `server/main.py`，当前实现创建世界、状态读取、位置保存、HIT 伤害、死亡清理、事件查询与 SQLite 持久化。默认模型模式 fallback。地图使用 shared/regions.json 中 market 的占位平面，后续由 D 提供正式单地图。固定 01—15 进度表位于 team/C_WORLD/STATUS.md 顶部。

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

默认数据库在仓库 `runtime/worlds.sqlite3`，被 Git 忽略。重启服务后，用原 world_id 可以读取世界。WORLD_DB_PATH 可指定数据库，WORLD_REGION_ID 可指定地图配置里的区域 ID。单个世界保留创建时的地图数据。当前 CHECKPOINT 和 HIT 命令可执行，其他动作返回 ACTION_NOT_SUPPORTED。对话、世界导演的执行与持久化、评审以及 Godot 展示待后续节点。

步骤 04 可运行 `python -m server.api.combat_smoke`，它创建新世界、报告命中直到一个 NPC 死亡、检查重复命中和原武器掉落，并打印可访问的状态及事件地址。该脚本使用合成碰撞报告验证真实 HTTP 后端。规则和 A/D 接入方法见 docs/COMBAT_API.md。

## 当前机器的已用环境

已存在的 `C:/ProgramData/anaconda3/envs/weclone/python.exe` 可用于本次临时启动。启动命令中的 python 替换为下列完整调用即可。

```powershell
& 'C:/ProgramData/anaconda3/envs/weclone/python.exe' -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```

此环境为 Python 3.10.14、FastAPI 0.112.0、Pydantic 2.8.2、Uvicorn 0.30.6。目标交付环境 Python 3.11 与 requirements.txt 固定版本仍需验收。

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
