# 真实生成式世界演示

在项目根目录运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File server/start_generative_demo.ps1
```

本机默认打开已验证的实验世界，使用 8781 端口和独立数据库 `runtime/generative-live.sqlite3`。E 对话、Tab 查看两件商品与余额、J 查看模型整理的手札。可继续自由输入需求，NPC 会结合已存记忆回应。实验世界不覆盖原 8765 游戏存档。

从头重跑真实演示：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File server/start_generative_demo.ps1 -Replay
```

它创建新世界，将玩家和一名 NPC 安排在木材点附近作为演示起始场景。接着通过真实 DeepSeek 对话提出采集与设计需求，Godot 执行采集，C 核验任务、消耗原料、创建物品、建立报价和结算金币。第二轮提供购买反馈，再采集、制作、购买。脚本不提交任务成功报告，不设置第二轮策略或成功结果。对话内容是演示输入；物品名称、描述、价格和模型是否执行不是预置答案。

外部脚本运行时由脚本安排回合，实验客户端每秒只读刷新状态以接收任务；普通交互启动恢复原游戏自动回合。模型拒绝、超时或任务失败时，脚本报告实际失败，不伪装成成功。再次运行会创建新世界，原存档保留。

## 已完成的真实验证（2026-11-14）

- 完整重跑中五次 NPC 调用均为 live。
- 第一轮模型生成“松纹旅木牌”，5 金币；玩家余额 20 → 15。
- 玩家反馈体积太大，偏好拇指大小、月牙图案、便携，预算 3 金币。
- 第二轮生成“月牙木牌”，3 金币；余额 15 → 12。两个采集任务均由 Godot 执行完成。
- 模型提炼反馈记忆；生成内容和已执行交易进入手札。历史较长时按批次整理，下一回合继续整理后续事件。
- 保存反馈前后两个快照；加载反馈前快照到独立分支后，第一件物品仍在、第二件不存在、余额恢复 15。
- 本机完整证据：`runtime/generative-live-report.json`，包含对话、物品、价格、存档和章节。文件不上传，因为它是个人运行产物。

这是一次有来源的经验适应演示：模型从反馈改变设计与报价。不是同条件运输成绩提升的量化证明，也没有训练模型权重。外观细节目前是物品描述，未生成新贴图；木雕没有饮用等机械效果。新的动态生产任务、可组合使用效果仍需继续实现。

## 文件与接入

- `server/api/generative_live_demo.py`：真实 HTTP 演示与结果断言。
- `server/api/generative_demo.gd`：加载现有正式 Godot 主场景的实验入口，没有重写 A/D 动作或界面。
- `server/start_generative_demo.ps1`：启动独立服务与演示。
- NPC 模型使用 B 已有 service；C 通过共享 CreationProposal 和 identity.creation_rules 提供生成能力。
- 提案、制作、报价、付款各有真实事件；付款仍需玩家接受。B 不写数据库。
