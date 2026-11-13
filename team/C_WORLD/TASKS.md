# C｜世界规则、数据、接口与评测

## 你负责什么
你做世界的账本和裁判：谁活着、物品归谁、行动是否成功；并负责两次实验如何开始、结算、自动学习和回退。你是接口负责人。

**工作分支：** `feature/c-world`。
**可修改目录：** `server/main.py`、`server/api/`、`server/world/`、`server/storage/`、`server/generation/`、`server/evaluation/`、共享协议与Python依赖、后端测试。另可更新本目录 STATUS.md。
**不要碰：** 不写角色动画、不做主UI、不偷偷修改D地图坐标；不在接口内部直接手写“第二轮成功”。不能把原 MOCK 改标签成 live 当成真后端。

## 开工前读
- `AGENTS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/SETUP.md`
- `docs/API_CONTRACT.md`
- `docs/INTEGRATION.md`
- `docs/EVOLUTION_REQUIREMENTS.md`
- `docs/EVALUATION_CONTRACT.md`
- `shared/protocol.py`
- `shared/evaluation_protocol.py`
- `shared/regions.json`
- `docs/ACCEPTANCE.md`

以上路径从仓库根目录算；不要把 docs/archive 旧手册当成新版任务。

## 任务清单

| 编号 | 优先级 | 你需要做的事 | 怎样算完成 |
|---|---|---|---|
| C01 | P0 | 真 FastAPI入口、health、创建世界、state、统一错误外壳 | D改启动服务即可接入，不用重写字段 |
| C02 | P0 | SQLite保存、事务、版本、request去重 | 重复命中/付款只生效一次 |
| C03 | P0 | NPC/组织/装备按seed生成，动态ID，记忆和事实分开 | 通用数据，不把npc_02写死为唯一商人 |
| C04 | P0 | commands：检查存活、距离、冷却、物品归属 | 最终伤害/库存由你计算，不信任自报奖励 |
| C05 | P0 | 接 B 的计划，合法后建 Task；接 A 的报告完成结算 | 计划不是事件，未到达不发资源 |
| C06 | P0 | 事件来源、目击者、组织关系、死亡任务清理 | 无目击者不自动全知；死人不复活 |
| C07 | P0 | 保存/加载世界分支；动态迁入规则最小实现 | 重开世界一致，不丢装备历史 |
| C08 | P0 | 世界回合与 WorldDirector 的有限建议 | 不每帧调模型，不任意创造世界事实 |
| CE1 | 新P0 | 按EVALUATION_CONTRACT实现评测会话和路由 | 基础 v1 不破坏，评审与普通游戏隔离 |
| CE2 | 新P0 | 保存S0/P0、冻结配置/敌人/预算与hash | 第二轮条件一致，仅profile不同 |
| CE3 | 新P0 | 首轮实际结算→调用B学习→校验→保存P1 | 一轮最多学习一次，无前端手填成绩 |
| CE4 | 新P0 | 第二轮创建S0的新世界，加载P1，实际执行 | 敌人/资金/货物未继承上轮优势 |
| CE5 | 新P0 | 报告真实指标与来源，恢复整个P0+S0 | 旧请求作废，未来经验不泄漏 |
| C09 | P0 | 超时/断线、安全配置、Windows后端构建 | 不在锁内等模型；D可以启动真实后端 |
| C10 | P1 | 更复杂经济、新组织成立 | 学习和回退全部验收后再加 |


## 第一轮交付与顺序
先交可启动 `server.main:app` 与创建世界/状态/一条命令；再接一个 B 函数形成闭环。评测流程尽早用测试替身联调，但真实验收必须换成实际执行日志。

## 预期代码位置
`server/main.py`、`server/api/`、`server/world/`、`server/storage/`、`server/generation/`、`server/evaluation/`，以及 `tests/test_world.py`、`tests/test_evaluation.py`。

## 和别人交接
交 D：/docs、统一服务命令、真实测试世界、数据变化/错误样例；交 B：最小 AgentContext 与 Outcome；交 A：任务和命中规则。合并共享字段时更新样例和测试。
共同字段和方法在 docs/INTEGRATION.md。自己的想法与协议冲突时找 C/D，不私自改。

## 怎么自测
基础 contracts 回归 + tests/test_world.py + tests/test_evaluation.py；验证幂等、权限、死亡、同快照、自动学一次、回退隔离、不同条件不可比较。Windows打包须Windows实测。
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
