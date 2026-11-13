# 原附件怎么迁入，以及哪里以新版为准

此仓库整理自原 `UnwrittenRealm_Interface_Starter_v1.zip`，不需要再把旧 ZIP 整体放进仓库。

| 原文件/目录 | 新位置/处理 | 说明 |
|---|---|---|
| team_starter/shared/protocol.py | shared/protocol.py | 原样保留，基础接口不破坏 |
| shared/protocol.schema.json | 同路径 | 原样保留，基础字段 Schema |
| shared/mock_openapi.json | 同路径 | 原基础 MOCK OpenAPI，不包含新评审接口 |
| shared/regions.json | 同路径 | 原样保留，D 后续统一维护地图描述 |
| examples/*.json | 同路径 | 原样保留，原示例不改成所谓实测数据 |
| tools/mock_api.py | 同路径 | 原基础 MOCK，不偷换成真实服务 |
| tools/check_contracts.py、tests/test_contracts.py | 同路径 | 原检查和 16 项测试保留 |
| requirements*.txt | 同路径 | 保留原固定依赖组合 |
| .env.example | 同路径 | 无密钥模板 |
| .gitignore | 根目录新版 | 扩充密钥、运行产物、导出包排除 |
| README.md | 根目录新版 | 从“接口附件”变为团队工作入口 |
| docs/API_CONTRACT.md | 同路径 | 基础接口语义；新版评审接口另列，不重命名旧接口 |
| docs/完整执行手册.md | docs/archive/team_plan_v1.md | 原完整手册只保留一份，旧时间表/范围不是最新指令 |
| docs/task_ownership.md | docs/archive/task_ownership_v1.md | 旧整合任务卡归档，新任务分为四份 |
| VALIDATION.md | docs/archive/validation_v1.md | 旧验证记录归档；根目录是本次验证 |
| 单独 Word | 不默认入仓 | 阅读用，已用 Markdown 归档保留内容 |
| 旧压缩包、渲染页图片 | 不入仓 | 不是源码，不让四人各自解一套 |

## 新增内容
`team/`：每岗 TASKS、PROMPT、STATUS。
`AGENTS.md`：四个大模型共同遵守的边界。
`docs/`：新范围、环境、Git 操作、内部交接、赛道要求、评测接口和验收。
`shared/evaluation_protocol.py`、`examples/evaluation/`、相应检查与测试：评审合同，不是评审实现。
`game/`：最小空 Godot 工程与责任目录。`server/`：分工目录，不虚构业务已完成。
`release/README.md`：交付责任与打包说明入口。

## 新版明确覆盖的旧说法
1. 旧版把“同一存档走出不同剧情”作为主要展示；新版必须另证明“同任务第二次更好”。
2. 旧版不做跨存档学习；正常世界仍独立，但评审的两个隔离任务实例必须共享版本化学习成果。
3. “长期反思晚点做”不能延后最小自动学习、对比、回退：这三项现在是 P0。
4. 旧对话里泛称 `/dialogue`、`/evaluation/start` 不是当前路由。
   基础路由以 `docs/API_CONTRACT.md` 的 `/v1/worlds/...` 为准；
   新评审路由以 `docs/EVALUATION_CONTRACT.md` 的 `/v1/evaluations/...` 为准。
5. 旧护卫案例里的货物交付率数字都是示意，不可填入正式成绩。

如果你已经开始写代码，不要整个覆盖现有项目。保留自己的代码，优先加入 team/、新版 docs/、
评审协议与忽略规则，再由 C/D 合并公共接口和工程配置。
