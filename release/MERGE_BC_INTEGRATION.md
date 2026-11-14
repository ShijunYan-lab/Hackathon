# A / B / C 接入 D 大地图 · 2026-11-14

已将用户指定分支合并到本地 `main`，并将控制器和后端接入现有主场景。没有 push。

| 分支 | 已合入版本 | 本地合并 |
|---|---|---|
| feature/a-sprites-48x64 | d1bcf52c55a599d5516330f6d594004ce20b725d | 先前已快进合入 |
| feature/c-world | 0cb7b93e3a93ab7653bdb929825a19121bb50d5f | 3ad3b1a |
| feature/b-agents | c48b16e246879781f2ce49d955959f06fd469799 | 979f158 |

C 拉取时已有 20 个提交，以实际远端为准。合并前的 295 个本地变更文件及 SHA-256 清单保存在 `D:\DBIS\_backups\Hackathon-before-bc-20261114-113412`。Git 合并无冲突，合并后第一时间验证原文件全部相同。随后新增的接入代码与兼容修正保留在工作区，未额外提交。

## 现在能运行的内容

- 保留 D 的 10240×7168 大地图、建筑与人物图集、全屏视野、树冠遮挡、边界空气墙。15 套 NPC 外观按后端动态 ID 实例化；新生成 NPC 也使用同一适配器。
- 玩家与 NPC 继承 A 的 Actor/Player/NPC。玩家走路、奔跑、闪避、挥砍、射弹；NPC 执行 C 下发的路径/护卫任务，按实际结果回报。原图角色动画通过 `reference_frames.gd` 适配，无替换图集。
- `game/net/game_api.gd` 串行 HTTP 请求，发送时填版本；断线保持原请求 ID 和相同请求体，F9 重试。版本冲突刷新状态，不自动重放攻击或交易。切换世界清理队列、角色、投射物，拒绝旧世界状态覆盖当前状态。
- C 确认六类武器装备与伤害、死亡、物品掉落/拾取/赠送。所有 NPC 可被击杀，死亡持久化。背包显示真实物品，支持出售提议、接受发给玩家的报价、制作入口与组织列表。
- 中文自由输入走 C → B → C，等待状态锁住输入。NPC 身份带本人职业、工作目标；知识范围仍由 C 限制。无模型时显示实际 `fallback`，不使用本地对白冒充在线回复。
- F6/F7 存档与读取；J/F2 显示世界篇章，F3 显示连接状态和附近任务。F4 创建运输观察、首跑、二跑、结果、学习记录、基线回退与回退验证。使用同一地图和 A 的物理控制器，成绩由 C 根据实际事件计算。

## 运行

在 `D:\DBIS\Hackathon`：

```powershell
powershell -File release/start_game.ps1
```

或打开 `game/project.godot` 按 F5。没有服务时客户端自动使用 `.venv/Scripts/pythonw.exe` 启动 `release/run_backend.py`。手动后端：

```powershell
.venv\Scripts\python.exe release/run_backend.py
```

本机 `.venv` 已安装 requirements.txt。换机先创建虚拟环境并安装依赖。启动器可用 `-GodotPath` 指定引擎。若 8765 已运行旧地图服务，先在其原终端关闭，再启动新服务；启动器不会强制结束其他进程。

正式数据库为 `runtime/overworld.sqlite3`；旧 `worlds.sqlite3` 不迁移、不覆盖。客户端会记住最近世界和快照。按 F9 重连；旧世界确实不存在时，可按 F8 创建新的旅途，旧快照不会被删除。

## 最小兼容变更

| 文件 | 原因 |
|---|---|
| `game/maps/network_*.gd`、`reference_frames.gd`、`world_item.gd` | A 控制器与 D 图集、碰撞、坐标、动态实例之间的适配 |
| `game/net/game_api.gd`、`game/ui/network_hud.gd`、`game/main.tscn` | 正式联网主入口和界面 |
| `game/maps/export_backend.gd`、`backend_world.json`、`director_locations.json` | 从同一 Godot 布局导出 320×224 连续地图；12,897 个阻挡格、15 个 NPC 模板、4 个资源点 |
| `release/run_backend.py` | 组合 C 应用、D 地图/导演地点/运输坐标，保留 C 独立入口 |
| `shared/protocol.py`、`server/world/items.py`、`combat.py` | 增加 A 已实现的锤、弓、弩、杖类型与服务器射程限制；伤害和冷却仍由 C 决定 |
| `server/generation/initial_world.py` | 可选地图 NPC 外观/位置模板与服务器生成的六武器初始背包，仍使用动态 ID；旧随机地图路径保留 |
| `server/world/agent_runtime.py` | 仅补充 NPC 本人职业/工作目标及生命信息，不改 B 学习算法 |
| `server/main.py` | health 添加地图 ID/大小，防止连接旧地图服务 |
| `game/combat/projectile.gd` | 使用 A 武器目录的射程/速度，正确碰撞 TileMapLayer |
| `game/actors/actor.gd` | 未提供受击来源时不把世界原点当攻击者，防止角色错误击退 |
| `tests/test_world.py`、`test_combat.py` | 原测试默认小地图边界与大地图冲突，改用显式 48×32 测试夹具 |

A/B/C 原有模块均保留；没有替换 B 的策略/学习实现，也没有让 UI 直接读写数据库。

## 实际验证

- Python：`155 passed`；包含 9 项新增地图/有限知识/六武器/射程/幂等/运输坐标检查。
- 协议检查：9 个基础示例、6 个评审示例通过。
- Godot 地图回归：`86 passed / 0 failed`，使用保留的离线美术预览场景验证双桥、边界、图集、地点/NPC 可达性等。
- Godot HTTP 端到端：`24 passed / 0 failed`，实测真实输入走路、闪避、中文聊天、NPC 寻路任务、射弹和近战结算、死亡掉落/拾取、存档/读档、切换世界清除飞行中投射物、两轮运输、报告、基线回退及恢复基线后的第三次实际执行、返回原旅途，零被拒 HTTP 请求。记录：`validation/network-results.json`。
- 该端到端测试使用 8766 和独立 QA 数据库。`backend_fixture.py` 的普通对话/移动决策是显式 test double；运输选策和学习使用合入的 B 实现，战斗/任务/收益使用真实 A/C。测试不要求第二轮必然成功，也不按轮次强制策略。
- 真实 B 对话冒烟：通过正式 `make_app` 调用 B，HTTP 200、回复非空、模式 `fallback`。未验证在线 LLM。
- 本机源码冷启动：Godot 自动启动后端，`connected=true actors=16 auto_start=true`。
- OpenGL 实际渲染并目视检查背包、中文聊天、主场景和地图。截图 `previews/v3_*.png`。

最近完整运输实测：首跑商人死亡、送达 0/10；第二轮雇佣护卫、送达 6/10、花费 5、收益 0.575；两轮均未达到 80% 成功标准。UI 如实展示结果，并恢复原策略版本 0。其结果只说明这一次实际运行，不是对稳定成功或在线模型提升的承诺。

## 边界与后续

本次完成用户要求的本地合并及大地图接入。尚未导出 Windows 发布包、录制提交视频、在第二台电脑冷启动或人工验收 Windows 中文输入法候选窗。当前装备协议仍是一个权威已装备武器；没有虚构 11 槽完整装备系统。建筑为外景，船为环境物件。角色图集保持原来的 48×64 适配版本；玩家攻击以原图角色和 A 的武器/特效组合呈现，未新增原图不存在的四方向攻击绘制帧。
