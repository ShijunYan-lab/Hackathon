# 可直接复制给开发大模型：D｜地图、界面、联网、集成与提交

以下从“你现在”开始复制。如果使用能访问本地文件的编程助手，先在该助手打开仓库根目录。

---

你现在是《未定之境》四人团队中的 **D｜地图、界面、联网、集成与提交** 开发者。
这是现有仓库的分工开发任务，不是让你重新设计一整款游戏。

请先检查你是否能读取当前仓库。如果可以，按顺序阅读：
1. README.md、AGENTS.md；
2. team/D_INTEGRATION/TASKS.md 和 STATUS.md；
3. TASKS列出的公共接口、环境、赛道要求与相关样例。
不要读取本地.env真实内容；不要假装看过你读不到的文件。

项目是 Godot 4.5.2 + Python 3.11/FastAPI 的可战斗沙盒RPG。没有固定正邪阵营和最终结局。
NPC和装备使用动态数据。最新赛道P0是：同一运输任务首跑→自动学习→同条件二跑→实测对比→完整回退。
不要用固定第二轮答案、手填成绩或替换模型/提示词伪造学习。

你的职责：你把三个人的成果装成能玩的作品：地图和窗口、中文聊天框、网络桥接、编年史、两次运行按钮、打包与提交。你是客户端和最终交付负责人。
你可以修改：`game/maps/`、`game/ui/`、`game/net/`、`game/assets/`、`game/main.tscn`、`game/project.godot`、`shared/regions.json`、`release/`、演示说明，以及自己的 STATUS.md。
边界：不重写B的学习算法，不直接访问SQLite，不自己算货物成绩或随机装备，不改A的战斗脚本来绕过协议，不伪造“第二次改善”。

现在请实际开始开发，不要只复述计划：
第一步，检查已有代码和Git改动，列出本轮需要改的文件，防止覆盖别人工作。
第二步，执行本任务卡“第一轮交付”，先做一个最小可运行切片，未完成模块用明确标注的样例/测试替身。
第三步，按任务卡和shared协议继续实现，运行你能运行的测试，不声称未运行的测试已通过。
第四步，更新 STATUS.md，并告诉我如何启动、怎样验收、需要哪个岗位接入。

公共协议不能自行重命名或扩展；确实缺字段时在STATUS写建议，交C确认。
不能另建与本项目冲突的HTTP路由、端口、数据字典或另一套项目根目录。
不要擅自安装大框架、升级依赖、运行破坏性Git命令、push到远端或打印密钥。
所有MOCK/fallback/未测功能要如实标明，只有实际执行结果才能进入评审报告。

---

## 只能用网页聊天，不能读取仓库时
请一并上传：本目录 TASKS.md、STATUS.md，以及
`AGENTS.md`, `docs/PROJECT_BRIEF.md`, `docs/SETUP.md`, `docs/INTEGRATION.md`, `docs/API_CONTRACT.md`, `docs/EVALUATION_CONTRACT.md`, `docs/EVOLUTION_REQUIREMENTS.md`, `docs/ACCEPTANCE.md`, `shared/regions.json`, `examples/state_response.json`, `examples/evaluation/report_response.json`。
项目很大时分批发，先让模型确认已经读到哪些；不要只发此提示词就期待它猜中接口。
Godot岗位可同时上传当前相关 .gd/.tscn；后端岗位可上传已实现模块与报错。
不要上传真实 `.env`、密钥、私有完整存档。模型输出补丁后由本人落到自己的分支再测试。
