extends "res://tests/r7_integration.gd"
func run() -> void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game);current_scene=game
	game.api.failed.connect(func(op,message): errors.append([op,message]);print("API ERROR ",op," ",message))
	if not await until(func():return game.api.connected): quit(1);return
	await idle()
	game.play_ui.use_model.button_pressed=false
	game.play_ui.start_new()
	await until(func():return not game.state.is_empty());await idle()
	if game.state.is_empty():quit(1);return
	game.evaluation_action("create");await idle()
	check(game.evaluation.get("status")=="ready","evaluation creates frozen physical scenario")
	if game.evaluation.get("status")!="ready":quit(1);return
	game.hud.open_evaluation()
	game.evaluation_action("first")
	check(await until(func():return game.evaluation.get("status") in ["ready_for_second","failed"],60) and game.evaluation.get("status")=="ready_for_second","first run executes while observation panel stays open and learns")
	if game.evaluation.get("status")!="ready_for_second":quit(1);return
	await idle()
	game.evaluation_action("second")
	check(await until(func():return game.evaluation.get("status") in ["complete","failed"],60) and game.evaluation.get("status")=="complete","second run executes from same physical conditions")
	if game.evaluation.get("status")!="complete":quit(1);return
	await idle()
	game.evaluation_action("report");await idle()
	check(game.evaluation_report.get("runs",[]).size()==2,"two actual measured runs are recorded")
	await capture("r7-evaluation")
	print("MEASURED_REPORT ",JSON.stringify(game.evaluation_report))
	game.evaluation_action("rollback");await idle()
	check(game.evaluation.get("active_profile_version")==0,"rollback restores baseline learning state")
	game.hud.open_evaluation()
	game.evaluation_action("rollback_check")
	await idle()
	check(await until(func():return game.evaluation.get("status")=="rolled_back",60),"rollback scenario completes in real Godot")
	await idle()
	game.evaluation_action("return");await idle()
	check(game.evaluation.is_empty(),"original exploration world restored")
	check(errors.is_empty(),"no API failures across evaluation and return")
	var file:=FileAccess.open("res://../release/validation/r7-evaluation.json",FileAccess.WRITE)
	file.store_string(JSON.stringify({"checks":checks,"errors":errors,"report":game.evaluation_report},"  "));file.close()
	quit(0 if checks.all(func(c):return c.passed) else 1)
