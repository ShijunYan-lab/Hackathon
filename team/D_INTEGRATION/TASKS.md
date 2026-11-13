# D｜地图、界面、联网、集成与提交

## 你负责什么
你把三个人的成果装成能玩的作品：地图和窗口、中文聊天框、网络桥接、编年史、两次运行按钮、打包与提交。你是客户端和最终交付负责人。

**工作分支：** `feature/d-integration`。
**可修改目录：** `game/maps/`、`game/ui/`、`game/net/`、`game/assets/`、`game/main.tscn`、`game/project.godot`、`shared/regions.json`、`release/`、演示说明。另可更新本目录 STATUS.md。
**不要碰：** 不重写B的学习算法，不直接访问SQLite，不自己算货物成绩或随机装备，不改A的战斗脚本来绕过协议，不伪造“第二次改善”。

## 开工前读
- `AGENTS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/SETUP.md`
- `docs/INTEGRATION.md`
- `docs/API_CONTRACT.md`
- `docs/EVALUATION_CONTRACT.md`
- `docs/EVOLUTION_REQUIREMENTS.md`
- `docs/ACCEPTANCE.md`
- `shared/regions.json`
- `examples/state_response.json`
- `examples/evaluation/report_response.json`

以上路径从仓库根目录算；不要把 docs/archive 旧手册当成新版任务。

## 任务清单

| 编号 | 优先级 | 你需要做的事 | 怎样算完成 |
|---|---|---|---|
| D01 | P0 | 接管空Godot工程，主场景、输入、Autoload和视口 | A能用相同工程；不新建第四套工程 |
| D02 | P0 | market/greenwood/moonwood地图、碰撞、出口、资源点 | shared/regions同步，出口不落墙里 |
| D03 | P0 | game_api.gd：HTTP队列、统一Envelope、错误/超时 | A只用信号；旧state不盖新state |
| D04 | P0 | 按ID构建WorldView、实例化A的Actor、同步道具 | 新NPC无需写专用场景；删除/死亡正确 |
| D05 | P0 | E打开中文对话、Enter发送、Esc关闭、等待提示 | 输入法能用，不边聊天边打人 |
| D06 | P0 | 血条、Tab背包/装备、F2编年史、F3调试 | 显示真实数据与来源，不给玩家泄露所有秘密 |
| D07 | P0 | 存档/加载、模式标识、断线恢复 | live/fallback/mock可区分，失联不伪造成功 |
| DE1 | 新P0 | 评审入口：首跑、二跑、报告、回退 | 按会话状态禁用非法按钮，不直接写参数 |
| DE2 | 新P0 | 轮询会话，切换任务世界时清旧角色/请求 | 第二轮画面确实来自S0新实例 |
| DE3 | 新P0 | 两次交付率/费用/耗时、学习差异、来源可展开 | 未测显示“未测”，不得显示虚假提升百分比 |
| DE4 | 新P0 | 演示回退并可重新执行V0，录真实两轮 | 正常游戏与评审不是两套假结果 |
| D08 | P0 | 合并主场景、导出Windows客户端、启动器 | 与C后端同包，第二台电脑能冷启动 |
| D09 | P0 | 素材授权、项目说明三行、录屏、提交、回执 | 11/15 08:00前完成，留上传余量 |
| D10 | P1 | 转场、装饰、美术扩展 | 只在端到端全部通过之后 |


## 第一轮交付与顺序
先把现有 MOCK 连通，显示占位人物和中文对话框；立即向 A 给输入/场景约定。先做能操作的框架，不为找素材耗掉第一轮。

## 预期代码位置
`game/net/game_api.gd`、`game/ui/`、`game/maps/`、`game/main.tscn`、`project.godot`、`shared/regions.json`、`release/` 启动和运行说明、`docs/demo_script.md`。

## 和别人交接
向 A 提供主场景挂载点、输入动作名、地图描述；向 C 提供请求和错误日志；向全员提供真游戏构建与可复现的联调步骤。
共同字段和方法在 docs/INTEGRATION.md。自己的想法与协议冲突时找 C/D，不私自改。

## 怎么自测
F5主场景、中文输入法、切图、对话中死亡/迟到请求、保存重开；按ACCEPTANCE逐项验收。不能把只接MOCK的界面标为完整游戏。
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
