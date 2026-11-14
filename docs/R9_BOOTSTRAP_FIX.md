# R9 在 Godot F5 启动时提示没有找到运行环境：修复说明

## 根因

R9 **源码 ZIP** 不包含 `.venv/` 或 `.runtime/python/`。旧版从 Godot 编辑器 F5 直接启动时，`game/maps/network_main.gd` 只能展示缺少 Python 环境的提示，不能在游戏界面自行安装。

## 本补丁修复

1. **Start_Game.bat** 会在缺少本地 Python 时自动调用现有 `Setup_Game.bat` 对应的 setup 脚本，验证依赖后继续启动。
2. Godot 主菜单新增 **「安装/修复运行环境」** 按钮（Windows）。点击才会打开 PowerShell 初始化项目目录的 `.venv`，游戏主线程不被安装过程阻塞。
3. 安装程序只在 `pip check` 成功后写出成功标记。游戏读取该标记后启动本版后端并重试健康检查；若安装失败，显示原因。
4. 使用当前项目目录的 Python 环境，不访问或修改其他 A/B/C/D 工作区，不覆盖旧存档，也不保存模型 API Key。

## 推荐方式（不需要补丁也能用）

```powershell
cd D:\VS_projects\R9-test\UnwrittenRealm_R9
.\Setup_Game.bat
.\Start_Game.bat
```

安装需要电脑上有 Python 3.11，并且首次下载 Python 依赖时需要网络。若手动安装遇到 pip 报错，应先解决依赖或网络问题。

## 使用带本修复的版本

- 将小补丁解压覆盖到 **R9 项目根目录**（包含 `Start_Game.bat` 的目录）。
- 双击 `Start_Game.bat`：缺少 Python 环境时可自动初始化。
- 也可以在 Godot 4.5.2 编辑器按 F5，主菜单点击「安装/修复运行环境」，等界面提示成功后再点「新游戏」。
- 如果提示后端启动失败，请检查项目 `runtime/` 下的日志，确认端口没有被旧服务占用。

## 测试边界

已检查脚本流程与静态引用；当前交付环境不是 Windows，不能替代 Windows PowerShell/Godot 4.5.2 实际运行验证。请在本机测试首次安装、安装失败反馈和 F5 后自动重连。
