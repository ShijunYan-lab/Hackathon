# B｜NPC 本地终端运行手册

在 Windows PowerShell 启动：

```powershell
conda activate hks
cd E:\HKS\Hackathon
python -m server.agents.cli --seed 20261113
```

开局四个主场景各 5 名 NPC。路、河、矿山是连通节点。按 seed 生成身份、居所、装备、目标；每名角色分别维护记忆及策略值。终端中的行动、资源、交战和评分都是本地规则模拟。只有成功收到模型回复的 `asklive` 显示 `live`。

可以直接输入中文问题，例如「你现在在干啥」或「你遇见了谁」，效果和 `asklive` 一样。`ask <问题>` 使用离线规则答复。

每名 NPC 开局带有一条自己的经历和可用 `inspect` 查看的人格设定。可以依次问「你以前有什么经历？」、「你是个胆小鬼！」、「我刚才说了什么？」。成功的实时对话会写入当前 NPC 的私有记忆。换另一个 NPC 后，可以对比两人的经历和反应。角色扮演提示词见 [npc_persona.txt](../prompts/npc_persona.txt)。

## 测试一：人格、对话和记忆隔离

在新会话的 `npc-b>` 逐行输入：

```text
world
npcs
inspect
memory
你以前有什么经历？
你是个胆小鬼！
我刚才说了什么？
memory
talk npc_local_002 npc_local_001 听说遗迹发现了破旧石碑。
遗迹里有什么？你是亲眼见到的吗？
select npc_local_006
memory
exit
```

- `npcs` 应显示 20 名 NPC，每名开局已有一条私有背景记忆。默认选中的阿岚记得自己曾在东村下雨前把货收回屋内。
- 中文回复成功时应显示 `[live模型=deepseek-flash]`。挑衅后的具体措辞可变，用 `inspect` 对照性格，用「我刚才说了什么？」确认角色记住了玩家的上一句话。
- 石碑消息应被说成转述。切到西村的 `npc_local_006` 后，`memory` 应显示该角色的背景经历。阿岚听到的挑衅和石碑消息仍归阿岚。

`talk` 要求两名角色存活且位于同一地点。接收者收到带来源的转述。同源转述不会累加为另一份独立证据。`select <ID>` 切换当前角色，`inspect <ID>` 查看目标、位置、可用动作和策略，`events` 查看最近审计事件。`spawn [职业ID]` 在本地额外生成角色。

## 测试二：任务反馈、两轮进化与回退

重新启动 seed `20261113`，保留默认 NPC `npc_local_001`。以下命令每行输入一次。先运行 `step` 会改变首轮初始环境。

```text
memory
run woodcut
learn
memory
rerun
rollback
inspect
memory
events
step 10
exit
```

- `run` 支持 `woodcut`、`mine`、`trade`、`explore`。终端打印实际经过地点、结果、损血、消耗回合和事件 ID。
- `learn` 从刚完成的任务更新已执行策略的 Q 值，打印版本差和依据。同一结果只能学习一次。
- `rerun` 恢复首轮身体、其他角色、资源、时钟和每地点风险样本，再导入被测 NPC 保存的学习状态。策略选择使用同一函数。
- `rollback` 恢复该任务的首轮快照与认知版本，历史事件仍可供开发调试。
- `step [1–20]` 推进角色目标、采集、返家、面对面交流和有限资源刷新。角色也可能交易、抢劫和防卫；事件由本地规则结算。该命令显示耗时及模型请求次数。

### 现场展示时看哪里

| 核对项 | seed 20261113 的本地结果 |
| --- | --- |
| 首轮与复跑的表现 | 两次都拿到 2 份木材。损血 17 → 0，耗时 3 → 2 个模拟回合，奖励 0.260 → 0.870。 |
| 系统学到的内容 | `learn` 打印捷径 Q 值 0.650 → 0.338、版本 v0 → v1 和来源事件 ID。新会话的遇险事件是 `evt_local_0023`。用 `memory` 展示新增经验。 |
| 回退 | `inspect` 显示回到 v0，捷径 Q 为 0.650。`memory` 仍能看到收货的开局经历，这次砍树和学习经验已撤回。`events` 仍可看到遇险事件。 |

两轮之间输入 `learn` 触发程序更新，可以用 `memory` 查看经验，再输入 `rerun`。如需验证模型能引用任务经历，可在复跑后、回退前问「你第一次砍树时在遗迹遇到了什么？」。回退后再问一次，回答只应依据首轮前的可见记忆。赛题演示用的数字和计算过程见[反馈学习算法说明](B_LEARNING_ALGORITHM.md)。团队正式运输评审的数据由 C 的集成运行产生。

## 常见问题

- `npcd` 会提示未知命令。查看角色列表的命令是 `npcs`。
- 直接输入中文仍显示未知命令时，退出旧会话并重新启动 CLI。
- 模型调用失败时，可用 `ask <问题>` 查看离线规则答复。两轮任务与学习命令可以离线运行。
- `rerun` 需要先对当前 NPC 完成 `run` 和 `learn`。若演示中已用 `step` 推进世界，重新启动后再按固定种子的顺序操作。
- 看到「同一运行结果不能重复学习」时，上一份反馈已经使用过。要学习新一次执行结果，先输入 `run woodcut` 开始新任务。

## 本地模型配置

仓库根目录 `.env` 可填写 `APP_MODE`、`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_TIMEOUT_SECONDS`、`LLM_MAX_CONCURRENCY`。本机已用 DeepSeek 凭据验证 `deepseek-flash`，直连官方 API 时关闭思考模式。其他机器需自己的配置。环境变量优先于文件。超时、并发满、HTTP 错误和不可解析结果会明确提示。

## 集成验证

```powershell
python -m pytest tests/test_agents.py tests/test_learning.py -q
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
```

本次复测 B 定向测试 25 项通过，全仓 59 项通过，两项协议检查均通过。自动化测试使用替身验证模型输出的处理逻辑。真实 DeepSeek 对话用测试一验证。见 [实测记录与 C 接入说明](../../team/B_AGENTS/STATUS.md)。
