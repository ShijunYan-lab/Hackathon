# 步骤 13：交易、组织、制造和迁入接口

这些是 C 的真实规则，使用原 /v1 路径、世界版本和 request_id 去重。DTO 新增在 shared/world_protocol.py；原有命令字段不变。默认单地图，距离按格计算。

## 报价与组织同意

POST /v1/worlds/{id}/offers 带 request_id、expected_world_version、actor_id（提出者）、target_id（接收者）、kind 及以下字段。两人必须存活并在同图两格内；expires_in_ticks 默认 3，最长 20。

| kind | 字段 | 接受时结果 |
| --- | --- | --- |
| trade | item_id、price（非负整数） | 再查卖方所有权和买方资金，真实扣款、收款、转移物品，卸下卖方装备 |
| invite | org_id | 提出者必须是当前组织代表；接收者同意后加入 |
| relation | org_id、target_org_id、stance（trade/allied/neutral） | 两组织当前代表同意后才写入双向关系 |

创建只产生 pending 报价。返回 events[0].facts.offer_id；以既有 ACCEPT_OFFER 命令接受，payload={actor_id: 接收者, offer_id: ...}。入会也可用 JOIN_ORG 的 actor_id/org_id/offer_id。LEAVE_ORG 的 actor_id/org_id 退出并重新选代表，空组织 inactive。参与者死亡、代表变化或回合过期使报价失效；再次接受不能再次付款。资金不足或物品已转移时整个事务回滚。

GET /v1/worlds/{id}/economy 返回 wallets、offers、recipes、resource_needs。普通新人物初始金币 20，怪物 0；该规则在世界首次初始化时冻结。评审商人的钱包按场景预算初始化，护卫费实际从同一钱包扣除。所有经济表均纳入存档。交易当前仅一件物品与金币，暂不提供复杂市场、借贷和多物品交换。

## 制造与资源

POST /v1/worlds/{id}/craft：request_id、expected_world_version、actor_id、recipe_id。iron_sword 消耗两份 iron 和一份 wood，生成伤害 6、冷却 0.5 秒的可装备铁剑；herb_bundle 消耗两份 herb 生成药草包（消耗使用效果尚未实现）。材料必须来自真实库存，全部消耗后生成唯一物品及来源事件；失败不部分扣材料。

正式资源点由 D 配置；未提供 sites 的新开发世界生成 herb、iron、wood 各五份，位置靠近出生点。已有世界保留原资源点。采集仍走 MOVE/GATHER → TASK_REPORT，不直接凭计划发材料。

## B 的意图参数

- TRANSFER：原 item_id 仍立即赠送；同时带 price 时创建 trade 报价，等待接收者同意。
- PROPOSE_RELATION：target_id=目标组织，params={org_id: 本人代表的组织, stance: ...}。
- RESPOND_PROPOSAL：target_id=本人收到的 offer_id，params={}，接受提议。拒绝可暂不接受，等待过期。
- JOIN_ORG：target_id=组织，params={offer_id: ...}；LEAVE_ORG：target_id=组织，params={}。
- CRAFT：target_id=null 或本人 ID，params={recipe_id: ...}。

上下文只附加本人参与的未过期报价、自己所属组织或附近代表的组织。未知目标、越权代表、错误字段或非法价格记 decision_rejected，不执行部分效果。

## 世界导演

RESOURCE_NEED 只为缺少铁资源的存活组织创建一份铁的需求记录，重复 open 需求被拒绝。它不会凭空增加资源；当前需求是可追踪的待办，自动组织采购与履约属于后续扩展。

MIGRATION 必须满足：配置 location 带 migration_entry、位置属于当前地图且可走、NPC 存活数小于 npc_alive_limit，并引用一个未用于迁入的已死亡 NPC 事件。事务内再次检查，生成全新 NPC ID 和武器，保留原人物死亡档案；同一死亡来源不能反复生成人物。随机状态继续保存。没有入口配置时不会迁入，正式两个村庄、森林、遗迹的位置仍由 D 提供。

测试中地点配置与材料库存均注明为合成夹具；真实 Godot 地点/移动与 B 输出需组装验收。复杂经济、组织分裂和自动需求履约未标为完成。
