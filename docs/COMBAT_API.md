# 步骤 04 · 伤害与死亡接口

当前使用既有 POST /v1/worlds/{world_id}/commands 和 HitPayload。自动接口演示命令为 `python -m server.api.combat_smoke`，它通过合成碰撞报告调用真实后端、重复攻击直到一个新世界中的 NPC 死亡，检查去重、掉落和组织移除。输出含世界与事件查询地址，同时记录到被 Git 忽略的 runtime/combat_demo.json。该演示验证 HTTP 规则结算；Godot 碰撞与动画由 A/D 后续联测。

## 调用步骤

1. POST /v1/worlds 创建世界，读取 player_id、目标 NPC 的 id、玩家 equipped_item_id 和 world_version。
2. 提交以下结构。用实际 ID 替换占位值，并填入角色实际发生碰撞时的格坐标。
3. 从响应 data.state 应用权威血量、死亡、任务、组织和物品变化。下次新操作使用新的 request_id 与最新 world_version。

```json
{
  "api_version": "v1",
  "request_id": "本次请求ID",
  "expected_world_version": 0,
  "kind": "HIT",
  "payload": {
    "attack_id": "本次挥刀ID",
    "attacker_id": "实际攻击者ID",
    "target_id": "实际目标ID",
    "weapon_id": "当前装备武器ID",
    "region_id": "market",
    "attacker_tile": {"x": 8.5, "y": 8.5},
    "target_tile": {"x": 9.5, "y": 8.5}
  }
}
```

同 request_id 重试返回首次响应，包括首次 world_version。换 request_id 重报完全相同的 attack_id + target_id 时，返回当前 state，command_result.status=already_applied、applied=false 和原事件 ID；状态版本与事件数量保持原值。相同命中修改攻击者、武器、区域或原始位置后重报返回 409 ATTACK_ID_REUSED。

同一次挥刀可报告多个目标，写请求按顺序发送，并使用上次响应的 world_version。后续目标必须在首个合法命中起算的武器 cooldown_s 窗口内到达服务端，且该攻击者尚未开启下一次挥刀。超时返回 409 ATTACK_EXPIRED。新挥刀未过冷却返回 400 ATTACK_COOLDOWN。网络延迟可能导致后续目标过期，A/D 联测时需确认此窗口；规则使用后端接收时间。

## 规则与配置

server/world/combat_rules.json 定义近战欧氏距离 2 格、目击距离 6 格、玩家倒下时掉落材料比例 0.5。COMBAT_RULES_PATH 可指定其他规则文件。A/D 需要按 32 像素一格换算并对齐判定。世界创建时冻结规则；旧世界在首次成功 HIT 时保存规则快照，后续配置修改用于新世界。

攻击者与目标必须存活且属于当前地图，攻击者须持有并装备剑或斧。HIT 自带的当前位置会同步到世界，检查坐标有限、在地图范围且不落障碍格。移动与实际接触由可信本地 Godot 客户端报告。伤害为 max(1, weapon.damage - target.armor)，血量最低为 0。武器伤害与冷却在本次挥刀首次命中时记录。同次挥刀不能换武器，倒下角色的在途挥刀作废。

同区域、目标附近 6 格内的存活角色，加上攻击双方，记为事件目击者。当前采用距离近似，遮挡与 NPC 记忆检索待后续节点接入。

## 死亡结果与事件

NPC 或怪物死亡后保留档案，hp=0、alive=false、behavior=dead，清除当前任务与装备引用。取消其自身或以其为目标的 pending/running 任务，释放相关角色的任务引用。物品沿用原 item_id 落到死亡位置，组织移除成员，代表从存活成员中按 ID 稳定选取；组织无存活成员时变为 inactive。原关系与来源历史保留。

玩家倒下后恢复满血并回到当前单地图配置的 spawn_tile。随身 material 按物品 ID 排序，掉落数量为比例乘数量向上取整，保留武器和组织身份。正式地图的 spawn_tile 由 D 放在集市。报价系统尚待步骤 13 实现，当前世界没有可创建的报价。

一次命中可产生 hit_applied、actor_died / player_downed、task_cancelled、item_dropped、organization_membership_changed 和 player_recovered 事件，caused_by 指向此前的命中或死亡事件。所有后果、攻击去重记录、请求响应与世界版本在同一 SQLite 事务中提交。死亡后 CHECKPOINT/HIT 拒绝其继续行动。任务报告与对话的死亡检查将在步骤 07 的实现中接入。

## 测试与接入

`python -m pytest tests/test_combat.py -q` 覆盖 HTTP 伤害、最小伤害、重复/并发命中、多目标挥刀、冷却与过期、非法攻击、NPC 死亡、玩家恢复、任务和组织清理、事件溯源、事务失败回滚及重启。任务、材料等尚未开放操作的场景在测试数据库内准备，未作为实际游戏成绩。

A 提供实际命中报告，D 串行发送、处理错误、更新权威 state；C 当前后端已支持该数据链路。后续存档加载需复制冻结规则，并明确隔离旧世界攻击记录。
