extends SceneTree
var game
func _initialize()->void: call_deferred("run")
func shot(label:String)->void:
	game.hud.notice_timer=0
	game.hud.zone_timer=0
	for i in range(8): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../release/previews/"+label+".png")
	print("CAPTURE ",label)
func run()->void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game)
	current_scene=game
	var deadline:=Time.get_ticks_msec()+30000
	while game.state.is_empty() and Time.get_ticks_msec()<deadline: await create_timer(0.1).timeout
	if game.state.is_empty(): quit(1); return
	game.advance_timer=-9999
	await create_timer(0.5).timeout
	await shot("v3_01_network_home")
	game.hud.toggle_inventory()
	await create_timer(0.3).timeout
	await shot("v3_02_inventory")
	game.hud.close_panel()
	var npc=game.actors.values().filter(func(a): return a!=game.player)[0]
	game.player.position=npc.position+Vector2(0,36)
	game.player.camera.reset_smoothing()
	game.hud.show_npc(npc)
	game.hud.submit_text("你好，你是做什么工作的？")
	await create_timer(1).timeout
	await shot("v3_03_dialogue")
	game.hud.close_dialogue()
	game.hud.map_open=true
	await shot("v3_04_world_map")
	print("CAPTURE_DONE actors=",game.actors.size()," mode=",game.model_mode)
	quit()
