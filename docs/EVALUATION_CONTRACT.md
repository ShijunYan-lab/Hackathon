# 评审与学习接口合同 · evaluation-v1

这是**新增合同，业务尚待 B/C/A/D 实现**。不要认为已有 MOCK 包含这些路由。
字段以 shared/evaluation_protocol.py 为准，HTTP 外壳继续用 shared/protocol.Envelope。
基础游戏 v1 无改名；正常探索与评审可复用 /commands、/state 和任务系统。

## 1. 三种版本不要混用
`world_version`：具体世界的状态变更版本，基础游戏命令使用。
`evaluation_version`：本次两轮实验的流程版本，启动/回退接口使用。
`LearningProfile.version`：NPC 学习状态版本，V0→V1→恢复V0。
回退后 evaluation_version 继续递增，不能倒退到旧请求能重新生效的版本。

## 2. HTTP 约定

| 方法 / 路径 | 输入 | data 类型 | 状态变更 |
|---|---|---|---|
| POST /v1/evaluations | EvaluationCreateRequest | EvaluationStateData | 建场景 S0/P0，会话 ready |
| POST /v1/evaluations/{id}/runs | EvaluationRunRequest | EvaluationStateData | 首轮/第二轮/回退验证开始 |
| GET /v1/evaluations/{id} | 无写入 | EvaluationStateData | 查询当前状态、运行与世界 |
| GET /v1/evaluations/{id}/report | 无写入 | EvaluationReportData | 只读真实记录，不触发学习 |
| POST /v1/evaluations/{id}/rollback | EvaluationRollbackRequest | EvaluationStateData | 恢复 S0/P0，保留审计记录 |

POST /runs 返回 HTTP 202，表示开始或已排队，不是任务成功。
其余成功返回 200。格式/错误 Envelope 沿用原合同。
MOCK 样例中 world_id 可以是 null；真开始运行后 data.state 给出当前世界 StateView。
D 每 0.5–1 秒轮询 GET 会话，忙时不并发重复请求。主要游戏写命令仍按 C 队列提交。

create 请求示例：
```json
{"api_version":"v1","request_id":"req_eval_new","scenario_id":"transport_v1","seed":20261113}
```
runs 请求示例：
```json
{"api_version":"v1","request_id":"req_eval_first","expected_evaluation_version":0,"kind":"first"}
```
这些 ID 只是示例，真客户端每次新操作生成新 request_id，重试保留原 ID。

## 3. 流程状态
ready → first_running → learning → ready_for_second → second_running → complete。
任一步出错可 failed；rollback 恢复到 rolled_back；rollback_check 进入 rollback_running 后回到 rolled_back。
一次同会话只允许一轮执行，运行中不能另开第二轮，第一轮尚未学完不能第二轮。
第一次真实任务结束后 **自动** 进行学习，不需要人按“写参数”按钮。
第二轮结束先封存报告，本次测评不再自动改成 V2，避免混淆对比；正常世界可继续学习。
rollback_check 不学习，仅验证旧状态是否真恢复。

同 request_id 重试返回原操作，不能重复创建会话、启动任务、付款或学习。
同 request_id 携带不同内容应 409 REQUEST_ID_REUSED。
expected_evaluation_version 过期应 409 EVALUATION_VERSION_CONFLICT。

## 4. 从动作变成实测结果：C 的职责
A 只报合法 HIT/TASK_REPORT；C 按 world_id 对应 run，不能让客户端提交任意 delivered_ratio。
场景配置事先确定：货物总量、金币、护卫费用、出发/接收点、敌人配置、每次命中损失规则、
任务超时、成功阈值、初始 profile。建议放 server/evaluation/scenario.py 或共享只读数据。
C 决定真实“到达交付”“死亡”“超时”终止，只结算一次。
奖励函数由 RunMetrics 校验；task_success 由场景条件校验，不由模型判断。
source_event_ids 需真实存在且属于该轮；报告不能用上一轮或其他世界的事件顶替。

货物是 C 的任务载荷，初始/损失/交付都记事件。物理碰撞、命中与到站由 A 执行。
护卫费用是实际扣款；未获双方授权、钱不够或护卫死亡，escort 不在合法选项中。
C 必须记录选策失败与原因，不能默默给免费护卫。
选策执行仍需符合普通世界的同区、存活、资源、权限约束。

## 5. B/C 学习数据
LearningProfile：profile_id、learner_id、version、context_key、alpha、values、memories、retrieval_epoch。
本场景仅两个策略值，但结构可以用于以后扩展；暂时不随意加第三个选项。
TransportContext：合法策略、资金、护卫、已知事件。
TransportChoice：选了什么、基于哪个 profile 版本、引用哪些记忆、短依据。
TransportOutcome：真实轮次 ID、策略、指标、来源事件。
LearningUpdate：新旧版本、差异、更新后完整 profile、来源与解释。

B 的学习函数不得读“第二轮”字段决定策略，不得改源代码、系统提示词或模型。
C 校验变更：来源是首轮；from_version 是当前版本；只更新本次执行策略；
alpha 未改；角色/context_key未改；无凭空成绩或无来源经验。然后事务保存 P1。
first_finished 与 learning_committed 各有唯一事件，并以 source_run_id 防止学习重复应用。

## 6. 比较与回退
`comparable=true` 只有两轮都实测完成，且快照/场景规则/预算/模型与代码设置一致。
`improvement` 的判定以货物交付率为主；同时显示费用、耗时和reward，不能隐去代价。
缺数据是 not_measured，条件不同是 incomparable；不同条件不能下“学得更好”的结论。
first/second 两条 RunView 都保留原数据和来源，不能把第一次覆盖成更差成绩。

回退步骤：停止任务并作废在途响应 → 新建 S0 任务世界 → 还原完整 P0 →
清空/隔离学习摘要和检索缓存 → 恢复策略实际读取入口 → 状态 rolled_back。
保留已经发生的日志作审计，但不作为 V0 的可检索经验。
已有事件不删除；旧缓存、后台 reflect、B 的进程内变量不许悄悄保留 V1。

## 7. 常用业务错误码
EVALUATION_NOT_FOUND / INVALID_PHASE / RUN_IN_PROGRESS /
EVALUATION_VERSION_CONFLICT / SNAPSHOT_MISMATCH / LEARNING_NOT_READY /
METRICS_NOT_READY / LEARNER_DEAD / PRECONDITION_FAILED。
D 显示可读原因，不用一直转圈代替报错。

## 8. 当前提供与还没有的内容
已有：DTO、JSON Schema、样例、字段验证测试。
未提供：真实评测路由、战斗与运输、学习函数实现、版本数据库、UI。
已有 tools/mock_api 仍仅提供基础世界接口；不能因为 /docs 没列新路由就自行设计另一套。
