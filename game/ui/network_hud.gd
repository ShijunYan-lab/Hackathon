extends "res://ui/realm_hud.gd"
var pending:=false
var panel_open:=false
var panel_kind:=""
var book:Control
var book_title:Label
var body:RichTextLabel
var actions:Control
var inventory:ItemList
var item_ids:Array[String]=[]
var chosen:=""
var price:SpinBox
var weapon_portrait:Control
var message:="连接本地世界……"
var notice_timer:=8.0

func _ready()->void:
	super._ready()
	book=Control.new()
	book.position=Vector2(72,82)
	book.size=Vector2(656,327)
	book.mouse_filter=Control.MOUSE_FILTER_STOP
	book.visible=false
	add_child(book)
	book.draw.connect(func():
		book.draw_rect(Rect2(Vector2.ZERO,book.size),INK)
		book.draw_rect(Rect2(Vector2.ZERO,book.size),GOLD,false,2))
	book_title=Label.new()
	book_title.position=Vector2(18,11)
	book_title.add_theme_font_override("font",font)
	book_title.add_theme_color_override("font_color",GOLD)
	book_title.add_theme_font_size_override("font_size",17)
	book.add_child(book_title)
	body=RichTextLabel.new()
	body.position=Vector2(18,45)
	body.size=Vector2(618,192)
	body.add_theme_font_override("normal_font",font)
	body.add_theme_font_size_override("normal_font_size",12)
	body.add_theme_color_override("default_color",PAPER)
	body.bbcode_enabled=false
	book.add_child(body)
	actions=Control.new()
	book.add_child(actions)
	inventory=ItemList.new()
	inventory.position=Vector2(18,45)
	inventory.size=Vector2(242,190)
	style_control(inventory)
	inventory.item_selected.connect(select_item)
	book.add_child(inventory)
	price=SpinBox.new()
	price.position=Vector2(466,252)
	price.size=Vector2(78,25)
	price.min_value=0
	price.max_value=999
	price.value=5
	style_control(price)
	book.add_child(price)
	weapon_portrait=preload("res://ui/weapon_portrait.gd").new()
	weapon_portrait.position=Vector2(270,45)
	weapon_portrait.size=Vector2(154,190)
	weapon_portrait.mouse_filter=Control.MOUSE_FILTER_IGNORE
	book.add_child(weapon_portrait)

func _process(delta:float)->void:
	super._process(delta)
	notice_timer=maxf(0,notice_timer-delta)
	book.visible=panel_open
	if panel_open: world.player.set_controls_locked(true)

func notice(value:String,seconds:float=5)->void:
	message=value
	notice_timer=seconds

func draw_hud()->void:
	super.draw_hud()
	if map_open: return
	panel(Rect2(216,13,400,44))
	var weapon:String=str(world.player.active_weapon().get("name","未装备"))
	text(Vector2(228,30),"生命 %d / %d    %s"%[world.player.hp,world.player.max_hp,weapon],11)
	text(Vector2(228,47),("世界已连接" if world.api.connected else "等待世界连接")+" · NPC "+world.model_mode+"    F6 保存 / F7 读取",10,MUTED)
	if not dialog_open:
		panel(Rect2(32,412,736,25))
		text(Vector2(43,429),"WASD 移动  Shift 跑  空格 闪避  鼠标 攻击  1/2 武器  E 交互  Tab 行囊  J 手札  M 地图  F4 运输",10)
	if notice_timer>0:
		panel(Rect2(55,76,690,27))
		text(Vector2(67,94),message.left(63),11,GOLD)

func draw_dialogue_frame(_size:Vector2)->void:
	panel(Rect2(52,242,696,194),Color("27231e"))
	canvas.draw_line(Vector2(174,254),Vector2(174,424),Color("786342"),1)
	text(Vector2(186,269),title,17,GOLD)
	text(Vector2(374,268),role,11,MUTED)
	text(Vector2(668,268),"Esc 关闭",10,MUTED)
	panel(Rect2(68,270,92,127),Color("1d1c1b"))
	if is_instance_valid(current_npc):
		canvas.draw_texture_rect_region(current_npc.portrait,Rect2(73,277,82,110),Rect2(0,0,48,64))
	text(Vector2(80,416),"思索中……" if pending else ("NPC · "+world.model_mode if current_npc else "地点手札"),10,MUTED)

func show_npc(npc:Node2D)->void:
	close_panel()
	super.show_npc(npc)
	transcript.text="你走近了"+str(npc.data.name)+"。"
	pending=false

func submit_text(value:String)->void:
	if pending or not is_instance_valid(current_npc) or not current_npc.alive: return
	if DisplayServer.has_feature(DisplayServer.FEATURE_IME) and DisplayServer.ime_get_text()!="": return
	value=value.strip_edges().left(120)
	if value.is_empty(): return
	transcript.add_text("\n\n你："+value)
	entry.text=""
	pending=true
	send_button.disabled=true
	entry.editable=false
	for button in topic_buttons: button.disabled=true
	chat_submitted.emit(str(current_npc.entity_id),value)

