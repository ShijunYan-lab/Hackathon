extends Node2D
## D owns HTTP orchestration; A executes motion; C settles all durable changes.
const Layout=preload("res://maps/world_layout.gd")
const PlayerScene=preload("res://actors/player.tscn")
const NpcScene=preload("res://actors/npc.tscn")
const PlayerAdapter=preload("res://maps/network_player.gd")
const NpcAdapter=preload("res://maps/network_npc.gd")
const Api=preload("res://net/game_api.gd")
var player
var hud
var api
var navigation
var actors:Dictionary={}
var loot:Dictionary={}
var state:Dictionary={}
var economy:Dictionary={}
var near_npc:Node2D
var interactable:Node2D
var landmark_data:Array=[]
var landmarks:Array=[]
var canopies:Array=[]
var checkpoint_timer:=0.0
var advance_timer:=0.0
var evaluation_timer:=0.0
var last_positions:=""
var session_world:=""
var save_id:=""
var ordinary_world:=""
var evaluation:Dictionary={}
var evaluation_report:Dictionary={}
var evaluation_running:=false
var evaluation_transition:=false
var model_mode:="未调用"
var boot_started:=false
var autostart:=true
var persistent_session:=true

func _ready()->void:
	for arg in OS.get_cmdline_user_args():
		if arg=="--no-autostart": autostart=false
		if arg=="--fresh": persistent_session=false
	player=PlayerScene.instantiate()
	player.set_script(PlayerAdapter)
	player.position=Layout.SPAWN
	player.controls_locked=true
	$World/Entities.add_child(player)
	player.hit_detected.connect(report_hit)
	player.equip_requested.connect(func(id): api.command("EQUIP",{"actor_id":player.entity_id,"item_id":id}))
	navigation=preload("res://maps/network_navigation.gd").new()
	add_child(navigation)
	landmark_data=Layout.new().landmarks
	landmarks=get_tree().get_nodes_in_group("landmarks")
	canopies=get_tree().get_nodes_in_group("canopies")
	var water:=ShaderMaterial.new()
	water.shader=preload("res://maps/water.gdshader")
	$World/Terrain.material=water
	var ambience=preload("res://maps/ambience.gd").new()
	ambience.player=player
	add_child(ambience)
	api=Api.new()
	add_child(api)
	api.state_received.connect(apply_state)
	api.completed.connect(_completed)
	api.failed.connect(_failed)
	hud=preload("res://ui/network_hud.gd").new()
	hud.world=self
	add_child(hud)
	hud.chat_submitted.connect(send_dialogue)
	if persistent_session:
		var config:=ConfigFile.new()
		if config.load("user://overworld-session.cfg")==OK:
			if str(config.get_value("session","server",""))==api.base_url:
				session_world=str(config.get_value("session","world",""))
				save_id=str(config.get_value("session","save",""))
				ordinary_world=str(config.get_value("session","ordinary_world",session_world))
	api.call_api("health","/health")

func remember_session()->void:
	if not persistent_session or not evaluation.is_empty() or evaluation_transition: return
	var config:=ConfigFile.new()
	config.set_value("session","server",api.base_url)
	config.set_value("session","world",session_world)
	config.set_value("session","save",save_id)
	config.set_value("session","ordinary_world",ordinary_world)
	config.save("user://overworld-session.cfg")

