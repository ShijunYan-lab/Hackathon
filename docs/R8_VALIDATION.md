# R8 验证状态（基于用户上传的 hackathon0426.zip）

## 已完成自动化验证

- Python `compileall` 通过，包括新增的物种注册模块和图标/代理动画生成脚本。
- `tests/test_r8_visuals_monsters.py`：6 项通过，检查无空白 RGBA 的透明 PNG、全部质量档装备图标、23 处地图装饰、5 种守卫原始帧、17 类怪物造型与 425 个动作代理帧、怪物属性与精英升级。
- `tests/test_a_module_assets.py tests/test_items.py tests/test_combat.py tests/test_continuity_r7.py`：42 项通过。
- `tests/test_contracts.py tests/test_evaluation_contracts.py tests/test_economy.py tests/test_world.py tests/test_world_consequences.py tests/test_transport.py tests/test_knowledge.py tests/test_agents.py tests/test_agent_runtime.py`：72 项通过。
- `tests/test_playable_r6.py`：24 项通过。
- `tests/test_overworld_integration.py tests/test_live_npc_integration.py`：15 项通过。

**合计 159 项选定 Python 测试通过；不代表全量测试通过。** 全量 `pytest tests -q` 尝试在集成测试阶段耗时过长而中止。未发现导入失败或本轮测试中明显的 Python 后端回归错误。

## 未完成 / 不做虚假保证

- Godot 4.5.2 引擎导入/解析：未运行，缺少可执行的本机 Godot 环境。
- Windows 启动器、真实游戏 F5、性能和帧率：未运行。
- 真实在线大模型调用和网络延迟：本轮未使用 API Key 做在线测试。
- 怪物攻击特效、碰撞体、动画与状态同步的真正画面验收：需用户本机验证。
- 动画代理帧只对原始透明立绘进行位移、旋转、亮度变化，非高级手工逐帧艺术；不可宣称全部敌人具有独立动作表。
- 装饰物件是只读的场景检查点，动态采集、箱子开合、经济与任务由 R7 服务端规则决定；装饰物件本身不提供可复制的免费材料。

## Windows 必验（D、A）

1. 关闭旧 8765 后端；运行 `Setup_Game.bat` 再运行 `Start_Game.bat`，确认正常进入游戏。
2. 用新存档打开玩家背包、NPC 商店、装备视图，检查金币、铁剑、头盔、胸甲、靴子、草药、铁矿、木头、石头均有图标。
3. 在地图上拾取物品，验证掉落物不是木箱占位；区分稀有装备掉落。
4. 灰橡镇、鸦渡镇、苔石猎营、旧王大道等地点检查真实装饰物和 E 查看提示。
5. 观察 5 类守卫的逐帧动画、所有普通与精英怪及 5 类敌对人类的动静、碰撞和追击。
6. 验证普通狼、野猪、蜘蛛、食尸鬼、沼泽潜伏兽和腐鸦不会显示为默认商人贴图或黑色方块。
7. 验证怪物离开安全区前的寻路、低血量撤退、远程攻击和死亡淡出。
8. 保存、退出、重新进入，确认资源、装备、金币与 NPC 生命状态仍由后端维护，不被美术替换破坏。

## 二进制补丁一致性

针对上传 ZIP 的源代码基线，`git apply --check` 成功，应用后**469 个新增/修改文件**的 SHA-256 与交付工作区完全一致。少量未修改的基准文档在 Git checkout 时因换行符自动转换而与原 ZIP 字节不同；这不影响增量补丁内容，也不意味着用户远程 main 的后续提交可以无冲突应用。
