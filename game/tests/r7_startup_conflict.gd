extends "res://tests/r7_integration.gd"
## Use a separate --local-db=...; leaves the existing default-port service untouched.
func run() -> void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game);current_scene=game
	game.api.completed.connect(func(op,data):completed[op]=data)
	game.api.failed.connect(func(op,message):errors.append([op,message]))
	var ready:bool=await until(func():return game.api.connected and completed.has("model_status") and not game.local_starting,30)
	check(ready,"connects to this version despite old service on default port")
	if not ready:quit(1);return
	check(game.api.base_url!="http://127.0.0.1:8765","old port is bypassed without killing its service")
	check(game.local_backend_pid>0,"editor entry launches bundled local backend")
	game.play_ui.use_model.button_pressed=false
	game.play_ui.name_input.text="启动修复验收"
	game.play_ui.start_new()
	check(await until(func():return not game.state.is_empty(),20),"new-game button actually creates a world")
	await idle()
	check(not game.play_ui.modal_open and game.actors.size()>=34,"new game enters playable world")
	check(game.state.has("contracts") and game.state.has("safe_zones"),"created world contains R7 systems")
	check(errors.is_empty(),"no API failures during automatic recovery and new game")
	var file:=FileAccess.open("res://../release/validation/r7-startup-conflict.json",FileAccess.WRITE)
	file.store_string(JSON.stringify({"checks":checks,"errors":errors,"server":game.api.base_url},"  "));file.close()
	quit(0 if checks.all(func(c):return c.passed) else 1)
