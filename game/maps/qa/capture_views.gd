extends SceneTree
var game:Node2D
func _initialize()->void: call_deferred("run")
func shot(title:String)->void:
	for i in range(20): await process_frame
	game.hud.zone_timer=0
	await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../release/previews/"+title+".png")
	print("CAPTURE ",title)
func run()->void:
	game=load("res://maps/offline_preview.tscn").instantiate()
	root.add_child(game)
	await process_frame
	DirAccess.make_dir_recursive_absolute("res://../release/previews")
	var views:=[
		["v2_01_home",Vector2(56,165.5)],
		["v2_02_market",Vector2(65,167)],
		["v2_03_smith",Vector2(81,168)],
		["v2_04_crowford",Vector2(246,165)],
		["v2_05_north_bridge",Vector2(150,143.5)],
		["v2_06_forest",Vector2(89,95)],
		["v2_07_ruins",Vector2(237,50)],
		["v2_08_ferry",Vector2(162,178)],
		["v2_09_windmill",Vector2(41,194)],
		["v2_10_graveyard",Vector2(267,104)]]
	for view in views:
		game.player.position=view[1]*32
		game.player.camera.reset_smoothing()
		await shot(view[0])
	game.hud.map_open=true
	await shot("v2_11_world_map")
	game.hud.map_open=false
	game.player.position=Vector2(81,169.5)*32
	game.hud.show_npc(game.npcs[0])
	game.hud.submit_text("附近有什么传闻？")
	await shot("v2_12_dialogue")
	game.hud.close_dialogue()
	game.player.switch_appearance()
	game.player.position=Vector2(244,169)*32
	await shot("v2_13_female")
	quit()
