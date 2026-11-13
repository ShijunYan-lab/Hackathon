extends PanelContainer
## Read-only universal inventory: same panel works for player and all NPCs.
## Production D may replace its look while reusing Actor.inventory_for_ui().
var selected_actor = null
var content: RichTextLabel = null

const SLOT_NAMES: Dictionary = {
    "melee":"近战武器  [1]", "ranged":"远程武器  [2]",
    "offhand":"副手", "head":"头部", "chest":"胸甲", "hands":"手套",
    "legs":"护腿", "boots":"靴子", "accessory":"饰品",
    "ring_1":"戒指 1", "ring_2":"戒指 2"
}

func _ready() -> void:
    name = "EquipmentPanel"
    visible = false
    position = Vector2(362, 43)
    custom_minimum_size = Vector2(266, 305)
    size = custom_minimum_size
    mouse_filter = Control.MOUSE_FILTER_STOP
    var text := RichTextLabel.new()
    text.name = "Text"
    text.bbcode_enabled = true
    text.fit_content = false
    text.scroll_active = true
    text.custom_minimum_size = Vector2(252, 293)
    add_child(text)
    content = text

func toggle_for(actor: Node) -> void:
    if visible and selected_actor == actor:
        visible = false
        selected_actor = null
        return
    selected_actor = actor
    visible = true
    refresh()

func refresh() -> void:
    if not visible or selected_actor == null or not is_instance_valid(selected_actor):
        return
    var data: Dictionary = selected_actor.inventory_for_ui()
    var items: Array = data.get("items", [])
    var slots: Dictionary = data.get("equipment", {})
    var name_by_id: Dictionary = {}
    for item in items:
        name_by_id[str(item.get("id", ""))] = str(item.get("name", item.get("base_type", "?")))
    var lines: Array[String] = [
        "[b]人物背包 · %s[/b]" % str(data.get("name", "")),
        "[color=#e9bd57]金币：%d[/color]" % int(data.get("coins", 0)),
        "[b]装备槽位[/b]"
    ]
    for slot in SLOT_NAMES:
        var item_id: String = str(slots.get(slot, ""))
        var slot_label: String = str(SLOT_NAMES[slot])
        var item_name: String = str(name_by_id.get(item_id, "空"))
        var indicator: String = " ★" if str(data.get("active_weapon_slot", "")) == slot else ""
        lines.append("%s：%s%s" % [slot_label, item_name, indicator])
    lines.append("[b]背包物品（%d）[/b]" % items.size())
    for item in items:
        lines.append("• %s" % str(item.get("name", item.get("base_type", "?"))))
    lines.append("[color=#a5b5a8]Tab 关闭；Z/X 更换测试武器[/color]")
    if content != null:
        content.text = "\n".join(PackedStringArray(lines))
