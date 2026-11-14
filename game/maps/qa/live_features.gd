extends SceneTree
## Isolated fixture world only. Tests real A physics and C settlement.
const Projectile=preload("res://combat/projectile.gd")
var game
var passed:=0
var failures:Array[String]=[]
var errors:Array=[]
var hits:Array=[]
var origin:=Vector2(120.5,143.5)*32
func _initialize()->void: call_deferred("run")
func check(ok:bool,label:String)->void:
	if ok: passed+=1; print("PASS ",label)
	else: failures.append(label); push_error("FAIL "+label)
func until(predicate:Callable,seconds:float=10)->bool:
	var deadline:=Time.get_ticks_msec()+int(seconds*1000)
	while not predicate.call() and Time.get_ticks_msec()<deadline: await create_timer(0.02).timeout
	return predicate.call()
func idle()->void: await until(func(): return game.api.idle(),30)
func gone(node:Node)->void:
	var instance:int=node.get_instance_id()
	await until(func(): return not is_instance_id_valid(instance))
func arrow(bow:Dictionary):
	var shot=Projectile.new()
	shot.configure(game.player,bow,"qa_volume",Vector2.RIGHT)
	shot.position=origin+Vector2(12,0)
	shot.hit_target.connect(func(payload): hits.append(payload))
	game.get_node("World/Entities").add_child(shot)
	return shot
func run()->void:
	game=load("res://main.tscn").instantiate()
	root.add_child(game); current_scene=game
	game.api.failed.connect(func(op,message): errors.append([op,message]))
	game.advance_timer=-9999
	game.checkpoint_timer=-9999
	if not await until(func(): return not game.state.is_empty(),25): check(false,"connect"); finish(); return
	await idle()
	var npcs:Array=game.actors.values().filter(func(a): return a!=game.player)
	var homes:Dictionary={}
	for npc in npcs: homes[npc.entity_id]=npc.position
	check(homes.values().size()==15 and npcs.all(func(n): return n.position.distance_to(game.player.position)>150),"15 NPCs at individual workplaces, forests and ruins")
	check(npcs.all(func(n): return n.collision_layer==2 and n.collision_mask==3 and n.get_node("CollisionShape2D").shape.radius==10),"all 15 NPC types have solid foot colliders")
	game.player.position=origin
	var bow:Dictionary=game.player.inventory_items.filter(func(i): return i.base_type=="bow")[0]
	var shot=arrow(bow)
	await until(func(): return not is_instance_valid(shot) or shot.remaining_px<shot.total_range*0.3)
	check(is_instance_valid(shot) and not shot.finished and shot.visual.modulate.a>0 and shot.visual.modulate.a<0.75,"arrow fades progressively while its collider remains active")
	await gone(shot)
	var obstacle:=StaticBody2D.new()
	var shape:=CollisionShape2D.new()
	var rect:=RectangleShape2D.new(); rect.size=Vector2(2,40); shape.shape=rect
	obstacle.add_child(shape); obstacle.position=origin+Vector2(70,0)
	game.get_node("World/Entities").add_child(obstacle)
	await physics_frame
	shot=arrow(bow)
	await until(func(): return not is_instance_valid(shot) or shot.finished)
	check(is_instance_valid(shot) and shot.position.x<origin.x+72 and hits.is_empty(),"swept projectile stops on a thin solid object")
	obstacle.queue_free(); await gone(shot)
	for npc in npcs:
		npc.position=origin+Vector2(80,0)
		await physics_frame
		shot=arrow(bow)
		await gone(shot)
		if not hits.any(func(h): return h.target_id==npc.entity_id): print("MISS ",npc.sprite_skin," at ",npc.position)
		npc.position=homes[npc.entity_id]
		await create_timer(0.06).timeout # Flush physics transforms before placing the next actor.
	check(hits.size()==15 and npcs.all(func(n): return hits.any(func(h): return h.target_id==n.entity_id)),"arrows hit every NPC reference type")
	var victim=npcs[0]
	victim.position=origin+Vector2(48,0)
	Input.action_press("move_right")
	await create_timer(0.6).timeout
	Input.action_release("move_right")
	check(game.player.position.x<victim.position.x and game.player.position.distance_to(victim.position)>=19,"walking cannot pass through a living NPC")
	game.player.position=origin
	game.checkpoint(true); await idle()
	var hp:int=game.player.hp
	game.player.facing=Vector2.RIGHT
	game.player.try_attack()
	check(await until(func(): return victim.active_task.get("kind")=="ATTACK",4),"attacked NPC enters server-authorized self defense")
	check(victim.speech.visible and victim.speech.text.contains("住手"),"attack produces visible NPC criticism")
	check(await until(func(): return game.player.hp<hp,6),"NPC counterattack visibly executes and reduces C player HP")
	game.player.position=origin-Vector2(320,0)
	game.checkpoint(true); await idle()
	check(await until(func(): return victim.active_task.get("kind")=="MOVE",5),"NPC stops chasing a distant player and returns home")
	game.hud.toggle_inventory(); await idle()
	var kinds:Array=[]
	for index in range(game.hud.inventory.item_count):
		game.hud.inventory.item_selected.emit(index)
		kinds.append(game.hud.weapon_portrait.kind)
	check(["sword","axe","hammer","bow","crossbow","staff"].all(func(k): return k in kinds),"all six inventory weapons select matching large illustrations")
	game.hud.close_panel()
	var ordinary:String=game.session_world
	game.evaluation_action("create"); await idle()
	var frozen:String=game.session_world
	game.evaluation={}
	game.ordinary_world=ordinary
	game.api.call_api("resume","/v1/worlds/"+frozen+"/state",{},false,true)
	await idle()
	check(game.session_world==ordinary and game.evaluation.is_empty() and game.actors.size()==16,"stale frozen session automatically restores the ordinary world")
	game.save_game(); await idle()
	check(not game.save_id.is_empty(),"ordinary saving works after frozen recovery")
	check(errors.is_empty(),"no rejected API operations")
	finish()
func finish()->void:
	FileAccess.open("res://../release/validation/live-features-results.json",FileAccess.WRITE).store_string(JSON.stringify({"passed":passed,"failed":failures,"errors":errors},"  "))
	print("LIVE_FEATURES_QA ",passed," passed; ",failures.size()," failed")
	quit(0 if failures.is_empty() else 1)
