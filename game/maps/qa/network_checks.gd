extends SceneTree
var game
var passed:=0
var failures:Array[String]=[]
var completions:Dictionary={}
var errors:Array=[]
func _initialize()->void: call_deferred("run")
func check(ok:bool,label:String)->void:
	if ok: passed+=1; print("PASS ",label)
	else: failures.append(label); push_error("FAIL "+label)
func until(predicate:Callable,seconds:float=12)->bool:
	var deadline:=Time.get_ticks_msec()+int(seconds*1000)
	while not predicate.call() and Time.get_ticks_msec()<deadline: await create_timer(0.05).timeout
	return predicate.call()
func idle()->void: await until(func(): return game.api.idle(),30)
func run()->void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game)
	current_scene=game
	game.api.completed.connect(func(op,data): completions[op]=data)
	game.api.failed.connect(func(op,message): errors.append([op,message]); print("API ERROR ",op," ",message))
	game.advance_timer=-9999
	if not await until(func(): return not game.state.is_empty(),25):
		check(false,"server connects")
		finish()
		return
	await idle()
	check(game.actors.size()==16,"C creates player and 15 reference NPCs")
	check(game.player.inventory_items.size()==6,"six owned C weapons")
	check(game.player.visual.sprite_frames.get_frame_texture("idle0",0).get_size()==Vector2(48,64),"player reference frame remains 48x64")
	var before:Vector2=game.player.position
	Input.action_press("move_down")
	await create_timer(0.35).timeout
	Input.action_release("move_down")
	check(game.player.position.distance_to(before)>20,"A controller actually walks")
	game.player.try_dodge(Vector2.DOWN)
	check(game.player.is_dodging(),"A dodge starts")
	await create_timer(0.4).timeout
	game.checkpoint(true)
	await idle()
	var victim=game.actors.values().filter(func(a): return a!=game.player)[0]
	# Explicit positioning is QA setup in an isolated DB, never production behavior.
	game.player.position=Vector2(120.5,143.5)*32
	victim.position=game.player.position+Vector2(48,0)
	game.checkpoint(true)
	await idle()
	game.hud.show_npc(victim)
	game.hud.submit_text("你好，最近怎么样？")
	await until(func(): return completions.has("dialogue"))
	check(completions.get("dialogue",{}).get("mode")=="fallback","unavailable provider visibly reports fallback")
	check(not game.hud.pending and game.hud.transcript.get_parsed_text().contains("fallback"),"Chinese chat returns through HTTP into dialogue UI")
	completions.erase("dialogue")
	game.hud.submit_text("QA_MOVE")
	await until(func(): return completions.has("dialogue"))
	game.hud.close_dialogue()
	check(await until(func(): return game.state.tasks.any(func(t): return t.status=="succeeded"),8),"B fixture intent -> C task -> A walking -> C task success")
	game.player.position=Vector2(120.5,143.5)*32
	victim.position=game.player.position+Vector2(96,0)
	game.checkpoint(true)
	await idle()
	var bow:Dictionary=game.player.inventory_items.filter(func(i): return i.base_type=="bow")[0]
	game.api.command("EQUIP",{"actor_id":game.player.entity_id,"item_id":bow.id})
	await idle()
	check(game.player.active_weapon().get("id")==bow.id,"C equip drives A ranged slot")
	var hp_before:int=victim.hp
	game.player.facing=Vector2.RIGHT
	game.player.try_attack()
	check(await until(func(): return victim.hp<hp_before,4),"A visible projectile collision -> C authoritative damage")
	var sword:Dictionary=game.player.inventory_items.filter(func(i): return i.base_type=="hammer")[0]
	game.api.command("EQUIP",{"actor_id":game.player.entity_id,"item_id":sword.id})
	await idle()
	victim.position=game.player.position+Vector2(40,0)
	game.checkpoint(true)
	await idle()
	for i in range(25):
		if not victim.alive: break
		var chase_deadline:=Time.get_ticks_msec()+1200
		while game.player.position.distance_to(victim.position)>34 and Time.get_ticks_msec()<chase_deadline:
			var motion:Vector2=(victim.position-game.player.position).normalized()
			Input.action_press("move_right",maxf(0,motion.x))
			Input.action_press("move_left",maxf(0,-motion.x))
			Input.action_press("move_down",maxf(0,motion.y))
			Input.action_press("move_up",maxf(0,-motion.y))
			await physics_frame
		for key in ["move_right","move_left","move_down","move_up"]: Input.action_release(key)
		game.player.facing=(victim.position-game.player.position).normalized()
		game.player.try_attack()
		await create_timer(1.05).timeout
	await idle()
	print("COMBAT_FINAL hp=",victim.hp," distance=",game.player.position.distance_to(victim.position)," weapon=",game.player.active_weapon().get("base_type"))
	check(not victim.alive and game.loot.size()>0,"A melee -> permanent NPC death and C ground loot")
	var old_count:int=game.player.inventory_items.size()
	game.player.position=victim.position
	game.checkpoint(true)
	await idle()
	game.interact()
	await idle()
	check(game.player.inventory_items.size()>old_count,"E pickup changes C ownership and A inventory")
	game.save_game()
	await idle()
	check(not game.save_id.is_empty(),"C durable save")
	var old_world:String=game.session_world
	var dead_id:String=victim.entity_id
	game.player._shoot_projectile(bow,"qa_inflight_before_load")
	await physics_frame
	game.load_game()
	await idle()
	check(game.session_world!=old_world and not game.actors[dead_id].alive,"load branches world and preserves death")
	check(get_nodes_in_group("world_projectiles").is_empty(),"world switch removes in-flight projectiles")
	game.hud.toggle_inventory()
	await idle()
	check(game.hud.panel_open and game.hud.inventory.item_count==game.player.inventory_items.size(),"inventory UI shows confirmed items")
	game.hud.close_panel()
	game.evaluation_action("create")
	await idle()
	check(game.evaluation.get("status")=="ready","transport scenario created on real map")
	game.evaluation_action("first")
	await until(func(): return game.evaluation.get("status") in ["ready_for_second","failed"],55)
	check(game.evaluation.get("status")=="ready_for_second","first transport actually executes and learns")
	game.evaluation_action("second")
	await until(func(): return game.evaluation.get("status") in ["complete","failed"],55)
	check(game.evaluation.get("status")=="complete","second transport executes with same frozen conditions")
	await idle()
	game.evaluation_action("report")
	await idle()
	check(game.evaluation_report.get("runs",[]).size()==2,"C measured two runs; UI does not manufacture scores")
	print("EVALUATION_REPORT ",JSON.stringify(game.evaluation_report))
	game.evaluation_action("rollback")
	await idle()
	check(game.evaluation.get("active_profile_version")==0,"rollback restores original learning profile")
	game.evaluation_action("rollback_check")
	await until(func(): return game.evaluation.get("status")=="rollback_running",5)
	check(await until(func(): return game.evaluation.get("status")=="rolled_back",55),"restored baseline executes again in the actual map")
	await idle()
	game.evaluation_action("return")
	await idle()
	check(game.evaluation.is_empty(),"return to original exploration world")
	check(errors.is_empty(),"no rejected HTTP operations")
	finish()
func finish()->void:
	var report:={"passed":passed,"failed":failures,"errors":errors,"evaluation":game.evaluation_report}
	FileAccess.open("res://../release/validation/network-results.json",FileAccess.WRITE).store_string(JSON.stringify(report,"  "))
	print("NETWORK_QA ",passed," passed; ",failures.size()," failed")
	quit(0 if failures.is_empty() else 1)
