# 本次整理与验证记录

## 已实际完成
- 从用户已有的 Interface Starter v1 解压并迁移；21 个原始代码、样例、依赖文件逐字节未改。
- 新增四套 TASKS / PROMPT / STATUS，文件存在性检查通过。
- 运行 `python -m pytest tests -q`：**34 项通过**。
- 原 `tools.check_contracts`：**9 份 JSON 样例通过**。
- 新 `tools.check_evaluation_contracts`：**6 份 JSON 样例通过**。
- `tools.check_original_files`：21 个原文件 hash 相同。
- 在临时本地 Git 仓库检查 `.gitignore`：**17 个代表路径通过**。
  .env/缓存/日志/发布产物被忽略；.env.example/.gd.uid/场景/源素材/协议与任务卡不被忽略。
- 生成 evaluation_protocol.schema.json；新增模型不替换基础 protocol.py。

## 验证环境
本工作容器：Linux，Python **3.13.5**；Git 2.47.3。
直接依赖：fastapi 0.128.2、uvicorn 0.48.0、pydantic 2.13.5、
httpx 0.28.1、python-dotenv 1.2.2、pytest 9.0.2。
团队交付目标仍是 Windows + Python 3.11 + Godot 4.5.2；
**该目标环境仍须 B/C/D 在本机测试，不能把容器测试当作 Windows 验证。**

## 没有完成、也没有声称完成
没有完成真实Godot玩法、人物动画、地图、真实LLM调用、世界数据库、运输业务、
自动学习算法、两次运行的业务API、持久化版本回退或最终Windows发行包。
Godot空工程未在本环境启动验证；前后端未做真实端到端联调。
新增评审路由目前只是合同，原MOCK不提供它们。
未产生任何实际游戏成绩；样例中的数字只有初始化参数或单元测试输入。

## 提交边界
生成的是可交给团队开发的源码工作区ZIP，不是游戏发行包。
没有执行远程GitHub上传，没有创建任何远程仓库或修改权限。
没有包含.git历史、真实.env、模型密钥、数据库、运行存档、缓存、字体或第三方美术。

## 后续说明
check_original_files 只是此次迁移的原文件保真检查。
C以后通过审批修改共享协议或旧工具时，该检查可能故意失败；需同步记录新的协议版本，
而不是为维持旧hash否定合理开发。它没有被塞进pytest业务验收门槛。
