# 哪些东西放 Git，以及怎样发给四个人

## 1. 直接提交新包里的源码与文字资料
根 README、AGENTS、team、docs、shared、examples、tests、tools、game、server、release 中的说明/脚本、
requirements*.txt、.env.example、.gitignore、.gitattributes、.editorconfig 都适合版本管理。
`game/` 的合法素材是项目源文件，要提交；不要把整个 assets 忽略掉。
`shared/protocol.py` 是四个人共用的一份协议，不复制到各人目录。
原 Word 可自己留着阅读；仓库已经有 Markdown 归档，不需要再上传相同内容的 Word 和 ZIP。

## 2. 不要提交
真实 `.env`、模型密钥、登录凭证、数据库、私人对话日志、存档、Conda/Python 环境、
`.godot` 缓存、安装包、打包出来的 EXE/PCK、大录像、临时图片和解压用的旧 ZIP。
根 `.gitignore` 已覆盖常见情况。Godot `.gd.uid` / `.tscn` / `.tres` 与项目文件应保留。
`.gitignore` 不会自动移除已经提交过的文件。误提交密钥后需要立刻撤销/轮换密钥；
只删除文件或后补 ignore，不能消除历史泄漏。[R1][R2]

## 3. 推荐的第一次上传（全新空仓库）
网页新建 GitHub 仓库；开发期可设 Private，再按赛事要求调整。
不要在网页预先勾选 README、.gitignore 或 License，本包已经提供前两者，源码授权由团队决定。
解压后找到里面的 `unwritten-realm`，此目录下应直接出现 README.md，不要再套一层 team_starter。

在该目录 PowerShell：
```powershell
git init -b main
git status --short
git add .
git diff --cached --stat
git diff --cached --name-only
```
先检查暂存列表有没有 `.env`、存档、密钥或开发环境。确认安全再执行：
```powershell
git commit -m "chore: initialize team workspace and shared contracts"
git remote add origin https://github.com/YOUR_NAME/YOUR_REPOSITORY.git
git push -u origin main
```
把 `YOUR_NAME/YOUR_REPOSITORY` 替换成自己的真实仓库地址。认证按 GitHub 本机提示完成，
不要把 Token 写进 URL、源码或截图。[R3]

如果 Git 提示没有用户名/邮箱，用你自己的信息设置，不照抄他人的身份：
```powershell
git config user.name "Your Name"
git config user.email "YOUR_EMAIL"
```
设置后重新 commit；已经成功 commit 的不重复操作。

## 4. 远程已有 README 或已有项目
先 `git clone` 真实仓库到一个新目录，再把本包的内容复制进去，审查后 commit/push。
不要覆盖原 `.git`；本包本身没有 `.git`。
如果已有业务代码，先保留自己的修改，再按 MIGRATION.md 手动合并，尤其不要覆盖别人写好的
project.godot、main.tscn、README 或协议。不要 force push 来解决历史不一致。

## 5. 四人如何开始
仓库设置中把其他三个人加入协作者。每人在自己的电脑：
```powershell
git clone https://github.com/YOUR_NAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
git switch -c feature/a-gameplay
```
最后一行按岗位替换为：
A `feature/a-gameplay`；B `feature/b-agents`；C `feature/c-world`；D `feature/d-integration`。
本机项目文件夹名字可以与包名不同，依然以 README 所在目录为根。

## 6. 平时怎样交付
以 A 为例，先测试，再提交自己负责文件：
```powershell
git status --short
git add game/actors game/combat game/controllers game/tests team/A_GAMEPLAY/STATUS.md
git diff --cached --stat
git commit -m "feat(gameplay): implement first combat slice"
git push -u origin feature/a-gameplay
```
在网页开 Pull Request（合并申请），写清运行步骤、测试结果和待接入项。
C 审核后端/共享接口，D 审核客户端/发布。main 保持可运行，不四个人同时往 main 推。

合并别人更新前，先提交或妥善保存自己的工作：
```powershell
git fetch origin
git merge origin/main
```
有冲突找文件负责人一起处理，不要整段选择“保留我的版本”。A/D 不同时编辑同一 .tscn 或 project.godot。
Git 分支不等于目录隔离，也不等于会自动帮你们合并业务逻辑。

## 7. 大模型怎样读取仓库
最省事：每人在本机 clone 后，使用能读取本地工程的编程助手，打开仓库，再粘贴自己的 PROMPT。
它先读 AGENTS、公共资料和本人 TASKS，然后只在本人目录开发。
单纯把私有 GitHub 链接发给普通网页聊天，不代表模型有访问权限。不要发访问 Token。
只能聊天上传文件时，按本人的 PROMPT 中“无仓库访问时的附件清单”上传所需 Markdown、协议与样例。
对方看不到文件时必须说明，不能让它靠想象重新设计接口。

## 8. 发布物单独管理
源码仓库保存构建脚本和运行说明；大安装包、视频用比赛平台或发布附件交付。
确需版本管理大型源素材时再由 D 配置 Git LFS；本包没有强制 LFS，避免队友首次 clone 缺素材。
小型合法像素素材直接 Git 即可。第三方素材记录许可证和来源，不把没有再分发权的素材公开推送。
官方依据见 REFERENCES.md；团队协作规则为本项目约定。