func receive_reply(value:String,mode:String)->void:
	pending=false
	if not dialog_open: return
	transcript.add_text("\n"+title+"："+value+"\n（"+mode+"）")
	entry.editable=true
	send_button.disabled=false
	for button in topic_buttons: button.disabled=false
	entry.grab_focus()

func receive_history(data:Dictionary)->void:
	if not is_instance_valid(current_npc) or str(data.get("npc_id",""))!=current_npc.entity_id or pending: return
	transcript.clear()
	for turn in data.get("turns",[]):
		transcript.add_text("你："+str(turn.player)+"\n"+title+"："+str(turn.npc)+"\n\n")
	if data.get("turns",[]).is_empty(): transcript.add_text("你走近了"+title+"。")

func close_panel()->void:
	panel_open=false
	if is_instance_valid(book): book.hide()

func open_book(kind:String,caption:String)->void:
	close_dialogue()
	map_open=false
	panel_open=true
	panel_kind=kind
	book_title.text=caption+"                        Esc  收起"
	book.show()
	inventory.visible=kind=="inventory"
	price.visible=kind=="inventory"
	weapon_portrait.visible=kind=="inventory"
	body.position=Vector2(440,45) if kind=="inventory" else Vector2(18,45)
	body.size=Vector2(198,192) if kind=="inventory" else Vector2(618,192)
	for child in actions.get_children():
		actions.remove_child(child)
		child.queue_free()

func button(label:String,x:float,y:float,width:float,callback:Callable,disabled:bool=false)->void:
	var control:=Button.new()
	control.text=label
	control.position=Vector2(x,y)
	control.size=Vector2(width,26)
	control.disabled=disabled
	style_control(control)
	control.pressed.connect(callback)
	actions.add_child(control)

func toggle_inventory()->void:
	if panel_open and panel_kind=="inventory": close_panel(); return
	if world.state.is_empty(): return
	render_inventory()
	world.api.call_api("economy","/v1/worlds/{world}/economy")

func render_inventory()->void:
	open_book("inventory","旅人的行囊")
	inventory.clear()
	item_ids.clear()
	for item in world.player.inventory_items:
		item_ids.append(str(item.id))
		inventory.add_item(str(item.name)+("  · 已装备" if world.player.active_weapon().get("id")==item.id else "")+"   伤害 "+str(int(item.stats.damage)))
	if not item_ids.is_empty():
		var index:=maxi(0,item_ids.find(chosen))
		chosen=item_ids[index]
		inventory.select(index)
	body.text="钱币：%d\n\n附近人物：%s\n\n物品、装备与交易均记录在此世界。\n出售需对方接受提议。\n\nF6 保存旅途    F7 读取存档"%[int(world.economy.get("wallets",{}).get(world.player.entity_id,0)),str(world.near_npc.display_name) if world.near_npc else "请走近人物"]
	button("装备",18,252,80,func(): item_action("EQUIP"))
	button("赠送",105,252,80,func(): item_action("GIVE"),world.near_npc==null)
	button("提出出售",192,252,105,func(): item_action("offer"),world.near_npc==null)
	button("接受报价",304,252,105,accept_offer)
	button("组织 / 制作",18,289,130,show_economy)
	button("保存旅途",162,289,115,world.save_game)
	button("读取存档",290,289,115,world.load_game)
	if not item_ids.is_empty(): select_item(maxi(0,item_ids.find(chosen)))

func select_item(index:int)->void:
	if index<0 or index>=item_ids.size(): return
	chosen=item_ids[index]
	var item:Dictionary=world.player.find_item(chosen)
	weapon_portrait.show_weapon(str(item.get("base_type","")))
	var descriptions:={"sword":"单手直剑，锋刃轻巧。", "axe":"宽刃战斧，适合横扫。", "hammer":"铁制战锤，重击破甲。", "bow":"木制猎弓，远处制敌。", "crossbow":"机械轻弩，射程更远。", "staff":"镶嵌紫晶的施法杖。"}
	body.text=str(item.get("name","物品"))+"\n\n"+str(descriptions.get(item.get("base_type",""),"旅途中取得的物品。"))+"\n\n伤害  %d\n间隔  %.2f 秒\n护甲  %d\n\n钱币  %d"%[int(item.stats.damage),float(item.stats.cooldown_s),int(item.stats.armor),int(world.economy.get("wallets",{}).get(world.player.entity_id,0))]

func item_action(kind:String)->void:
	if chosen.is_empty() or not world.api.idle(): return
	var payload:={"actor_id":world.player.entity_id,"item_id":chosen}
	if kind in ["GIVE","offer"]:
		if not is_instance_valid(world.near_npc): return
		world.checkpoint(true)
		payload.target_id=world.near_npc.entity_id
	if kind=="offer":
		payload.kind="trade"
		payload.price=int(price.value)
		world.api.call_api("offer","/v1/worlds/{world}/offers",payload,true)
	else: world.api.command(kind,payload)

func accept_offer()->void:
	for offer in world.economy.get("offers",[]):
		if offer.target_id==world.player.entity_id and offer.status=="pending":
			world.checkpoint(true)
			world.api.command("ACCEPT_OFFER",{"actor_id":world.player.entity_id,"offer_id":offer.id})
			return
	notice("没有发给你的待接受报价。")