func _process(delta:float)->void:
	if not is_instance_valid(hud): return
	var blocked:bool=state.is_empty() or not api.connected or api.suspended or evaluation_transition
	player.set_controls_locked(blocked or hud.dialog_open or hud.map_open or hud.panel_open or not evaluation.is_empty())
	player.visible=evaluation.is_empty() and not evaluation_transition
	player.set_meta("observer",not player.visible)
	if not player.visible:
		player.collision_layer=0
		player.collision_mask=0
	elif player.alive:
		player.collision_layer=2
		player.collision_mask=3
	near_npc=null
	var distance:=64.0
	for id in actors:
		var npc=actors[id]
		if npc==player: continue
		npc.set_controls_locked(blocked or (not evaluation.is_empty() and not evaluation_running) or (hud.dialog_open and hud.current_npc==npc))
		var d:float=player.position.distance_to(npc.position)
		if npc.alive and npc.actor_kind=="npc" and d<distance:
			distance=d
			near_npc=npc
	interactable=null
	distance=75
	for place in landmarks:
		var d:float=player.position.distance_to(place.position)
		if d<distance:
			distance=d
			interactable=place
	for tree in canopies:
		var diff:Vector2=player.position-tree.position
		tree.get_node("Art").modulate.a=0.42 if absf(diff.x)<47 and diff.y<0 and diff.y> -133 else 1.0
	if blocked: return
	checkpoint_timer+=delta
	advance_timer+=delta
	evaluation_timer+=delta
	if api.idle() and checkpoint_timer>=1 and (evaluation.is_empty() or evaluation_running):
		checkpoint_timer=0
		checkpoint()
	if api.idle() and not evaluation.is_empty() and evaluation_timer>=1:
		evaluation_timer=0
		api.call_api("evaluation_poll","/v1/evaluations/"+str(evaluation.evaluation_id))
		var learner=actors.get(str(evaluation.learner_id))
		if learner:
			player.camera.global_position=learner.global_position
	elif api.idle() and evaluation.is_empty() and advance_timer>=30 and not hud.dialog_open and not actors.values().any(func(a): return a!=player and a.current_task_id!=""):
		advance_timer=0
		api.call_api("advance","/v1/worlds/{world}/advance",{"reason":"idle_timer","trigger_event_ids":[]},true)

func checkpoint(force:bool=false)->void:
	if state.is_empty(): return
	var positions:Array=[]
	for actor in actors.values():
		if actor.alive: positions.append(actor.collect_checkpoint())
	var signature:=JSON.stringify(positions)
	if not force and signature==last_positions: return
	last_positions=signature
	api.command("CHECKPOINT",{"region_id":"overworld","positions":positions})

func report_hit(payload:Dictionary)->void:
	if not api.connected or api.suspended or state.is_empty(): return
	if not evaluation.is_empty() and not evaluation_running: return
	var hit:=payload.duplicate(true)
	hit.attack_id=api.session+"-"+session_world+"-"+str(payload.attack_id)
	api.command("HIT",hit)

func report_task(payload:Dictionary)->void:
	if not evaluation.is_empty() and not evaluation_running: return
	api.command("TASK_REPORT",payload)

