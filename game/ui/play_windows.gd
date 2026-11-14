extends CanvasLayer
## Standard local-game screens. API keys are never written to ConfigFile.
var world
var modal_open: bool = true
var screen: String = "title"
var shade: ColorRect
var frame: PanelContainer
var column: VBoxContainer
var status_label: Label
var name_input: LineEdit
var appearance: OptionButton
var use_model: CheckBox
var base_input: LineEdit
var model_input: LineEdit
var key_input: LineEdit
var known_config: Dictionary = {}
var pending_start: Dictionary = {}
var pending_save: String = ""
var after_save: String = ""
var selected_item: String = ""
var trade: Dictionary = {}
var chest: Dictionary = {}
var page_after: int = 0
var next_after: int = 0
var page_history: Array[int] = []
var font: SystemFont

func _ready() -> void:
	layer = 25
	font = SystemFont.new()
	font.font_names = PackedStringArray(["Microsoft YaHei", "Noto Sans CJK SC", "sans-serif"])
	shade = ColorRect.new()
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.035, 0.045, 0.06, 0.94)
	shade.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(shade)
	frame = PanelContainer.new()
	frame.position = Vector2(38, 16)
	frame.size = Vector2(724, 418)
	var style = StyleBoxFlat.new()
	style.bg_color = Color("242523")
	style.border_color = Color("b79864")
	style.set_border_width_all(2)
	style.content_margin_left = 22
	style.content_margin_right = 22
	style.content_margin_top = 14
	style.content_margin_bottom = 12
	frame.add_theme_stylebox_override("panel", style)
	var theme = Theme.new()
	theme.default_font = font
	theme.default_font_size = 13
	frame.theme = theme
	frame.add_theme_font_override("font", font)
	frame.add_theme_font_size_override("font_size", 13)
	add_child(frame)
	open_title()

func rebuild(kind: String, title: String) -> void:
	screen = kind
	modal_open = true
	shade.show()
	frame.show()
	if is_instance_valid(world.hud):
		world.hud.close_dialogue()
		world.hud.close_panel()
		world.hud.map_open = false
	for child in frame.get_children():
		frame.remove_child(child)
		child.queue_free()
	column = VBoxContainer.new()
	column.add_theme_constant_override("separation", 7)
	var scroll = ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	frame.add_child(scroll)
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(column)
	frame.size = Vector2(724, 418)
	var heading = Label.new()
	heading.text = title
	heading.add_theme_font_size_override("font_size", 22)
	heading.add_theme_color_override("font_color", Color("dac598"))
	column.add_child(heading)
	status_label = null

func label(value: String, parent: Node = null) -> Label:
	var control = Label.new()
	control.text = value
	control.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	(parent if parent != null else column).add_child(control)
	return control

func row() -> HBoxContainer:
	var control = HBoxContainer.new()
	control.add_theme_constant_override("separation", 8)
	column.add_child(control)
	return control

func button(parent: Node, caption: String, callback: Callable, disabled: bool = false) -> Button:
	var control = Button.new()
	control.text = caption
	control.custom_minimum_size = Vector2(112, 29)
	control.disabled = disabled
	control.pressed.connect(callback)
	parent.add_child(control)
	return control

func input_line(parent: Node, hint: String, value: String = "", secret: bool = false) -> LineEdit:
	var control = LineEdit.new()
	control.placeholder_text = hint
	control.text = value
	control.secret = secret
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	control.custom_minimum_size.y = 28
	parent.add_child(control)
	return control

