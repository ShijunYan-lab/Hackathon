extends SceneTree
var game
var reply:Dictionary={}
var failures:Array=[]
func _initialize()->void: call_deferred("run")
func until(predicate:Callable,seconds:float=75)->bool:
	var deadline:=Time.get_ticks_msec()+int(seconds*1000)
	while not predicate.call() and Time.get_ticks_msec()<deadline: await create_timer(0.05).timeout
	return predicate.call()
func run()->void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game); current_scene=game
	game.advance_timer=-9999
	game.api.failed.connect(func(op,message): failures.append([op,message]); print("ACTION_API_ERROR ",op," ",message))
	game.api.completed.connect(func(op,data):
		if op=="dialogue": reply=data)
	if not await until(func(): return not game.state.is_empty(),25): quit(1); return
	await until(func(): return game.api.idle())
	var npc=game.actors.values().filter(func(a): return a!=game.player and a.sprite_skin=="elena")[0]
	for offset in [Vector2(0,64),Vector2(64,0),Vector2(-64,0),Vector2(0,-64)]:
		var point:Vector2=npc.position+offset
		if not game.navigation.grid.is_point_solid(game.navigation.world_to_cell(point)) and not game.navigation.find_path(npc.position,point).is_empty():
			game.player.position=point
			break
	var start:Vector2=npc.position
	game.checkpoint(true); await until(func(): return game.api.idle())
	game.hud.show_npc(npc)
	game.hud.submit_text("伊莲娜，请过来我身旁看看，我想请你帮忙辨认一点药草。我就站在摊位旁两步远的地方，请走到我旁边再聊。")
	await until(func(): return not reply.is_empty() or not failures.is_empty())
	game.hud.close_dialogue()
	var moved:bool=await until(func(): return game.state.tasks.any(func(t): return t.actor_id==npc.entity_id and t.kind=="MOVE" and t.status=="succeeded"),10)
	var passed:bool=reply.get("mode")=="live" and moved and npc.position.distance_to(start)>20 and failures.is_empty()
	var result:={"passed":passed,"mode":reply.get("mode"),"reply":reply.get("reply"),"intent_status":reply.get("intent_status"),"actual_move_pixels":npc.position.distance_to(start),"task_succeeded":moved,"errors":failures}
	FileAccess.open("res://../release/validation/live-action-result.json",FileAccess.WRITE).store_string(JSON.stringify(result,"  "))
	print("REAL_MODEL_ACTION ",JSON.stringify(result))
	quit(0 if passed else 1)