func apply_state(next:Dictionary,operation:String)->void:
	if str(next.current_region_id)!="overworld":
		api.connected=false
		hud.notice("后端使用了旧地图。请运行 release/start_game.ps1 的大地图服务。",30)
		return
	var switched:bool=state.get("world_id","")!=next.world_id
	if switched:
		hud.close_dialogue()
		for projectile in get_tree().get_nodes_in_group("world_projectiles"):
			projectile.get_parent().remove_child(projectile)
			projectile.queue_free()
		player.velocity=Vector2.ZERO
		player.knockback_velocity=Vector2.ZERO
		player.dodge_until_ms=0
		player.animation_lock_until_ms=0
		player.animation_attack_until_ms=0
		player.set_meta("attack_ready_at",0)
		for actor in actors.values():
			if actor!=player:
				actor.get_parent().remove_child(actor)
				actor.queue_free()
		actors.clear()
		last_positions=""
	state=next
	if not evaluation.is_empty() and evaluation_running and not next.tasks.any(func(t): return t.kind=="MOVE" and t.status in ["pending","running"]):
		stop_evaluation_actions()
	session_world=str(next.world_id)
	for value in next.actors:
		var id:=str(value.id)
		var fresh:=not actors.has(id)
		var actor
		if value.kind=="player": actor=player
		elif fresh:
			actor=NpcScene.instantiate()
			actor.set_script(NpcAdapter)
			actor.world_map=navigation
			$World/Entities.add_child(actor)
			actor.hit_detected.connect(report_hit)
			actor.task_reported.connect(report_task)
		else: actor=actors[id]
		if fresh or switched: actor.position=Vector2(value.tile.x,value.tile.y)*32
		actor.apply_actor_state(value)
		actors[id]=actor
		var slots:={"melee":"","ranged":""}
		for item in next.items:
			if item.id==value.equipped_item_id:
				var group:String=actor.WEAPON_CATALOG.group_for_type(str(item.base_type))
				if not group.is_empty():
					slots[group]=item.id
					actor.active_weapon_slot=group
		var owned:Array=next.items.filter(func(item): return item.owner_id==id)
		var coins:int=int(economy.get("wallets",{}).get(id,0))
		var loadout_stamp:=JSON.stringify([owned,slots,coins])
		if str(actor.get_meta("loadout_stamp",""))!=loadout_stamp:
			actor.set_meta("loadout_stamp",loadout_stamp)
			actor.apply_inventory_snapshot(owned,slots,coins)
		if actor!=player and actor.alive and str(value.behavior)=="dead": actor.set_controls_locked(true)
	for id in actors.keys():
		if not next.actors.any(func(value): return str(value.id)==str(id)):
			actors[id].queue_free()
			actors.erase(id)
	for task in next.tasks:
		var actor=actors.get(str(task.actor_id))
		if operation=="refresh" and actor and actor!=player and task.status in ["pending","running"]:
			actor.reported.erase(str(task.id))
		if actor and actor!=player and task.status in ["pending","running"]: actor.execute_task(task)
	_sync_loot()
	if is_instance_valid(hud.current_npc) and (not hud.current_npc.alive or hud.current_npc.active_task.get("kind")=="ATTACK"): hud.close_dialogue()
	if switched:
		player.camera.position=Vector2.ZERO
		player.camera.reset_smoothing()
	if operation in ["create","resume","load"]:
		ordinary_world=session_world
		evaluation_transition=false
		remember_session()
		api.call_api("economy","/v1/worlds/{world}/economy")

func _sync_loot()->void:
	var present:Dictionary={}
	for item in state.items:
		if item.owner_id!=null or item.region_id!="overworld": continue
		present[item.id]=true
		if not loot.has(item.id):
			var node=preload("res://maps/world_item.gd").new()
			node.item=item
			$World/Entities.add_child(node)
			loot[item.id]=node
		loot[item.id].position=Vector2(item.tile.x,item.tile.y)*32
	for id in loot.keys():
		if not present.has(id):
			loot[id].queue_free()
			loot.erase(id)

func send_dialogue(id:String,value:String)->void:
	checkpoint(true)
	api.call_api("dialogue","/v1/worlds/{world}/dialogue",{"npc_id":id,"text":value},true)

func interact()->void:
	if player.controls_locked: return
	for node in loot.values():
		if player.position.distance_to(node.position)<=60:
			checkpoint(true)
			api.command("PICKUP",{"actor_id":player.entity_id,"item_id":node.item.id})
			return
	if near_npc:
		if near_npc.active_task.get("kind")=="ATTACK":
			hud.notice("对方正在自卫；请先停手并拉开距离。")
			return
		hud.show_npc(near_npc)
		checkpoint(true)
		api.call_api("history","/v1/worlds/{world}/dialogue/"+str(near_npc.entity_id)+"/history")
	elif interactable: hud.show_place(interactable)

func save_game()->void:
	if state.is_empty() or not evaluation.is_empty() or not api.idle(): return
	checkpoint(true)
	api.call_api("save","/v1/worlds/{world}/saves",{"label":"南境旅途 · "+Time.get_datetime_string_from_system()},true)

func load_game()->void:
	if save_id.is_empty() or not evaluation.is_empty() or not api.idle():
		hud.notice("暂无存档，或当前操作尚未结束。")
		return
	api.call_api("load","/v1/saves/"+save_id+"/load",{"api_version":"v1"},false,true)