func open_title() -> void:
	rebuild("title", "\u672a\u5b9a\u4e4b\u5883  /  THE UNWRITTEN REALM")
	label("\u6ca1\u6709\u5199\u597d\u7684\u7ed3\u5c40\u3002\u4f60\u7684\u884c\u52a8\uff0c\u4f1a\u7559\u5728\u8fd9\u4e2a\u4e16\u754c\u3002")
	var identity_row = row()
	name_input = input_line(identity_row, "\u4f60\u7684\u540d\u5b57", "\u65c5\u4eba")
	name_input.max_length = 30
	appearance = OptionButton.new()
	appearance.add_item("\u7537\u6027\u89d2\u8272", 0)
	appearance.add_item("\u5973\u6027\u89d2\u8272", 1)
	identity_row.add_child(appearance)
	var previews = row()
	for skin in ["player_male", "player_female"]:
		var picture = TextureRect.new()
		var atlas = AtlasTexture.new()
		atlas.atlas = load("res://assets/characters/" + skin + ".png")
		atlas.region = Rect2(0, 0, 48, 64)
		picture.texture = atlas
		picture.custom_minimum_size = Vector2(48, 64)
		picture.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		previews.add_child(picture)
	label("\u65b0\u65c5\u9014\u4ece\u65e7\u94c1\u5251\u3001\u5e03\u8863\u548c\u5c11\u91cf\u91d1\u5e01\u5f00\u59cb\u3002\n\u4eba\u7269\u7684\u540d\u5b57\u4e0e\u7ecf\u5386\uff0c\u9700\u8981\u4f60\u81ea\u5df1\u53bb\u4e86\u89e3\u3002", previews).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	model_fields()
	var buttons = row()
	button(buttons, "\u65b0\u6e38\u620f", start_new)
	button(buttons, "\u8bfb\u53d6\u5b58\u6863", request_saves)
	button(buttons, "\u9000\u51fa", func(): get_tree().quit())
	status_label = label("\u6b63\u5728\u68c0\u67e5\u672c\u5730\u4e16\u754c\u670d\u52a1\u2026")

func model_fields() -> void:
	use_model = CheckBox.new()
	use_model.text = "\u542f\u7528\u5927\u6a21\u578b\uff08\u4e0d\u542f\u7528\u65f6\u4e3a\u660e\u786e\u6807\u6ce8\u7684\u89c4\u5219\u6a21\u5f0f\uff09"
	use_model.button_pressed = bool(known_config.get("configured", false))
	column.add_child(use_model)
	var endpoints = row()
	base_input = input_line(endpoints, "API Base URL (HTTPS)", str(known_config.get("base_url", "")))
	model_input = input_line(endpoints, "\u6a21\u578b\u540d\u79f0", str(known_config.get("model", "")))
	key_input = input_line(column, "API Key - \u4ec5\u5728\u672c\u6b21\u8fd0\u884c\u5185\u5b58\u4e2d\u4f7f\u7528", "", true)
	label("\u652f\u6301 OpenAI-compatible chat/completions\uff1b\u4e0d\u4fdd\u5b58\u5bc6\u94a5\u5230\u5b58\u6863\u3002").add_theme_font_size_override("font_size", 11)

func start_new() -> void:
	if not world.api.connected or not world.api.idle():
		notice("\u4e16\u754c\u670d\u52a1\u5c1a\u672a\u5c31\u7eea\uff0c\u8bf7\u5148\u542f\u52a8\u540e\u7aef\u6216\u7b49\u5f85\u5f53\u524d\u8bf7\u6c42\u5b8c\u6210\u3002")
		return
	pending_start = {"seed": int(Time.get_unix_time_from_system()) % 2147483647,
		"player_name": name_input.text.strip_edges() if not name_input.text.strip_edges().is_empty() else "\u65c5\u4eba",
		"appearance": "female" if appearance.selected == 1 else "male"}
	if not configure_model(): pending_start = {}

func configure_model() -> bool:
	if not world.api.idle(): return false
	var enabled = use_model.button_pressed
	if enabled and key_input.text.strip_edges().is_empty() and known_config.get("configured", false) and base_input.text.strip_edges() == known_config.get("base_url", "") and model_input.text.strip_edges() == known_config.get("model", ""):
		finish_configuration()
		return true
	if enabled and (key_input.text.strip_edges().is_empty() or base_input.text.strip_edges().is_empty() or model_input.text.strip_edges().is_empty()):
		notice("\u8bf7\u586b\u5199 API \u5730\u5740\u3001\u6a21\u578b\u540d\u548c\u5bc6\u94a5\uff0c\u6216\u5173\u95ed\u5927\u6a21\u578b\u5f00\u5173\u3002")
		return false
	world.api.call_api("configure_model", "/v1/local/model", {"enabled": enabled, "base_url": base_input.text.strip_edges(), "model": model_input.text.strip_edges(), "api_key": key_input.text.strip_edges()})
	key_input.text = ""
	notice("\u6b63\u5728\u5e94\u7528\u672c\u6b21\u8fde\u63a5\u914d\u7f6e\u2026")
	return true

