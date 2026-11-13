# A｜角色、战斗与可见行动

## 你负责什么
你做角色的身体：玩家能走、能攻击；NPC 能执行移动、护卫、战斗、死亡。让 Agent 的决定真正出现在地图里。

**工作分支：** `feature/a-gameplay`。
**可修改目录：** `game/actors/`、`game/combat/`、`game/controllers/`、`game/tests/`。另可更新本目录 STATUS.md。
**不要碰：** 不改 project.godot、main.tscn、地图/UI、shared 协议、后端数据库。需要输入动作由 D 添加；不自己建另一套 HTTP 或伤害账本。

## 开工前读
- `AGENTS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/SETUP.md`
- `docs/INTEGRATION.md`
- `docs/API_CONTRACT.md`
- `docs/EVOLUTION_REQUIREMENTS.md`
- `shared/regions.json`
- `examples/state_response.json`
- `examples/hit_request.json`

以上路径从仓库根目录算；不要把 docs/archive 旧手册当成新版任务。

## 任务清单

| 编号 | 优先级 | 你需要做的事 | 怎样算完成 |
|---|---|---|---|
| A01 | P0 | 在 game/tests 建占位测试场景；玩家 WASD 移动、碰撞、镜头 | 斜走不加速、不穿墙；不等待美术 |
| A02 | P0 | 通用 Actor：玩家/NPC/怪物用同一种稳定 ID 和数据入口 | 给不同 ActorState 就能显示，无 npc 名字判断 |
| A03 | P0 | J 普攻、K 闪避、受击、击退、攻击冷却和死亡表现 | 每次 attack_id 对同目标只上报一次命中 |
| A04 | P0 | 按 INTEGRATION 的信号把命中交 D；用 C 返回血量更新 | 不在客户端再次扣服务器已扣的血 |
| A05 | P0 | NPC/怪物待机、追击、普通攻击、逃跑；所有 NPC 可攻击 | 不需 LLM 每帧驱动；死亡不能交谈或行动 |
| A06 | P0 | execute_task 支持 MOVE/ATTACK/FLEE 与完成/失败上报 | 人真正走到地点，不直接打印“任务完成” |
| A07 | P0 | 死亡掉落的表现、装备 stats 读取、换场景恢复 | 物品和死人不重复生成；不自行随机装备 |
| A08 | P0 | collect_checkpoint，关闭聊天时恢复输入，切图取消在途本地攻击 | 中文输入不同时触发攻击；存档不重复打击 |
| AE1 | 新P0 | 商人自动移动到接收点，失败/死亡/到达都能报告 | 一轮任务能明确结束，不能永久卡路 |
| AE2 | 新P0 | 护卫 ESCORT：跟随指定商人，附近敌人用正常战斗攻击 | 使用实际 NPC 与同一战斗逻辑，不做特制获胜动画 |
| AE3 | 新P0 | 重新加载同一场景时清理角色、计时器、旧信号和任务 | 第二轮不继承上一轮已死敌人/残留攻击 |
| A09 | P1 | 刀光、音效、人物动画和第二类敌人表现 | 真闭环和评审先通过，再美化 |


## 第一轮交付与顺序
先交 A01–A03 的方块战斗场景与信号格式；随后接 D/C 实际命中，再做 MOVE/ESCORT。不要第一轮就写整套背包或剧情。

## 预期代码位置
预计产出 `game/actors/actor.tscn`、`actor.gd`、`game/controllers/player_controller.gd`、`npc_controller.gd`、`game/combat/hitbox.gd`、`game/tests/combat_test.tscn`。实际模块拆分可在本人目录内调整。

## 和别人交接
交给 D：Actor.tscn、脚本、测试场景、方法/信号说明；给 C：实际 HIT/TASK_REPORT 样例与报错复现。供 D 实例化，不让 D 复制你的逻辑。
共同字段和方法在 docs/INTEGRATION.md。自己的想法与协议冲突时找 C/D，不私自改。

## 怎么自测
F6 跑独立测试场景；验证一次挥刀只报一次、NPC 都能被攻击、死亡持续、MOVE 到达、ESCORT 参与实际战斗；再由 D 联调真实后端验证数据。
公共基础检查：
```powershell
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
```
这些公共检查不能替代你自己的功能测试。尚未创建的岗位测试先实现，不能声称现成存在。

## 交付时更新 STATUS.md
记录完成项、修改文件、真实测试结果、未完成项和下一位同学需要怎样连接。
交付实际代码，不只把设计文字再输出一遍。未测Windows/Godot/LLM必须明说。