func evaluation_action(action:String)->void:
	if not api.idle(): return
	if action=="create":
		if not evaluation.is_empty(): return
		ordinary_world=session_world
		remember_session()
		evaluation_transition=true
		checkpoint(true)
		api.call_api("evaluation_create","/v1/evaluations",{"seed":int(state.get("seed",42))},false,true)
	elif action=="return":
		if str(evaluation.get("status","")).ends_with("running") or evaluation.get("status")=="learning":
			hud.notice("运输还在执行，请等实际结果记录完成。")
			return
		evaluation={}
		api.call_api("resume","/v1/worlds/"+ordinary_world+"/state",{},false,true)
	elif not evaluation.is_empty():
		var path:="/v1/evaluations/"+str(evaluation.evaluation_id)
		if action=="report": api.call_api("evaluation_report",path+"/report")
		elif action=="profile": api.call_api("evaluation_profile",path+"/profile")
		elif action=="rollback": api.call_api("evaluation_rollback",path+"/rollback",{"expected_evaluation_version":evaluation.evaluation_version,"target":"baseline"},false,true)
		else: api.call_api("evaluation_run",path+"/runs",{"expected_evaluation_version":evaluation.evaluation_version,"kind":action},false,true)

func _completed(operation:String,data:Dictionary)->void:
	if operation=="dialogue" and data.has("mode"): model_mode=str(data.mode)
	match operation:
		"health":
			if data.has("region_id") and (data.region_id!="overworld" or int(data.get("map_width_tiles",0))!=320):
				api.connected=false
				hud.notice("8765 端口运行的是旧地图服务。请启动 release/run_backend.py。",30)
				return
			if state.is_empty():
				if session_world.is_empty(): api.call_api("create","/v1/worlds",{"seed":int(Time.get_unix_time_from_system())%2147483647,"player_name":"旅人"},false,true)
				else: api.call_api("resume","/v1/worlds/"+session_world+"/state",{},false,true)
		"resume","refresh":
			if data.get("evaluation_active",false):
				var recovery:String=str(data.get("recovery_world_id", "")) if data.get("recovery_world_id")!=null else ""
				if ordinary_world!="" and ordinary_world!=session_world: recovery=ordinary_world
				evaluation={}
				evaluation_transition=false
				hud.notice("已识别临时评审记录，正在恢复普通旅途。",10)
				if recovery!="": api.call_api("resume","/v1/worlds/"+recovery+"/state",{},false,true)
				else: api.call_api("create","/v1/worlds",{"seed":int(Time.get_unix_time_from_system())%2147483647,"player_name":"旅人"},false,true)
		"dialogue":
			if is_instance_valid(hud.current_npc) and str(data.get("npc_id",hud.current_npc.entity_id))==hud.current_npc.entity_id:
				hud.receive_reply(str(data.get("reply","")),model_mode)
		"history": hud.receive_history(data)
		"economy":
			economy=data
			if hud.panel_open and hud.panel_kind=="inventory": hud.render_inventory()
		"save":
			save_id=str(data.save_id)
			remember_session()
			hud.notice("旅途已保存。F7 读取此存档。")
		"load": hud.notice("已从存档恢复；死亡、物品与任务一并恢复。")
		"story": hud.show_story(data)
		"evaluation_create","evaluation_run","evaluation_poll","evaluation_rollback":
			evaluation_transition=false
			evaluation=data.get("session",{})
			evaluation_running=str(evaluation.get("status","")).ends_with("running")
			if hud.panel_kind=="evaluation": hud.render_evaluation(data.get("run",{}))
		"evaluation_report":
			evaluation_report=data
			hud.show_evaluation_report(data)
		"evaluation_profile": hud.show_profile(data)
		"EQUIP","PICKUP","GIVE","offer","craft","ACCEPT_OFFER","supply":
			hud.notice("已确认。" if operation!="offer" else "提议已送达，等待对方决定。")
			api.call_api("economy","/v1/worlds/{world}/economy")
	for event in data.get("events",[]):
		if event.type in ["npc_protested","npc_speech"] and operation!="dialogue":
			var speaker=actors.get(str(event.actor_id))
			if speaker and speaker!=player: speaker.say(str(event.facts.get("text","")))
		if event.type=="hit_applied":
			var attacker=actors.get(str(event.actor_id))
			if attacker:
				var cooldown:float=float(attacker.active_weapon().get("stats",{}).get("cooldown_s",0.5))
				attacker.set_meta("attack_ready_at",Time.get_ticks_msec()+int(cooldown*1000)+50)
			var target=actors.get(str(event.target_id))
			if attacker and target and target.alive:
				target.knockback_velocity=(target.global_position-attacker.global_position).normalized()*90
		if event.type=="player_recovered": player.position=Vector2(event.facts.tile.x,event.facts.tile.y)*32
		if event.type=="actor_died": hud.notice("有人倒下了。其物品与组织关系已由世界记录。")
		if event.type in ["first_finished","second_finished","rollback_check_finished"]: stop_evaluation_actions()