func finish_configuration() -> void:
	if pending_save == "list":
		pending_save = ""
		_request_saves_now()
		return
	if not pending_start.is_empty():
		var body = pending_start.duplicate(true)
		pending_start = {}
		world.api.call_api("create", "/v1/worlds", body, false, true)
		notice("\u6b63\u5728\u5efa\u7acb\u65b0\u4e16\u754c\u2026")
	else: notice("\u914d\u7f6e\u5df2\u751f\u6548\uff1b\u4e0b\u6b21\u5bf9\u8bdd\u4f1a\u9a8c\u8bc1\u771f\u5b9e\u8fde\u63a5\u3002")

func request_saves() -> void:
	if screen == "title" and is_instance_valid(use_model):
		pending_save = "list"
		if not configure_model(): pending_save = ""
		return
	_request_saves_now()

func _request_saves_now() -> void:
	if not world.api.connected: notice("\u8bf7\u5148\u8fde\u63a5\u4e16\u754c\u670d\u52a1\u3002"); return
	world.api.call_api("list_saves", "/v1/saves")

func show_saves(data: Dictionary) -> void:
	rebuild("saves", "\u65c5\u9014\u5b58\u6863")
	var scroll = ScrollContainer.new()
	scroll.custom_minimum_size = Vector2(670, 285)
	column.add_child(scroll)
	var list = VBoxContainer.new()
	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(list)
	for slot in data.get("saves", []):
		var identifier = str(slot.save_id)
		button(list, str(slot.player_name) + "  |  " + str(slot.label) + "  |  " + str(slot.tick), func(): load_save(identifier))
	if data.get("saves", []).is_empty(): label("\u8fd8\u6ca1\u6709\u4fdd\u5b58\u8fc7\u65c5\u9014\u3002", list)
	button(column, "\u8fd4\u56de", func(): open_title() if world.state.is_empty() else open_pause())

func load_save(identifier: String) -> void:
	if not world.api.idle(): return
	world.api.call_api("load", "/v1/saves/" + identifier + "/load", {"api_version": "v1"}, false, true)

func open_pause() -> void:
	rebuild("pause", "\u65c5\u9014\u6682\u505c")
	label("\u5730\u56fe\u3001\u751f\u6b7b\u3001\u7269\u54c1\u548c\u8bb0\u5fc6\u5c06\u968f\u5b58\u6863\u4fdd\u7559\u3002")
	button(column, "\u7ee7\u7eed\u6e38\u620f", close)
	button(column, "\u4fdd\u5b58\u6e38\u620f", world.save_game)
	button(column, "\u8bfb\u53d6\u5b58\u6863", request_saves)
	button(column, "\u6a21\u578b\u8bbe\u7f6e", open_settings)
	button(column, "\u4fdd\u5b58\u5e76\u8fd4\u56de\u6807\u9898", func(): save_and_leave("title"))
	button(column, "\u4fdd\u5b58\u5e76\u9000\u51fa", func(): save_and_leave("quit"))
	status_label = label("")

func open_settings() -> void:
	rebuild("settings", "\u5927\u6a21\u578b\u8fde\u63a5")
	model_fields()
	button(column, "\u5e94\u7528\u914d\u7f6e", configure_model)
	button(column, "\u8fd4\u56de", open_pause)
	status_label = label("")

func save_and_leave(destination: String) -> void:
	if not world.api.idle(): notice("\u64cd\u4f5c\u5c1a\u672a\u5b8c\u6210\uff0c\u8bf7\u7a0d\u540e\u518d\u4fdd\u5b58\u3002"); return
	after_save = destination
	world.save_game()

func show_shop(data: Dictionary) -> void:
	trade = data
	selected_item = ""
	rebuild("shop", "\u5546\u4eba\u7684\u8d27\u7bb1")
	label("\u91d1\u5e01 %d  |  \u672c\u6b21\u4f18\u60e0 %d%%  |  \u62a5\u4ef7\u7531\u5b9e\u9645\u5e93\u5b58\u548c\u4ea4\u5f80\u8bb0\u5f55\u51b3\u5b9a" % [int(data.gold), int(data.discount_percent)])
	var list = ItemList.new()
	list.custom_minimum_size = Vector2(668, 244)
	column.add_child(list)
	for listing in data.get("stock", []):
		list.add_item(str(listing.item.name) + "  |  " + rarity(str(listing.item.quality)) + "  |  " + str(listing.price) + " \u91d1\u5e01")
	list.item_selected.connect(func(index: int): selected_item = str(trade.stock[index].item.id))
	var buttons = row()
	button(buttons, "\u8d2d\u4e70\u9009\u4e2d\u7269\u54c1", buy_selected)
	button(buttons, "\u5237\u65b0\u62a5\u4ef7", func(): world.api.call_api("shop", "/v1/worlds/{world}/shops/" + str(trade.merchant_id)))
	button(buttons, "\u8fd4\u56de\u4ea4\u8c08", func():
		close()
		var npc = world.actors.get(str(trade.merchant_id))
		if is_instance_valid(npc) and npc.alive: world.hud.show_npc(npc))
	button(buttons, "\u6536\u8d77", close)
	status_label = label("")

