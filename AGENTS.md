# 给所有开发大模型的共同工作约定

## 先识别你的岗位
先读根 README，再读 `team/<你的岗位>/TASKS.md` 与 `STATUS.md`。
未明确岗位时先请使用者指定 A/B/C/D，不能自动接管全部项目。
用户允许的是开发协作，不是擅自 push、删除历史、修改密钥或访问生产账号。

## 项目不能被改成什么
这是一款可战斗、可探索、自由输入对话的像素 RPG，不是聊天网页、固定剧情选择器或狼人杀。
NPC/组织/装备使用通用数据和动态 ID；没有固定正邪阵营，没有固定结局，没有角色等级。
任何已生成 NPC 可受攻击和永久死亡；世界必须承认后果。内容数量有开发上限不等于写死角色。
不再引入 Dopame、Phaser、另一个引擎、复杂 Agent 框架或大型训练系统。

## 当前文档优先级
1. 最新赛道要求与 `docs/EVOLUTION_REQUIREMENTS.md`。
2. 本文件和 `docs/PROJECT_BRIEF.md`：范围、所有权、行为原则。
3. `shared/protocol.py` / `shared/evaluation_protocol.py`：接口的可执行字段约定；对应 API 文档解释语义。
4. `docs/INTEGRATION.md`、`docs/ACCEPTANCE.md`、本人任务卡。
5. `docs/archive/` 仅供考古，不覆盖新版要求。
如果代码协议和当前语义文档冲突，记录问题找 C 协调，不能私自选一个改坏另一端。

## 文件所有权
A：game/actors、game/combat、game/controllers、game/tests。
B：server/agents、server/prompts、tests/test_agents.py、tests/test_learning.py。
C：server/main.py、server/api、server/world、server/storage、server/generation、server/evaluation；
   shared/*protocol*、公共 Python 依赖、后端测试和 API 文档。
D：game/maps、game/ui、game/net、game/assets、game/main.tscn、game/project.godot、
   shared/regions.json、release、演示文档。
本人可以更新自己的 team/*/STATUS.md。公共文件要找归属人改，不跨岗重写。

## 不变的工程边界
- A 负责碰撞与可见动作，C 负责最终血量、资源、死亡、物品归属。
- B 只返回回复、计划、记忆/学习提议，不能直接写世界库。
- D 统一发 HTTP，A 不自行创建网络服务或复制后端逻辑。
- 先遵守现有 `/v1/...` 路径、snake_case 字段、8765 端口和 32 像素格。
- 有“计划”不等于有“结果”；未执行动作不能记为成功。
- `request_id` 重试不换，重复命中不重复扣血，过期回复不能复活死人。
- `APP_MODE` 的 live / fallback / mock 必须如实显示。
- 模型输入只能含该 NPC 可知信息；不给所有 NPC 共用全知记忆。
- 模型可以说明行为依据，但不索要/展示隐藏推理链；用短摘要和来源事件。
- 评审运行的成绩由 C 从真实执行日志计算，B 和 UI 不能传入自选分数。

## 自进化验收不能作弊
第一次完整任务 → 真实结果 → 自动学习 → 同条件第二次任务 → 实际指标对比 → 可恢复学习前状态。
不能用 `if run_number == 2` 强制换策略，不能预置第二次成功，不能手调敌人或资源。
第一次失败只支持对已尝试策略的反馈；不能把没试过的策略写成“已证明成功”。
保存旧策略、学习记忆、检索可见性和缓存状态；回退不删除审计日志，但旧版本不能检索未来经验。
随机世界的多样性是产品特色，不是“第二次更好”的量化证明。

## 本次协作方式
先检查已有文件，列出自己要改的文件，再做一个可运行小切片。
不要一次给出几十个空函数后宣布完成，不要重生成别人已经实现的文件。
别人模块未完成时，用 shared/examples 或清楚标注的 test double 自测，不修改公共契约迁就假数据。
有需要增加的字段/动作/依赖，先在本人 STATUS 写变更建议，让 C/相邻岗位确认。
不读、不打印、不上传 .env 的真实内容，不把密钥放进提示词、截图或日志。
不要执行 `git reset --hard`、`git clean -fd`、force push、删除数据库等破坏性命令。

## 每次交付
写明：改了哪些文件、如何运行、实际跑了哪些测试及结果、没有测的部分、已知限制、需要谁接入。
更新本人 STATUS，给最小复现步骤；不要把“推测可用”写成“已验证”。
