# D｜地图、界面、联网、集成与提交 · 工作记录

认领人：D（Codex 按用户明确的地图/美术优先级执行）
分支：main；B/C 合并提交 3ad3b1a / 979f158 已落在本地，集成修改在工作区，未 push。更新时间：2026-11-14。
当前状态：A/B/C 已接入 D 大地图。F5 使用 network_main.gd，真实 HTTP 与持久化战斗/物品/任务/存档已运行，两轮运输和基线回退已实测；全部 15 位 NPC 的真实 DeepSeek live 对话及独立记忆已验证。发布包、第二台电脑仍未验证。

## 当前交付：真实模型、独立记忆、受击反应和交互修复

见 [LIVE_NPC_UPDATE.md](../../release/LIVE_NPC_UPDATE.md)。按用户明确要求，已在忽略的本地 .env 接入 DeepSeek；不在代码/前端/文档中存密钥。补齐每 NPC/世界的持久对话、独立快照、旧评审会话恢复、驻地修复、正确握持点、渐隐投射物/所有 NPC 实体碰撞、六类武器大图与 NPC 警告/反击/返家。

本次跨模块变更为用户授权的 A/B/C 接入修复：A projectile 连续碰撞/渐隐；B provider 结构化响应与提示上下文；C 私聊表及快照、自卫任务/完成验证、旧普通世界加法升级和评审恢复信息。保留协议权责：B 提议，A 实际执行，C 结算；未重写运输学习算法。

验证：160 项 pytest，9+6 协议示例，24 项 Godot 原集成检查 + 14 项新功能检查。15/15 NPC 真模型 live；重启暗号回忆与跨 NPC 不泄露通过。新增 C 可见可达候选目标，真实模型让商贩走近玩家，A 实际移动 41.25px 后 C 确认成功。OpenGL 真模型中文对话、武器与警告框截图 v4_* 已检查。正式服务与普通存档恢复 connected=true / actors=16 / ordinary=true。备份、复现命令和限制见交付文档。

## 前一阶段：2026-11-14 B/C 合并与完整场景接入

见 [交付记录](../../release/MERGE_BC_INTEGRATION.md)。保留原地图、48×64 原图角色；统一为 overworld 连续坐标。新增 game/net/game_api.gd、maps/network_*.gd、reference_frames.gd、ui/network_hud.gd、后端地图导出与启动器。按用户本次明确的跨模块接入要求，最小补齐 A 的投射物 TileMap 碰撞/武器目录/受击方向，以及 C 六武器协议、可选 NPC 模板和本人职业上下文；未重写 B 学习算法。

验证：155 项 pytest、9+6 个协议示例、86 项地图回归、24 项真实 Godot HTTP 流程通过（含基线回退后的第三次实际执行与读档清除飞行投射物）。实际 B 对话返回 fallback；不宣称在线模型已验证。冷启动 connected=true / actors=16 / auto_start=true。OpenGL 界面截图见 release/previews/v3_*；运输实测 JSON 见 release/validation/network-results.json。

运行：Godot 打开 game/project.godot 后 F5，或根目录运行 powershell -File release/start_game.ps1。正式数据库 runtime/overworld.sqlite3；旧数据库和用户原有未提交修改已保留。主场景不再调用离线对白与 mock 伤害。

完整 D 岗中仍待办：打包 Windows 发行版、第二台电脑冷启动、人工 IME 候选窗验收、录屏与最终提交。本次用户要求的分支合并和大地图功能接入已经完成。

## 以下为先前地图与 A 合并阶段记录（不代表当前接入状态）

## 本轮完成

- [x] 320×224 格、10240×7168px，面积为前版四倍；71,680 原生 TileMapLayer 格、7,369 环境对象。
- [x] 双村庄各 12 座服务/居住建筑，双独立路线/桥梁，磨坊、农田/果园、河港、船、猎营、遗迹和墓园。
- [x] 大森林不铺道路；移除全部圆形/距离视野遮罩，全屏可见。树冠 Y 排序与近身淡化。
- [x] 四边实体空气墙、水岸/建筑脚部碰撞和玩家防越界。
- [x] 玩家使用用户第五张原图；15 NPC 使用村庄/森林/遗迹动作图，全部单帧 48×64。玩家四方向、行走、V 切换；NPC 待机、短距离行走，提取攻击帧供 A 接入。
- [x] 两镇、森林、遗迹部署 15 名可交谈 NPC；铜色深底对话 UI、头像、中文自由输入、快捷话题、滚动文本、E/Enter/Esc 与输入锁。
- [x] 内置 ImageGen 建筑/自然/细节图集已落盘；地形/原生场景由 Godot 绘制和编辑；来源和提示规格归档。
- [ ] 完整 TASKS P0、真实 HTTP/AI、战斗/死亡、背包/存档、评审两轮与回退、EXE/冷启动。

