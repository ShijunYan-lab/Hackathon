# 《未定之境》整合修复 R6：启动、验收与合并

## 先说明交付状态

这份代码以你上传的 `Hackathon-main.zip` 为基础修改，ZIP 标记的原提交为
`1e2d84c5a01d2a11454364d398cabd6306449029`。保留 D 的整张地图、人物美术、
A 的移动战斗、B 的 Agent 基础和 C 的世界服务，补的是跨模块的真实玩法连接。

这是**源代码整合候选版**，不是已经在 Windows 导出验收的独立 EXE。
第一次需要 Python 和 Godot 4.5.2 Standard；依赖装好后可用 Start_Game.bat 启动。
本次环境实际通过 184 项 Python 测试、15 份协议样例和 160 处字面资源引用检查。
没有在这里运行 Godot、Windows 启动器或真实付费模型。必须完成下面的本机检查，
再把它作为比赛提交版本。不要把这些不同层级的验证混为一谈。

## 一、先用新目录测试，不覆盖任何人的分支

下载 `UnwrittenRealm_Integrated_R6_Source.zip`，在 PowerShell 运行：

```powershell
$zip = "$env:USERPROFILE\Downloads\UnwrittenRealm_Integrated_R6_Source.zip"
Expand-Archive -LiteralPath $zip -DestinationPath "D:\VS_projects\R6-test"
cd "D:\VS_projects\R6-test\UnwrittenRealm_R6"
code .
```

如果 R6-test 已存在，换一个新目录。不要用 -Force 覆盖你们正在开发的工作区。

先关闭旧版游戏和旧后端终端。若 8765 端口已有服务，启动器会核对版本，不会擅自
杀掉别人的 Python 进程。看到“old or different service”时，在原终端 Ctrl+C
关闭旧服务，再启动本版。

### 首次安装依赖

双击 `Setup_Game.bat`。它只在项目内建立 `.venv`，不改 Anaconda base。

已经使用 Conda 的同学，也可以明确选择 Python：

```powershell
# 在已激活的 Python 3.11 环境中执行
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

### 启动游戏

双击 `Start_Game.bat`。

首次会让你选择 **Godot 4.5.2 Standard 的 EXE**，不是 project.godot。
路径仅保存在本地 runtime/godot-path.txt，不进入 Git。启动器会启动本版后端、
检查 /health，再启动游戏。关闭游戏后只清理它自己启动的后端；如果后端原本就存在，
则不关闭它。

本版默认存档数据库为 `runtime/playable-r6.sqlite3`，不覆盖旧的
`runtime/overworld.sqlite3`。需要体验弱装备开局、箱子和新增人口，应当新建游戏；
没有承诺把旧存档无损升级为全部新玩法。

启动器尚未在 Windows 实测，因此也保留手动方式：

```powershell
# 终端一，先启动后端，保持窗口开着
.\.venv\Scripts\python.exe release/run_backend.py --db runtime/playable-r6.sqlite3

