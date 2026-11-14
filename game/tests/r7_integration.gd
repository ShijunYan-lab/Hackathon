extends SceneTree
## Real Godot controls + real local HTTP, on an isolated QA database.
var game
var errors: Array = []
var completed: Dictionary = {}
var checks: Array = []
func _initialize() -> void: call_deferred("run")
func check(value: bool, label: String) -> void:
	checks.append({"check":label,"passed":value})
	print("PASS " if value else "FAIL ",label)
func until(predicate: Callable, seconds: float = 15.0) -> bool:
	var end := Time.get_ticks_msec()+int(seconds*1000)
	while not predicate.call() and Time.get_ticks_msec()<end: await create_timer(0.05).timeout
	return predicate.call()
func idle() -> void: await until(func(): return game.api.idle(),30)
func capture(name: String) -> void:
	if DisplayServer.get_name()=="headless": return
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../release/validation/"+name+".png")
func run() -> void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game);current_scene=game
	game.api.completed.connect(func(op,data):completed[op]=data)
	game.api.failed.connect(func(op,message):errors.append([op,message]);print("API ERROR ",op," ",message))
	game.advance_timer=-9999
	game.autosave_timer=-9999
	if not await until(func():return game.api.connected): quit(1);return
	await idle()
	await capture("r7-title")
	game.play_ui.use_model.button_pressed=false
	game.play_ui.name_input.text="联调旅人"
	game.play_ui.start_new()
	check(await until(func():return not game.state.is_empty()),"new game through title UI")
	if game.state.is_empty():quit(1);return
	await idle()
	game.advance_timer=-9999
	check(game.state.sites.size()>=40,"resource nodes synchronized")
	check(game.state.safe_zones.size()==2,"two real settlement safety zones")
	var guards: Array=game.actors.values().filter(func(a):return a!=game.player and a.sprite_skin.begins_with("guard_"))
	check(guards.size()==4,"four new guards use extracted artwork")
	check(guards[0].visual.sprite_frames.get_frame_count("attack")==5,"guard attack animation has five source frames")
	var npc=game.actors.values().filter(func(a):return a!=game.player and a.actor_kind=="npc")[0]
	# QA positions use a known clear road; gameplay itself uses normal movement.
	game.player.position=Vector2(120.5,143.5)*32
	npc.position=game.player.position+Vector2(-55,0)
	game.checkpoint(true);await idle()
	game.hud.show_npc(npc)
	game.hud.submit_text("请免费跟随我，一起同行")
	check(await until(func():return completed.has("dialogue")),"free-text hire returns via HTTP")
	check(game.state.contracts.any(func(v):return v.status=="active"),"hire creates active world contract")
	game.hud.close_dialogue()
	var start: Vector2=npc.position
	Input.action_press("move_right")
	await create_timer(1.25).timeout
	Input.action_release("move_right")
	await create_timer(2.0).timeout
	check(npc.position.distance_to(start)>50,"hired NPC visibly follows moving player")
	check(npc.current_task_id!="" and npc.active_task.get("kind")=="FOLLOW","following remains active after arrival")
	await capture("r7-follow")
	game.player.position+=Vector2(300,0)
	game.player.facing=Vector2.RIGHT
	var attack_before: int=game.player.animation_lock_until_ms
	var started: int=Time.get_ticks_msec()
	game.player.try_attack()
	check(game.player.animation_lock_until_ms>attack_before and Time.get_ticks_msec()-started<50,"local attack starts within 50 ms without waiting for model")
	game.hud.render_inventory();await process_frame
	check(game.hud.panel_open,"inventory opens")
	game.hud.show_economy();await process_frame
	var back:=InputEventKey.new();back.physical_keycode=KEY_ESCAPE;back.keycode=KEY_ESCAPE;back.pressed=true
	game.hud._input(back)
	check(game.hud.panel_kind=="inventory","Escape returns crafting to inventory")
	game.hud.close_panel()
	await idle()
	var site:Dictionary=game.state.sites.filter(func(v):return v.kind=="herb").filter(func(v): return game.state.actors.all(func(a):return a.kind!="monster" or Vector2(a.tile.x,a.tile.y).distance_to(Vector2(v.tile.x,v.tile.y))>12))[0]
	game.player.position=Vector2(site.tile.x,site.tile.y)*32
	game.checkpoint(true);await idle()
	game.api.call_api("interact","/v1/worlds/{world}/interact",{"action":"GATHER","target_id":site.id},true)
	await idle()
	check(game.player.inventory_items.any(func(i):return i.material_id=="herb"),"visible resource interaction grants authoritative material")
	await capture("r7-resources")
	game.play_ui.request_journal();await idle()
	check(game.play_ui.screen=="journal","single travel journal opens")
	await capture("r7-journal")
	game.play_ui.close()
	var shop_id:String=str(game.state.containers.filter(func(v):return v.kind=="merchant" and v.merchant_id!=npc.entity_id)[0].merchant_id)
	var shop_actor=game.actors[shop_id]
	game.player.position=shop_actor.position+Vector2(45,0)
	game.checkpoint(true);await idle()
	game.api.call_api("shop","/v1/worlds/{world}/shops/"+shop_id)
	await idle()
	check(game.play_ui.trade.has("sellable"),"two-way trade receives sellable list")
	check(game.play_ui.trade.get("stock",[]).size()>0,"resident merchant exposes physically available stock")
	await capture("r7-trade")
	game.play_ui.close()
	for step in range(3):
		game.api.call_api("advance","/v1/worlds/{world}/heartbeat",{"reason":"idle_timer","trigger_event_ids":[]},true)
		await idle()
	var material_obtained: Callable = func():return game.state.items.any(func(i):return i.base_type=="material" and i.owner_id!=null and i.owner_id!=game.player.entity_id and game.actors.has(str(i.owner_id)))
	check(await until(material_obtained,20),"NPC autonomously obtains materials through world policy and arrival settlement")
	check(errors.is_empty(),"no API failures in real client run")
	var file:=FileAccess.open("res://../release/validation/r7-client.json",FileAccess.WRITE)
	file.store_string(JSON.stringify({"checks":checks,"errors":errors},"  "));file.close()
	quit(0 if checks.all(func(c):return c.passed) else 1)
