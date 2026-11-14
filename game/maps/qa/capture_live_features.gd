extends SceneTree
var game
var failed:=false
func _initialize()->void: call_deferred("run")
func idle()->void:
	var deadline:=Time.get_ticks_msec()+80000
	while not game.api.idle() and Time.get_ticks_msec()<deadline: await create_timer(0.05).timeout
func shot(label:String)->void:
	game.hud.notice_timer=0; game.hud.zone_timer=0
	for i in range(8): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../release/previews/"+label+".png")
	print("CAPTURE ",label)
func run()->void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game); current_scene=game
	game.advance_timer=-9999
	game.api.failed.connect(func(op,message): failed=true; print("CAPTURE_API_ERROR ",op," ",message))
	var deadline:=Time.get_ticks_msec()+30000
	while game.state.is_empty() and Time.get_ticks_msec()<deadline: await create_timer(0.1).timeout
	if game.state.is_empty(): quit(1); return
	await idle()
	await shot("v4_01_home")
	game.hud.toggle_inventory(); await idle()
	for index in range(game.hud.inventory.item_count):
		game.hud.inventory.select(index)
		game.hud.inventory.item_selected.emit(index)
		await shot("v4_weapon_"+game.hud.weapon_portrait.kind)
	game.hud.close_panel()
	var npc=game.actors.values().filter(func(a): return a!=game.player)[0]
	game.player.position=npc.position+Vector2(0,40)
	game.player.camera.reset_smoothing()
	game.checkpoint(true); await idle()
	await process_frame
	if "--bubble-layout" in OS.get_cmdline_user_args():
		npc.say("住手！我没有招惹你。再靠近，我就还手了！")
		await shot("v4_04_bubble_layout")
		print("BUBBLE_LAYOUT lines=",npc.speech.get_line_count()," visible=",npc.speech.get_visible_line_count()," rect=",npc.speech.size)
		quit()
		return
	game.interact(); await idle()
	game.hud.submit_text("你好，我是刚到镇上的旅人。你叫什么，这里能修理武器吗？")
	await idle()
	await shot("v4_02_live_dialogue")
	print("CAPTURE_REAL_DIALOGUE_MODE ",game.model_mode)
	game.hud.close_dialogue()
	for kind in ["sword","axe","hammer","bow","crossbow","staff"]:
		var item:Dictionary=game.player.inventory_items.filter(func(i): return i.base_type==kind)[0]
		game.api.command("EQUIP",{"actor_id":game.player.entity_id,"item_id":item.id}); await idle()
		game.player.facing=Vector2.RIGHT
		game.player.direction=2
		game.player._play_anim("idle2")
		await shot("v4_pose_"+kind)
	var sword:Dictionary=game.player.inventory_items.filter(func(i): return i.base_type=="sword")[0]
	game.api.command("EQUIP",{"actor_id":game.player.entity_id,"item_id":sword.id}); await idle()
	game.player.facing=(npc.position-game.player.position).normalized()
	game.player.try_attack()
	await create_timer(0.8).timeout
	await shot("v4_03_self_defense")
	print("CAPTURE_DONE failed=",failed)
	quit(1 if failed else 0)