# 终端二检查，应该能看到 play_revision: r6、region_id: overworld
Invoke-RestMethod http://127.0.0.1:8765/health
```

然后使用 Godot 4.5.2 Standard 导入 `game/project.godot`，按 F5。
不要改用 `uvicorn server.main:app`；那不是这张整合地图的启动入口。

## 二、菜单和 API

主菜单可以输入玩家名字、选择男女外观、选择是否启用大模型，然后新游戏或读取存档。
新游戏会自动生成第一份存档。Esc 是暂停菜单，F6 保存；自由探索约 60 秒会尝试自动
保存一次。正在对话、等待请求或打开菜单时不会强行抢占保存。

大模型输入三项：

- API Base URL：HTTPS 基地址，例如服务商要求的 `/v1` 基地址；不要填整个
  `/chat/completions` 请求地址。
- 模型名：使用自己账号确实可调用的名称。
- API Key：输入自己的密钥。

当前适配的是 OpenAI-compatible Chat Completions 格式，不代表支持所有厂商的原生
接口。不开启模型也能玩规则模式，但复杂自由语言和真正的 LLM 决策需要有效网络与模型。
UI 会区分 live / fallback；配置保存成功不等于已验证模型调用成功，应实际对话检查。

菜单输入的密钥只留在本次服务进程内存，不写入数据库、存档或 Git；下次冷启动重新输入。
不要在录屏时展示密钥，不要将 `.env` 上传。项目仍兼容开发者私有 `.env` 配置，
但源代码包不包含它。

## 三、操作方式

| 操作 | 按键 |
|---|---|
| 移动 | WASD |
| 奔跑 | Shift |
| 闪避 | Space |
| 朝鼠标攻击 | 鼠标左键 |
| 切换已拥有的近战/远程武器 | 1 / 2 |
| 接近人物交谈，或靠近公共箱子打开 | E |
| 行囊、装备、使用药剂、赠送物品 | Tab |
| 地图 | M |
| 个人手札：事件、已知委托、编年章节 | J / F2 |
| 暂停、设置、保存、返回标题 | Esc |
| 保存 / 快速读取已记录的保存点 | F6 / F7 |
| 保留原项目的运输评审界面 | F4 |
| 请求失败后用相同请求编号重连 | F9 |

新玩家只有旧铁剑、布衣和 12 金币。没有远程武器时按 2，不应凭空得到弓箭。
11 个装备槽的数据结构仍保留；这轮真正实现的防具属性是胸甲槽，不宣称所有槽位都有
完整装备外观与属性系统。

## 四、按这个顺序做本机验收

### 1. 首次进入

新建男角色，再另建一个女角色；检查人物外观、中文名字、镜头、移动、奔跑、闪避和攻击。
打开背包应只有普通开局物品。不开模型时界面应说明是规则降级，不冒充真实 AI。

### 2. 对话和交易

到村内摊位附近，靠近人物按 E，直接输入：
“你叫什么名字？”“我想看看你的东西”“能给我打折吗？”
这些只是人工测试输入，不是游戏里强制出现的预设对话选项。

应当观察到：
- 不再到处显示姓名、职业、私人记忆或关系分值。
- 询问姓名后可以在后续对话标题中记住其身份，头顶仍不显示名字。
- 商人同意查看商品后打开真实商店，非商人不能凭空开店。
- 议价后的报价由后端根据交往记录和性格结算；不是模型说几折就几折。
- 反复要求打折不能无限叠加。敌意足够高的商人会拒绝交易。
- 购买后金币和唯一物品归属真正变化。钱不够不能买，重试不能重复扣款。

当前议价依据是结构化的关系记忆、实际事件与性格，不是把任意一段对话当价格指令。
“所有谈判方式都能被理解”不在离线规则模式的承诺范围内。

### 3. 箱子、掉落和探索

村镇与野外共有固定位置附近的种子化宝箱，内容有不同品质，商人旁有独立货箱。
公共宝箱可 E 打开；商人的活体库存必须经交易，不能直接当免费宝箱拿走。

取走金币和物品，关闭重开，再保存、退出、加载：不应重新出现。
商人死亡后已有货箱成为遗留物，不复制库存。钱袋拾取后应增加钱包，不留一枚可无限领的钱袋。

### 4. 战斗与人物反应

攻击一个人物，确认实际扣血后出现反击或逃离；附近合适守卫可接到呼救。
当前紧急应对是人格/血量驱动的快速策略，不等大模型每一帧回复；长期理解仍由 Agent 负责。
测试死亡动画后淡出、无碰撞、不可对话、物品可拾取；保存加载后仍死亡。
死亡角色的档案和事件保留，并不是从历史中抹掉这个人。

野外初始有 10 只怪物。它们使用规则战斗 AI，不为每只狼调用大模型。

### 5. 人口和世界事件

正常探索时世界约每 12 秒推进一次；打开菜单/对话/背包会暂停推进。
初始为原来的 15 名常驻人物 + 4 名游荡人物，另有 10 只怪物。
后续按间隔补充游荡人物与怪物，存活上限分别为 28、16；不是无限刷。

这一轮落地的是两种可组合委托：送货、帮助迷路旅人回去。
世界有可用资源、支付能力和可达路线时才创建任务；大 Agent 在线时可以提出 ERRAND，
断网则由明确标注的规则导演提出。两种方式共用同一套实际结算。

有可用同伴时商人可派 NPC 取货、移动、送达；不能“还没走过去就完成送货”。
部分委托留给玩家，必须交谈获得信息并接受。送货后从行囊将指定包裹赠送给收件人；
救助任务需与迷路旅人交谈，再由它沿路线回到委托人附近。报酬先从委托人资金托管，
不是无限生成金币。相关人物死亡、行动中断或超时，任务应失败而不是继续假成功。

### 6. 手札与编年史

按 J。应有亲历记录、已知托付、编年章节。
完成交易或战斗后，下一次世界推进把真实事件整理成章节，带来源 ID。
未获知的 NPC 私人事件不应因为玩家打开手札就变得全知。
当前规则归纳章节标记 rules；这不是伪造的实时模型叙事。

### 7. 保存与重新启动

用 Esc → 保存并退出。重启并加载，确认人物生死、装备、箱子、钱、关系和任务不丢失。
runtime 整个目录是本地数据；分享代码时不要上传它。重要现场存档另行备份此目录。

### 8. 保留赛道验收

F4 仍是原项目运输评测入口。需另做相同初始任务两次、自动学习、对比指标、恢复旧版本。
184 项测试包含原有评测测试，但没有替代你在 Godot 中的现场演示。随机剧情丰富
不等于第二次任务表现更好，两个目标仍须分别验证。

## 五、自动测试和报错材料

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m tools.check_contracts
.\.venv\Scripts\python.exe -m tools.check_evaluation_contracts
.\.venv\Scripts\python.exe -m tools.check_client_resources
```

