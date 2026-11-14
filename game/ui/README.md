# D 界面

当前主场景使用 network_hud.gd，继承 realm_hud.gd 的铜色边框、深色底板、地点标题、全图、NPC 头像、滚动对话与中文 LineEdit；增加真实背包/装备/赠送/报价/制作、存档、篇章与运输评审。

E 打开，Enter/按钮发送，Esc 关闭；对话与地图锁定玩家。chat_submitted 现在连接 GameAPI，内容来自 C/B 返回值，等待时禁用重复提交；不再调用 npc_catalog 的本地 reply_to。模式按真实响应显示 live/fallback。Tab 行囊，J/F2 手札，F3 状态，F4 运输，F6/F7 存读档，F9 重连。

输入法组合文本未结束时不提交；使用 Godot 原生 LineEdit。当前自动检查覆盖中文字符串、空白过滤、话题、移动锁、Esc，未做 Windows 输入法候选窗人工验证。

Tab 点击武器后显示 weapon_portrait.gd 绘制的六种像素大图和后端真实属性。重开对话会加载当前 NPC 最近 20 轮私有历史，迟到回复按 NPC ID 核对。受击警告在人物头顶显示铜边深底对话框。背包、编年史与评审面板已集成；exploration_hud.gd 是第一版历史实现，当前不挂载。
