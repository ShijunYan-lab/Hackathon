extends SceneTree
func _initialize()->void: call_deferred("run")
func run()->void:
	var game=load("res://main.tscn").instantiate()
	root.add_child(game)
	current_scene=game
	var deadline:=Time.get_ticks_msec()+30000
	while game.state.is_empty() and Time.get_ticks_msec()<deadline: await create_timer(0.1).timeout
	print("COLD_START connected=",game.api.connected," actors=",game.actors.size()," auto_start=",game.boot_started)
	quit(0 if game.actors.size()==16 else 1)
