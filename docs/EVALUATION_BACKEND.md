# C 评审后端交接（步骤 10—12）

本文件说明已实现部分；字段仍以 shared/evaluation_protocol.py 为准。真实 Godot 动作与真实 B 模块尚待联测。当前默认使用公开规则 fallback：从合法策略中取 Q 最大者，首轮结束后只更新本次执行策略。没有按轮次强制选策。

## 操作顺序

1. POST /v1/evaluations：request_id、seed。返回 ready 会话和 S0 世界，记录 evaluation_id。
2. POST /v1/evaluations/{id}/runs：request_id、expected_evaluation_version、kind=first。返回 202，任务开始，data.state 包含商人 MOVE，若付费则还包含护卫 ESCORT。
3. D 把任务交给 A。A 报真实 HIT 或 TASK_REPORT，D 向当前 world_id 的 /commands 发送。不得提交分数、奖励或自选货物数量。ESCORT 是跟随保护商人的持续任务，随运输结束取消；C 不模拟护卫战斗，不凭雇佣自动减伤。
4. GET /v1/evaluations/{id} 轮询会话；/report 读取原始成绩与学习差异；/profile 查看 baseline_profile 和 active_profile。GET 不触发学习。首轮结束由后台自动学习，再变为 ready_for_second。
5. 用最新 evaluation_version POST /runs，kind=second。后端恢复 S0，只保留 P1，创建新的 world_id。D 清空旧角色与请求队列，按新 state 开始执行。
6. 第二轮结束后 report 展示两次交付率、费用、耗时、reward。货物交付率决定 improved/unchanged/worse；模式或冻结条件不同标为 incomparable。
7. POST /rollback：request_id、expected_evaluation_version、target=baseline（可省略）。停止运行任务、创建新 S0 分支、恢复完整 P0，状态 rolled_back。可再 POST /runs，kind=rollback_check，验证恢复后的策略；此轮不学习。

所有写操作支持原 request_id 重试。同 ID 不同内容返回 409；版本冲突需刷新。任务完成不意味着请求中可以附带任意奖励。历史审计在回退后仍存在，但 V0 的选策输入不包含 V1 经验。

## 冻结配置与接入

TransportScenario 位于 server/evaluation/scenario.py。默认同图 start=(8.5,8.5)、destination=(20.5,8.5)、threat=(14.5,8.5)，货物 10、初始金币 20、护卫费 5、每次命中损失 2、超时 45 秒、成功阈值 80%。这些是公开的开发参数，正式地点由 D 提供后在创建新评审前替换。两轮复用首次冻结的数据，不能中途改难度。

create_app(transport_scenario=..., choose_provider=..., learn_provider=..., evaluation_identity=...) 供组装注入。B 的 choose_transport(context, profile) 和 learn_transport(profile, outcome) 为无副作用纯同步函数，分别返回 TransportChoice、LearningUpdate；默认尝试 server.agents.transport_learning，缺失或异常使用明确 fallback。传入 evaluation_identity 应标明固定模型与提示词 hash；后端同时冻结代码和适配器 hash，条件改变拒绝继续同一会话。

护卫同意由冻结 guard_consents 表达本场景预授权；资金不够、未同意或护卫不可用时不提供 escort。雇佣实际扣除商人预算并记录护卫收到的金币；两轮都从原始预算重置。死亡或超时不送达，任务成功需要到达、存活和交付阈值。模型不能选择成绩。

客户端报告被视为可信游戏执行输入；后端校验地图、距离、武器、任务状态和去重，不能代替 Godot 对行走轨迹、碰撞及现实耗时的实际验收。此版没有另一套后端战斗模拟。

## 验证

python -m server.api.evaluation_smoke 会创建独立会话，通过合成客户端失败/到达报告验证自动学习、二轮与回退。输出明确标记 synthetic_client_reports。它不证明真实战斗中第二轮必然更好。

自动测试覆盖正常交付、货物损失/重复命中、死亡、超时、真实付款/授权、策略不强制切换、非法学习校验、重启、不重复学习、同快照二跑、完整回退、旧世界及在途学习失效。默认规则模式无需模型密钥。实际游戏验收与 Python 3.11 目标环境另记录。
