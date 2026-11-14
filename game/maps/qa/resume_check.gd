extends SceneTree
func _initialize()->void: call_deferred("run")
func run()->void:
	var game=load("res://main.tscn").instantiate()
	root.add_child(game); current_scene=game
	game.advance_timer=-9999
	var deadline:=Time.get_ticks_msec()+30000
	while (game.state.is_empty() or not game.api.idle()) and Time.get_ticks_msec()<deadline: await create_timer(0.05).timeout
	await process_frame
	var okay:bool=game.api.connected and game.actors.size()==16 and game.evaluation.is_empty() and game.ordinary_world==game.session_world
	print("NORMAL_SESSION connected=",game.api.connected," actors=",game.actors.size()," ordinary=",okay)
	FileAccess.open("res://../release/validation/resume-result.json",FileAccess.WRITE).store_string(JSON.stringify({"connected":game.api.connected,"actors":game.actors.size(),"ordinary_restored":okay}))
	quit(0 if okay else 1)