func buy_selected() -> void:
	if selected_item.is_empty() or not world.api.idle(): return
	world.api.call_api("shop_buy", "/v1/worlds/{world}/shops/" + str(trade.merchant_id) + "/buy", {"item_id": selected_item, "quote_id": trade.quote_id}, true)

func show_container(data: Dictionary) -> void:
	chest = data
	selected_item = ""
	rebuild("container", str(data.container.label))
	label("\u7bb1\u4e2d\u91d1\u5e01\uff1a%d\u3002\u5df2\u53d6\u8d70\u7684\u4e1c\u897f\u4e0d\u4f1a\u56e0\u91cd\u65b0\u6253\u5f00\u800c\u51fa\u73b0\u3002" % int(data.container.get("gold", 0)))
	var list = ItemList.new()
	list.custom_minimum_size = Vector2(668, 244)
	column.add_child(list)
	for item in data.get("items", []): list.add_item(str(item.name) + "  |  " + rarity(str(item.quality)))
	list.item_selected.connect(func(index: int): selected_item = str(chest.items[index].id))
	var buttons = row()
	button(buttons, "\u53d6\u51fa\u7269\u54c1", func(): take_selected(false))
	button(buttons, "\u53d6\u51fa\u91d1\u5e01", func(): take_selected(true), int(data.container.get("gold", 0)) <= 0)
	button(buttons, "\u5173\u95ed", close)
	status_label = label("")

func take_selected(gold: bool) -> void:
	if not world.api.idle() or (not gold and selected_item.is_empty()): return
	world.api.call_api("container_take", "/v1/worlds/{world}/containers/" + str(chest.container.id) + "/take", {"item_id": null if gold else selected_item, "take_gold": gold}, true)

func request_journal(reset: bool = true) -> void:
	if reset:
		page_after = 0
		page_history.clear()
	world.api.call_api("journal", "/v1/worlds/{world}/journal?after_seq=" + str(page_after) + "&limit=30")