func stop_evaluation_actions()->void:
	evaluation_running=false
	api.queue=api.queue.filter(func(job): return job.op not in ["CHECKPOINT","HIT","TASK_REPORT"])
	for actor in actors.values(): actor.set_controls_locked(true)
	for projectile in get_tree().get_nodes_in_group("world_projectiles"): projectile.queue_free()

func _failed(operation:String,message:String)->void:
	last_positions=""
	hud.notice(message,12)
	if operation.begins_with("evaluation_"): evaluation_transition=false
	if message.contains("EVALUATION_FROZEN") and evaluation.is_empty():
		api.call_api("resume","/v1/worlds/{world}/state")
	if operation=="dialogue": hud.receive_reply(message,"fallback")
	elif hud.pending and message.contains("VERSION_CONFLICT"): hud.receive_reply("世界已更新，请重新发送这句话。","fallback")
	if operation=="health" and not boot_started and autostart and api.base_url=="http://127.0.0.1:8765":
		boot_started=true
		var root:=ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
		var python:=root.path_join(".venv/Scripts/pythonw.exe")
		if FileAccess.file_exists(python):
			OS.create_process(python,[root.path_join("release/run_backend.py")],false)
			hud.notice("正在启动本地世界服务……",8)
			await get_tree().create_timer(3).timeout
			api.retry()
	elif operation=="resume" and state.is_empty() and api.connected:
		hud.notice("旧世界无法读取；F9 重试，或 F8 开始新旅途。原存档仍保留。",30)

func _unhandled_input(event:InputEvent)->void:
	if event is InputEventKey and event.pressed and not event.echo:
		match event.physical_keycode:
			KEY_F9: api.retry()
			KEY_F8:
				if state.is_empty() and api.connected and api.idle():
					api.call_api("create","/v1/worlds",{"seed":int(Time.get_unix_time_from_system())%2147483647,"player_name":"旅人"},false,true)
			KEY_F6: save_game()
			KEY_F7: load_game()
			KEY_TAB: hud.toggle_inventory()
			KEY_J: api.call_api("story","/v1/worlds/{world}/story/chapters")
			KEY_F2: api.call_api("story","/v1/worlds/{world}/story/chapters")
			KEY_F3: hud.show_world_status()
			KEY_F4: hud.open_evaluation()
			KEY_ESCAPE: hud.close_panel()
	if hud.dialog_open or hud.panel_open: return
	if event.is_action_pressed("toggle_map"): hud.map_open=not hud.map_open
	elif event.is_action_pressed("interact"): interact()
	elif event.is_action_pressed("appearance") and not player.controls_locked: player.switch_appearance()
	elif event.is_action_pressed("ui_cancel"): hud.map_open=false
