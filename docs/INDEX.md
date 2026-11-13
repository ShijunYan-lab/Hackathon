# 文档导航：各看哪些文件

| 用途 | 读这些 |
|---|---|
| 全员入门 | 根 README → AGENTS → PROJECT_BRIEF → SETUP |
| 认领工作 | TEAM_BOARD → 对应 team/*/TASKS.md |
| 交给大模型 | 对应 team/*/PROMPT.md；让模型在仓库中按顺序读文件 |
| A 和 D 联调 | INTEGRATION 第 1、3、4 节；API_CONTRACT；examples |
| B 和 C 联调 | INTEGRATION 第 2 节；shared/protocol.py；EVALUATION_CONTRACT |
| 证明自进化 | EVOLUTION_REQUIREMENTS → EVALUATION_CONTRACT → ACCEPTANCE |
| 上传和协作 | GIT_GUIDE → MIGRATION |
| 回顾原文 | archive/team_plan_v1.md；里面的旧优先级与评审段落已由新版覆盖 |

当前文档均使用 UTF-8 Markdown；源代码和接口不用复制到四份目录，大家引用同一份。
`team/` 放职责和提示词，`game/`、`server/` 放真正代码，`shared/` 放跨人共享约定。