或双击 `Test_Game.bat`。如果已经通过启动器选择过 Godot，它会继续做资源导入和 UI
冒烟测试；否则明确提示 Godot 尚未检查。它不会把跳过引擎检查报告成引擎通过。
可以显式指定：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\release\test_game.ps1 -GodotPath "D:\你的Godot目录\Godot_v4.5.2-stable_win64_console.exe"
```

本地测试若装有额外 pytest 插件、导致干扰，可使用：
`$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD="1"` 再运行测试。本次验证也是这个设置。
其中一个旧测试会写入 1000 次位置快照，在慢磁盘上可能耗时较长。

出现问题时先保留：
`runtime/godot.log`、`runtime/backend.stderr.log`、`runtime/backend.stdout.log`，
以及操作步骤、首条红色脚本错误、版本和是否启用模型。
发日志前检查并移除自己的密钥和不愿公开的聊天内容。不要只截最后一条连锁错误。

## 六、安全提交到你们的仓库

**先测试下载的完整源码，再将差异补丁应用到独立整合分支。不要用完整 ZIP 覆盖远程 main，
也不要 --force。** 这轮横跨 B/C/D/A 的连接，不适合藏在一个只叫“换角色贴图”的提交里。

在已有能联网的 Git 仓库中：

```powershell
cd D:\VS_projects\unwritten-realm
git status --short
```

确认没有未提交修改；有则先保存到原分支。然后逐段执行，失败就停下：

```powershell
git fetch origin --prune
# 只有 fetch 成功才继续，失败后的 origin/main 可能是旧缓存。

git switch -c integration/playable-r6 origin/main

$patch = "$env:USERPROFILE\Downloads\UnwrittenRealm_Integrated_R6.patch"
git apply --check $patch
# 只有检查成功才执行下一行
git apply $patch

git diff --check
git status --short
```

如果 `git apply --check` 不通过，可能是 D 已经继续改了相同文件。不要用覆盖方式掩盖冲突；
让 D 根据补丁与当前 main 合并。`docs/R6_HANDOFF.md` 列了所有模块边界。
测试通过后：

```powershell
git add game server shared release tools tests docs README.md README_R6.md AGENTS.md Setup_Game.bat Start_Game.bat Test_Game.bat
git diff --cached --stat
git diff --cached --check
git commit -m "feat: integrate playable menus trade world events saves and journal"
git push -u origin HEAD
```

GitHub 创建 PR：base 选 main，compare 选 integration/playable-r6，由 D 和 C 审查。
提交命令中没有 runtime、.env、.venv。不要把下载的 ZIP、Godot EXE、存档和密钥加入 Git。

如果你的 GitHub 连接仍失败：不必先解决 Git 才测试。先用完整源码运行；把 `.patch` 发给
能连接仓库的 D，让他在上述整合分支应用。ZIP 解压目录没有 .git，不要在那里随便
git init 后强推 main。

## 七、边界与未完成项

- 这次是可测的游戏闭环增强，不是无限内容生成器。只有送货、救助两种实际世界任务，
  不能让模型编造尚无执行器的行为并声称已完成。
- 角色帧、世界美术和大部分界面基于 D 上传的版本；新增箱子用程序画图，商店与菜单
  是基础可用 UI，并未完成商业游戏级美术打磨、音频制作、手柄适配。
- 装备栏结构保留，但不宣称每一种防具槽都有独立换装外观。
- 正式独立 Windows EXE + Python 后端打包仍需 D 在 Windows 完成；当前交付是
  Python/Godot 已安装后可用启动器启动的源代码版。
- 网络失效时进入可辨识的规则降级；真实模型的延迟、中文意图识别效果和费用需要
  使用你们实际选择的模型测试。
- 开发者可以查看私有状态用于验收；普通玩家不会直接看见人格数值和私人记忆。