## 修改范围

D 所属 game/maps、game/ui、game/assets、game/main.tscn、game/project.godot、shared/regions.json、release 和本 STATUS。未改 A/B/C 的业务实现。

入口为 main.tscn → maps/realm_main.gd，布局源 realm_layout_v2.gd，经 world_layout.gd 暴露；运行加载已保存 realm.tscn。旧 main.gd / field_of_view.gd / exploration_hud.gd 和 32×48 图集保留作历史参考，当前不挂载。

## 实际验证

本机 Windows，Godot 4.5.2.stable.official.6ce3de25a，Compatibility / OpenGL 3.3，NVIDIA RTX 5060 Ti。

- 编辑器 headless 导入和主场景 smoke 启动通过。
- Godot 地图烘焙：71,680 tiles / 7,369 objects / 10240×7168px。
- maps/qa/exploration_checks.gd：**86 passed / 0 failed**，实际 CharacterBody2D 输入过双桥、河水/四边实体碰撞、移动/奔跑、对话锁/中文文本/话题/Esc、外观尺寸、出生出口、村间双路线及全部 NPC 连通。
- capture_views.gd / capture_actors.gd：真实 OpenGL 截图，13 个场景/UI/外观视图、7 张角色对照与全帧表；目视复查建筑、森林、遗迹、河港、聊天、玩家方向及 180 帧 NPC 动作。
- 当前日志 release/validation/*-v2.log，截图 release/previews/v2_*.png。旧版 44 项结果和旧截图不代表当前版。
- 公共 Python 检查未重跑；第一版尝试时系统 Python 3.14.7 缺 pytest / pydantic，未改公共依赖，不宣称通过。

未验证：真实 B/C 联网、A 战斗、存档/学习评审、Windows 输入法候选窗人工交互、EXE 导出、第二台电脑。

## 接入与限制

A：替换 Main/World/Entities 下 D 的探索替身；角色帧 48×64，脚部约 18×14，Y 排序，输入/锁定/检查点接口详见 game/maps/README.md。NPC appearance_key 与实例 id 分开；攻击动作图已备好但无伤害。

C：shared/regions.json 格式与 ID 不变，market=320×112（偏移0,112），greenwood=160×112（偏移0,0），moonwood=160×112（偏移160,0）。tile 保持局部单位，旧出生/资源/评审快照需适配并联调。local_preview_player / preview_* 不是服务器 Actor ID。

B/C：当前离线对话根据每个 NPC 的独立本地文本回应，明确显示“离线对话”。Hud.chat_submitted(npc_id,text) 可供后续统一网络层接入；没有伪造 LLM 请求或学习结果。

角色来自用户原图；48×64 适配、去背景、镜像和补充行走会改变像素，不能承诺与原大图逐像素相同。房屋仅外景，船仅环境物件。

最小复现：Godot 导入 game/project.godot → F5 → WASD/方向键、Shift、E、Enter、Esc、M、V。验收路线与截图索引：release/EXPLORATION.md。

## 2026-11-14：按用户要求合并 A 分支

已 fetch 并快进合并 `origin/feature/a-sprites-48x64` 到本地 main，HEAD 从 bc5326f 更新为 d1bcf52，含 94601d4 / d1bcf52 两个提交、94 个文件变更。未 push，未合并 B/C 分支，未创建额外提交。

286 个原本地修改文件已备份至 `D:\DBIS\_backups\Hackathon-before-a-sprites-20261114-104924`，恢复后逐一 SHA-256 相同。按 A 接入文档约定，保留 D 的正式 main、项目配置和大地图说明；A 的 Actor/战斗/装备模块与独立演示均已进入同一工程。

实际验证：Godot 导入通过；A 六种外观的动画加载检查通过；A 独立演示启动并执行 600 固定帧通过；D 地图 86/86 复测通过；Python 图集检查通过；A 的五项无依赖静态测试直接调用通过。修正该静态测试将 .gdshader 误识别为 .gd 的路径正则；未修改 A 业务脚本。由于缺 pytest/pydantic，协议模型检查一项跳过，未执行完整 pytest。

当前 F5 仍为 D 地图；A 演示在 `game/tests/a_open_world_demo.tscn` 按 F6。战斗 Actor 尚未接管 D 的探索替身，真实 AI/后端仍未连接。完整记录和日志索引见 `release/MERGE_A_SPRITES.md`。
