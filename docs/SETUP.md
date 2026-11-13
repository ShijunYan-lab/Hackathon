# 统一环境与启动说明

这是本项目冻结的开发组合，不是“必须使用最新版”的推荐。沿用原附件，避免团队中途升级。

| 内容 | 统一选择 | 谁安装 |
|---|---|---|
| 游戏 | Godot 4.5.2 Standard，GDScript，Compatibility | A、D |
| 导出 | 与引擎一致的 4.5.2 导出模板 | D，A 备份 |
| 后端 | Python 3.11 独立环境 | B、C；A、D 运行 MOCK 时也需要 |
| Python 库 | 仓库 requirements.txt 固定直接依赖 | 安装后端的人 |
| 数据库 | Python 自带 SQLite | 不单独安装服务 |
| 网络 | 本机 HTTP，127.0.0.1:8765，业务 /v1 | 全员遵守 |
| 地图 | 32 像素一格；market / greenwood / moonwood | A、C、D |
| 画面 | 内部 640×360，初始窗口 1280×720，Nearest | A、D |
| 协作 | 一个 Git 仓库，每人一个工作分支 | 全员 |
| 模型 | B 选择一个已有权限的 API，密钥仅在后端本地 | B、C |

不需要 CUDA、PyTorch、Docker、Redis、向量库。若自己已有科研用 base 环境，不要破坏它。

## 1. 安装 Python 依赖
以下为 PowerShell，工作目录是能看到 README.md、requirements.txt 的仓库根目录。

已有 Conda：
```powershell
conda create -n unwritten python=3.11 -y
conda activate unwritten
python -m pip install -r requirements.txt
python -m pip check
```

没有 Conda但已有 Python 3.11：
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```
此后将文中的 `python` 替换成 `.\.venv\Scripts\python.exe` 即可，不需要改变系统执行策略。

## 2. 创建本地配置
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
B 在自己的 `.env` 填 API 地址、模型名和密钥。不要复制他人的真实密钥，不提交这个文件。
`.env.example` 只留空值和不敏感默认值，可以入仓。
已有配置时不要用复制命令覆盖。

## 3. 先验证附件
```powershell
python -m pytest tests -q
python -m tools.check_contracts
python -m tools.check_evaluation_contracts
```
测试通过仅证明当前协议、样例与基础 MOCK 的行为；不能证明游戏、LLM 或自动学习已完成。
详细验证范围看根目录 VALIDATION.md。

## 4. 启动已有的基础 MOCK
```powershell
python -m uvicorn tools.mock_api:app --host 127.0.0.1 --port 8765
```
另开终端：
```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```
`data.mode` 应为 `mock`。这是界面开发用的假后端，不会扣血、执行动作、保存到磁盘或学习。
MOCK 暂不实现 `/v1/evaluations`；D 先读 `examples/evaluation/`，C 实现对应真接口。

## 5. C 交付后启动真后端
约定命令：
```powershell
python -m uvicorn server.main:app --host 127.0.0.1 --port 8765
```
目前 `server/main.py` 尚未实现，这条是交付标准，不是已完成能力。
同一时刻只开 MOCK 或真后端其中一个，避免 8765 端口冲突。不要开启多个 worker。

## 6. A/D 导入游戏
Godot 项目管理器导入 `game/project.godot`。现在仅有空主场景，不会出现可玩 RPG。
D 补主场景、输入映射、Autoload；A 在 `game/tests/` 建独立测试场景，用 F6 测当前场景。
A 不新建另一个根 `project.godot`，不改 D 的配置；先用占位图形，不等素材。
中文输入和字体显示必须在 Windows 上实测。需要的授权字体由 D 自行准备，不附带本环境字体。

## 7. 最终环境锁定
B/C 在 Windows 跑通后，由 C 统一生成：
```powershell
python -m pip freeze | Out-File -Encoding ascii requirements.lock.txt
```
之后所有后端成员安装同一 lock 文件。不各自 `pip install -U`，也不在两次评审之间更新依赖。
构建用 `requirements-build.txt`，真实 Windows 打包由 C/D 完成。发布工具可以提交，产出的 EXE/录像不要放源码目录。