func show_journal(data: Dictionary) -> void:
	rebuild("journal", "\u65c5\u4eba\u624b\u672d")
	var tabs = TabContainer.new()
	tabs.custom_minimum_size = Vector2(668, 284)
	column.add_child(tabs)
	var log = RichTextLabel.new()
	log.name = "\u4eb2\u5386\u4e0e\u89c1\u95fb"
	log.bbcode_enabled = false
	tabs.add_child(log)
	for entry in data.get("entries", []):
		log.add_text("[" + str(entry.tick) + "] " + str(entry.title) + "\n" + str(entry.text) + "\n")
		log.add_text("\u4e8b\u4ef6 " + str(entry.event_id) + "\n")
		if not entry.caused_by.is_empty(): log.add_text("\u6765\u6e90 " + ", ".join(PackedStringArray(entry.caused_by)) + "\n")
		log.add_text("\n")
	if data.get("entries", []).is_empty(): log.text = "\u8fd9\u4e00\u9875\u8fd8\u6ca1\u6709\u8bb0\u5f55\u3002\u624b\u672d\u53ea\u6536\u5f55\u4f60\u5df2\u83b7\u77e5\u7684\u4e8b\u4ef6\uff0c\u4e0d\u5c55\u793a NPC \u79c1\u4eba\u8bb0\u5fc6\u3002"
	var jobs = RichTextLabel.new()
	jobs.name = "\u5df2\u77e5\u6258\u4ed8"
	tabs.add_child(jobs)
	for quest in data.get("quests", []):
		jobs.add_text(str(quest.title) + "  [" + str(quest.status) + "]\n")
		jobs.add_text(str(quest.get("description", quest.get("item_name", ""))) + "\n")
		jobs.add_text("\u916c\u91d1 " + str(quest.reward) + " | \u76ee\u7684\u5730\uff08\u683c\u5750\u6807\uff09 " + str(quest.get("destination", {})) + "\n")
		jobs.add_text("\u901a\u8fc7\u4ea4\u8c08\u63a5\u4e0b\u6258\u4ed8\uff1b\u9001\u8d27\u9700\u5728\u6536\u4ef6\u4eba\u8eab\u8fb9\u4ece\u884c\u56ca\u8d60\u9001\u6307\u5b9a\u7269\u54c1\u3002\n\n")
	if data.get("quests", []).is_empty(): jobs.text = "\u8fd8\u6ca1\u6709\u5f97\u77e5\u59d4\u6258\u3002\u8bd5\u7740\u95ee\u95ee\u8def\u4eba\u6709\u4ec0\u4e48\u9700\u8981\u5e2e\u5fd9\u7684\u4e8b\u3002"
	var history = RichTextLabel.new()
	history.name = "\u7f16\u5e74\u7ae0\u8282"
	history.bbcode_enabled = false
	tabs.add_child(history)
	for chapter in data.get("chapters", []):
		history.add_text(str(chapter.title) + "\n" + str(chapter.narrative) + "\n")
		history.add_text("\u6765\u6e90 " + ", ".join(PackedStringArray(chapter.source_event_ids)) + "\n")
		history.add_text("\u8bb0\u5f55\u65b9\u5f0f " + str(chapter.get("mode", "rules")) + "\n\n")
	if data.get("chapters", []).is_empty(): history.text = "\u5b8c\u6210\u4ea4\u6613\u3001\u6218\u6597\u6216\u59d4\u6258\u540e\uff0c\u4e0b\u6b21\u4e16\u754c\u63a8\u8fdb\u4f1a\u628a\u771f\u5b9e\u4e8b\u4ef6\u6574\u7406\u6210\u7ae0\u8282\u3002"
	next_after = int(data.get("next_after_seq", page_after))
	var buttons = row()
	button(buttons, "\u4e0a\u4e00\u9875", previous_journal, page_history.is_empty())
	button(buttons, "\u4e0b\u4e00\u9875", next_journal, not data.get("has_more", false))
	button(buttons, "\u6536\u8d77", close)

func next_journal() -> void:
	page_history.append(page_after)
	page_after = next_after
	request_journal(false)

func previous_journal() -> void:
	if page_history.is_empty(): return
	page_after = page_history.pop_back()
	request_journal(false)

func rarity(value: String) -> String:
	return str({"common":"\u666e\u901a", "uncommon":"\u7cbe\u826f", "rare":"\u7a00\u6709"}.get(value, value))

func notice(value: String) -> void:
	if is_instance_valid(status_label): status_label.text = value
	if is_instance_valid(world.hud): world.hud.notice(value, 9)

func close() -> void:
	modal_open = false
	shade.hide()
	frame.hide()
	if is_instance_valid(key_input): key_input.text = ""

func complete(operation: String, data: Dictionary) -> void:
	match operation:
		"model_status":
			known_config = data
			if screen == "title" and modal_open:
				open_title()
				notice("\u4e16\u754c\u670d\u52a1\u5df2\u8fde\u63a5\u3002\u53ef\u4ee5\u521b\u5efa\u65b0\u65c5\u9014\u6216\u8bfb\u53d6\u5b58\u6863\u3002")
		"configure_model":
			known_config.configured = data.get("configured", false)
			if is_instance_valid(base_input): known_config.base_url = base_input.text.strip_edges()
			if is_instance_valid(model_input): known_config.model = model_input.text.strip_edges()
			finish_configuration()
		"create", "load", "resume":
			if data.has("state"):
				close()
		"list_saves": show_saves(data)
		"shop": show_shop(data)
		"shop_buy":
			show_shop(data.shop)
			world.api.call_api("economy", "/v1/worlds/{world}/economy")
		"container": show_container(data)
		"container_take":
			show_container(data)
			world.api.call_api("economy", "/v1/worlds/{world}/economy")
		"journal": show_journal(data)
		"consume":
			if world.hud.panel_open: world.hud.render_inventory()
		"save":
			notice("\u65c5\u9014\u5df2\u4fdd\u5b58\u3002")
			var destination = after_save
			after_save = ""
			if destination == "quit": get_tree().quit()
			elif destination == "title": open_title()

func _input(event: InputEvent) -> void:
	if modal_open and event is InputEventKey and event.pressed and event.physical_keycode == KEY_ESCAPE:
		if screen not in ["title", "saves"] or not world.state.is_empty(): close()
		get_viewport().set_input_as_handled()
