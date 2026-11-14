# R7 开发交接

所有状态仍以 FastAPI/SQLite 为权威；Godot 执行可见移动、命中和任务到达报告。没有引入第二套世界数据库。

`server/world/continuity.py` 增加契约、资源再生、消息发现、报案与 NPC 生计策略；由 living_world 初始化、事件结算和 heartbeat 调用。contracts/notices/safe_zones 直接随 StateView 序列化，元数据仍在已有 world_life 表，完整存档会一起保存。

新增 StateView 字段均有兼容默认值；SiteView 添加 capacity/regen_tick；ItemState 添加 quantity/durability。币栈 material_id=currency 是 wallets 的只读投影，不能通过普通 GIVE、出售或消费复制货币。散落的钱袋继续通过已有拾取结算进账。

新增 `/v1/worlds/{world_id}/interact`：WorldInteraction，action 为 GATHER/BOARD/PAY_HIRE/DISMISS/SUBMIT/GIVE_GOLD/REPAIR，target_id 为真实目标，amount 为金币赠送数量。所有写操作带原有 request_id 与 expected_world_version，同编号重试不重复结算。

新增 `/v1/worlds/{world_id}/shops/{npc_id}/sell`：沿用 ShopBuy 请求的 item_id/quote_id。报价附带 sellable 与 merchant_gold；装备中和受托物品禁止普通买卖。商人离开货箱后只能交易随身库存，不能远程销售留在原地的商品。

NPC 新意图：HIRE/PAY_HIRE/DISMISS/QUEST_INFO/SHARE_NEWS/PROPOSE_DELIVERY。参数候选引用当前世界实体；酬金可从当前话语中的数字添加为候选。提案通过校验后才创建契约或任务。FOLLOW 是持续任务，不因走到一次目标而完成，死亡、违约、解除或路径失败按真实状态处理。

人口：原有 19 名常驻/游荡 NPC + 4 名守卫、10 只初始野怪，初始总计34角色（包括玩家）。现有刷新预算保留，新守卫有新身份，不继承死者的私人记忆。

事件只由真实事实触发。目击者首先知道事件，抵达守卫附近才能报案；转述以 report 标记；守卫或其他知情者能传播消息。讨伐赏金先扣除委托人的真实资金。一般委托未被玩家发现前不会进入手记。

旅行手记过滤普通命中、随口对话、重复拾取等；内部审计来源与世界编年史仍保留，普通游戏界面只显示可读内容和已知线索。

网络保持世界写入顺序，后台模型仅计算提议，下一次 heartbeat 重新验证后落地。客户端限制同一攻击者积压多个不同攻击，并剔除队列中已经死亡目标的过期命中；攻击动画先在本地启动。

`game/assets/r7/manifest.json` 记录用户补充图的提取范围。没有依据图中文字修改阵营、尺寸协议或装备品质等级。Godot 与 Python 许可证随 Windows 运行包附带；.runtime 不进入源码仓库。