func show_economy()->void:
	open_book("economy","工坊与商会")
	body.text=""
	for org in world.state.get("organizations",[]):
		body.add_text(str(org.name)+"  · "+str(org.member_ids.size())+" 人  · "+str(org.status)+"\n")
	body.add_text("\n制作需要本人实际持有的材料。\n")
	var recipes:Dictionary=world.economy.get("recipes",{})
	var index:=0
	for key in recipes:
		body.add_text(str(key)+"  "+JSON.stringify(recipes[key])+"\n")
		button("制作 "+str(key),18+index*198,252,190,func(): world.api.call_api("craft","/v1/worlds/{world}/craft",{"actor_id":world.player.entity_id,"recipe_id":key},true))
		index+=1
	button("返回行囊",18,289,120,render_inventory)

func show_story(data:Dictionary)->void:
	open_book("story","旅人手札 · 世界记述")
	body.text=""
	for chapter in data.get("chapters",[]):
		body.add_text(str(chapter.get("title","见闻"))+"\n"+str(chapter.get("narrative",""))+"\n"+str(chapter.get("open_question",""))+"\n\n")
	if body.text.is_empty(): body.text="手札尚未形成新的篇章。探索、对话和世界事件会留下记述。"

func show_world_status()->void:
	open_book("status","旅途状态")
	body.text="世界连接："+("已连接" if world.api.connected else "已断开")+"\n最近 NPC 对话："+world.model_mode+"\n世界版本："+str(world.api.version)+"\n"
	for task in world.state.get("tasks",[]):
		var actor=world.actors.get(str(task.actor_id))
		if actor and (actor==world.player or actor.position.distance_to(world.player.position)<192):
			body.add_text("\n"+str(actor.display_name)+"："+str(task.kind)+" · "+str(task.status))
	button("重新连接",18,289,120,world.api.retry)

func open_evaluation()->void:
	if world.state.is_empty(): return
	render_evaluation({})

func render_evaluation(run:Dictionary)->void:
	open_book("evaluation","旧王道 · 运输观察")
	var session:Dictionary=world.evaluation
	var status:=str(session.get("status","尚未开始"))
	body.text="状态："+status+"   · "+str(session.get("mode","fallback"))+"\n\n商人沿大地图商路实际行走；护卫和威胁使用同一战斗控制器。\n货物、耗时、生死与收益由世界事件计算。两次运行条件一致。\n\n观察期间锁定玩家操作；完成后可返回原来的旅途。"
	if not run.is_empty(): body.add_text("\n\n本轮："+str(run.get("kind",""))+"  策略："+str(run.get("strategy",""))+"\n"+JSON.stringify(run.get("metrics",{})))
	var options:=[["创建观察","create",session.is_empty()],["第一次","first",status=="ready"],["第二次","second",status=="ready_for_second"],["恢复基线","rollback",status in ["complete","ready_for_second"]],["回退验证","rollback_check",status=="rolled_back"]]
	for i in range(options.size()):
		var action:String=options[i][1]
		button(options[i][0],18+i*124,252,116,func(): world.evaluation_action(action),not options[i][2])
	button("真实结果",18,289,115,func(): world.evaluation_action("report"),session.is_empty())
	button("学习记录",145,289,115,func(): world.evaluation_action("profile"),session.is_empty())
	button("返回旅途",399,289,115,func(): world.evaluation_action("return"),session.is_empty() or status.ends_with("running") or status=="learning")

func show_evaluation_report(data:Dictionary)->void:
	open_book("report","运输结果 · 实测记录")
	body.text="比较结果："+str(data.get("improvement","not_measured"))+"\n"
	for run in data.get("runs",[]):
		body.add_text("\n"+str(run.kind)+" / "+str(run.mode)+" / "+str(run.strategy)+"\n")
		if run.get("metrics") is Dictionary:
			var m:Dictionary=run.metrics
			body.add_text("送达 %d / %d　耗时 %.1fs　花费 %d　存活 %s　收益 %.3f\n"%[m.cargo_delivered,m.cargo_initial,float(m.duration_ms)/1000,m.gold_spent,str(m.merchant_survived),m.reward])
	for note in data.get("notes",[]): body.add_text("\n"+str(note))
	button("返回观察",18,289,120,open_evaluation)

func show_profile(data:Dictionary)->void:
	open_book("profile","学习记录 · 当前策略")
	var profile:Dictionary=data.get("active_profile",{})
	body.text="模式："+str(data.get("learning_mode","fallback"))+"\n版本："+str(profile.get("version",0))+"\n策略数值："+JSON.stringify(profile.get("values",{}))+"\n"
	for memory in profile.get("memories",[]): body.add_text("\n"+str(memory.statement)+"\n来源："+str(memory.source_run_id))
	button("返回观察",18,289,120,open_evaluation)

func _input(event:InputEvent)->void:
	if panel_open and event.is_action_pressed("ui_cancel"):
		close_panel()
		get_viewport().set_input_as_handled()
	else: super._input(event)
