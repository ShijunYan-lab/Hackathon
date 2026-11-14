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
var world_epoch:int=0
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
var local_backend_pid:int=-1
var local_starting:bool=false
var local_setup_pid:int=-1
var local_setup_pending:bool=false
var autostart:=true
var persistent_session:=true
var play_ui
var resource_nodes: Dictionary = {}
var container_nodes: Dictionary = {}
var scene_props: Array[Node2D] = []
var nearby_prop = null
var debug_ui: bool = false
var autosave_timer: float = 0.0

func _ready()->void:
	get_tree().auto_accept_quit = false
	for arg in OS.get_cmdline_user_args():
		if arg=="--no-autostart": autostart=false
		if arg=="--fresh": persistent_session=false
		if arg=="--debug-ui": debug_ui=true
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
	_spawn_scene_props()
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
	play_ui=preload("res://ui/play_windows.gd").new()
	play_ui.world=self
	add_child(play_ui)
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
	var menu_blocked: bool = is_instance_valid(play_ui) and play_ui.modal_open
	player.set_controls_locked(blocked or menu_blocked or hud.dialog_open or hud.map_open or hud.panel_open or not evaluation.is_empty())
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
		npc.set_controls_locked(blocked or ((menu_blocked or hud.panel_open or hud.dialog_open) and evaluation.is_empty()) or (not evaluation.is_empty() and not evaluation_running))
		var d:float=player.position.distance_to(npc.position)
		if npc.alive and npc.actor_kind=="npc" and d<distance:
			distance=d
			near_npc=npc
	nearby_prop = null
	var nearby_prop_distance: float = 56.0
	for prop in scene_props:
		var prop_distance: float = player.position.distance_to(prop.position)
		if prop_distance < nearby_prop_distance:
			nearby_prop_distance = prop_distance
			nearby_prop = prop
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
	for projectile in get_tree().get_nodes_in_group("world_projectiles"):
		projectile.set_physics_process(not (blocked or ((menu_blocked or hud.dialog_open or hud.panel_open) and evaluation.is_empty())))
	if blocked or menu_blocked: return
	autosave_timer+=delta
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
	elif api.idle() and evaluation.is_empty() and autosave_timer>=60 and not hud.dialog_open and not hud.panel_open:
		autosave_timer=0
		save_game()
	elif api.idle() and evaluation.is_empty() and advance_timer>=3 and not hud.dialog_open and not hud.panel_open:
		advance_timer=0
		api.call_api("advance","/v1/worlds/{world}/heartbeat",{"reason":"idle_timer","trigger_event_ids":[]},true)

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
	hit.attack_id=api.session+"-"+session_world+"-"+str(world_epoch)+"-"+str(payload.attack_id)
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
		world_epoch+=1
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
		if actor != player: actor.safe_zones = next.get("safe_zones", [])
		actors[id]=actor
		var slots: Dictionary = {}
		for slot in actor.WEAPON_CATALOG.EQUIPMENT_SLOTS: slots[slot] = ""
		for slot in value.get("equipped_slots", {}): slots[slot] = value.equipped_slots[slot]
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
	_sync_containers()
	_sync_resources()
	var female: bool = str(next.get("appearance", "male")) == "female"
	if player.female != female:
		player.female = female
		player._load_visual_frames()
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
	var nearest_resource = null
	var resource_distance: float = 60.0
	for node in resource_nodes.values():
		var d: float = player.position.distance_to(node.position)
		if d < resource_distance and (near_npc == null or d < player.position.distance_to(near_npc.position)):
			nearest_resource=node
			resource_distance=d
	if nearest_resource != null:
		checkpoint(true)
		var action: String = "BOARD" if nearest_resource.data.kind=="board" else "GATHER"
		api.call_api("interact","/v1/worlds/{world}/interact",{"action":action,"target_id":nearest_resource.data.id},true)
		return
	for node in loot.values():
		if player.position.distance_to(node.position)<=60:
			checkpoint(true)
			api.command("PICKUP",{"actor_id":player.entity_id,"item_id":node.item.id})
			return
	var nearest_box = null
	var nearest_distance: float = 56.0
	for box in container_nodes.values():
		var d: float = player.position.distance_to(box.position)
		if d < nearest_distance:
			nearest_box = box
			nearest_distance = d
	if nearest_box != null and nearest_box.data.get("kind") != "merchant" and (near_npc == null or nearest_distance < player.position.distance_to(near_npc.position)):
		checkpoint(true)
		api.call_api("container", "/v1/worlds/{world}/containers/" + str(nearest_box.data.id))
		return
	if near_npc:
		if near_npc.active_task.get("kind")=="ATTACK":
			hud.notice("对方正在自卫；请先停手并拉开距离。")
			return
		hud.show_npc(near_npc)
		checkpoint(true)
		api.call_api("history","/v1/worlds/{world}/dialogue/"+str(near_npc.entity_id)+"/history")
	elif nearest_box != null:
		hud.notice("\u8fd9\u662f\u5546\u4eba\u7684\u8d27\u7bb1\uff0c\u8bf7\u4e0e\u4ed6\u4ea4\u8c08\u67e5\u770b\u5546\u54c1\u3002")
	elif nearby_prop != null:
		hud.notice(str(nearby_prop.get("data").get("label", "场景物件")) + "：" + str(nearby_prop.get("data").get("description", "")), 7.0)
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
				_start_local_backend()
				return
			if str(data.get("play_revision", "")) != "r7":
				api.connected = false
				_start_local_backend()
				return
			api.call_api("model_status", "/v1/local/model")
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
			for action in data.get("ui_actions", []):
				if action.kind == "open_trade": api.call_api("shop", "/v1/worlds/{world}/shops/" + str(action.merchant_id))
				elif action.kind == "show_quests": play_ui.request_journal()
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
		"EQUIP","PICKUP","GIVE","offer","craft","ACCEPT_OFFER","supply","consume":
			hud.notice("已确认。" if operation!="offer" else "提议已送达，等待对方决定。")
			api.call_api("economy","/v1/worlds/{world}/economy")
	if operation == "create" and data.has("save_id"):
		save_id = str(data.save_id)
		remember_session()
	if is_instance_valid(play_ui): play_ui.complete(operation, data)
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
	if is_instance_valid(play_ui):
		play_ui.notice(message)
		play_ui.after_save = ""
	if operation.begins_with("evaluation_"): evaluation_transition=false
	if message.contains("EVALUATION_FROZEN") and evaluation.is_empty():
		api.call_api("resume","/v1/worlds/{world}/state")
	if operation=="dialogue": hud.receive_reply(message,"fallback")
	elif hud.pending and message.contains("VERSION_CONFLICT"): hud.receive_reply("世界已更新，请重新发送这句话。","fallback")
	if operation=="health" and not boot_started and autostart and api.base_url=="http://127.0.0.1:8765":
		_start_local_backend()
	elif operation=="resume" and state.is_empty() and api.connected:
		hud.notice("旧世界无法读取；F9 重试，或从主菜单开始新旅途。原存档仍保留。",30)

## Explicit Windows action from the title screen. This does not install anything
## until the player clicks the button. Setup runs in a separate console and
## writes an atomic success/failure marker after dependency verification.
func install_local_runtime() -> void:
	if local_setup_pending:
		play_ui.notice("运行环境正在安装，请查看弹出的 PowerShell 窗口。")
		return
	if OS.get_name() != "Windows":
		play_ui.notice("自动安装仅支持 Windows；请在项目根目录手动执行 Setup_Game.bat。")
		return
	if api.connected:
		play_ui.notice("当前世界已经连接，不需要安装运行环境。")
		return
	var root:String=ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	var setup_script:String=root.path_join("release/setup_game.ps1")
	if not FileAccess.file_exists(setup_script):
		play_ui.notice("找不到 release/setup_game.ps1；请重新解压完整游戏源码。")
		return
	DirAccess.make_dir_recursive_absolute(root.path_join("runtime"))
	var result_path:String=root.path_join("runtime/godot-setup-result.json")
	if FileAccess.file_exists(result_path):
		DirAccess.remove_absolute(result_path)
	var arguments:=PackedStringArray(["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", setup_script, "-StatusPath", result_path])
	local_setup_pid=OS.create_process("powershell.exe", arguments, true)
	if local_setup_pid<=0:
		play_ui.notice("未能启动 PowerShell；请在项目根目录运行 Setup_Game.bat。")
		return
	local_setup_pending=true
	play_ui.notice("安装程序已启动，请查看弹出的 PowerShell 窗口；依赖验证通过后将自动连接。")
	_poll_local_setup(result_path)

func _poll_local_setup(result_path:String) -> void:
	while local_setup_pending and is_inside_tree():
		await get_tree().create_timer(0.5).timeout
		if not is_inside_tree(): return
		if FileAccess.file_exists(result_path):
			var raw:String=FileAccess.get_file_as_string(result_path)
			var parsed:Variant=JSON.parse_string(raw)
			if parsed is Dictionary:
				local_setup_pending=false
				if parsed.get("status", "") == "ready":
					play_ui.notice("运行环境已安装，正在启动本地世界服务……")
					_start_local_backend()
				else:
					play_ui.notice("安装失败：" + str(parsed.get("message", "请检查 PowerShell 窗口。")))
				return
		if local_setup_pid>0 and not OS.is_process_running(local_setup_pid):
			# Let the PowerShell process finish writing the result file.
			await get_tree().create_timer(0.5).timeout
			if not FileAccess.file_exists(result_path):
				local_setup_pending=false
				play_ui.notice("安装进程已退出但未生成结果，请运行 Setup_Game.bat 查看错误。")
				return

func _start_local_backend() -> void:
	if local_starting: return
	if local_backend_pid>0 and OS.is_process_running(local_backend_pid):
		play_ui.notice("这个目录中的后端仍不匹配。请使用完整 R7 运行包，不要只在旧 R6 工程中替换客户端。")
		return
	local_starting=true
	boot_started=true
	api.connected=false
	play_ui.notice("发现旧服务或尚未连接，正在为本版游戏启动独立服务……")
	var project_root:String=ProjectSettings.globalize_path("res://").trim_suffix("/").get_base_dir()
	if not FileAccess.file_exists(project_root.path_join("server/world/continuity.py")):
		local_starting=false
		play_ui.notice("当前目录缺少 R7 后端。请打开完整 R7 运行包的 Start_Game.bat。")
		return
	var python:String=""
	for relative in [".runtime/python/python.exe",".venv/Scripts/python.exe"]:
		var candidate:String=project_root.path_join(relative)
		if FileAccess.file_exists(candidate):
			python=candidate
			break
	if python.is_empty():
		local_starting=false
		play_ui.notice("尚未安装本地 Python 环境。请点击主菜单的「安装/修复运行环境」，或运行 Start_Game.bat。")
		return
	var port:int=0
	for candidate in range(8766,8866):
		var probe:=TCPServer.new()
		if probe.listen(candidate,"127.0.0.1")==OK:
			port=candidate
			probe.stop()
			break
	if port==0:
		local_starting=false
		play_ui.notice("暂时没有可用的本地端口，请关闭多余的游戏窗口后重试。")
		return
	DirAccess.make_dir_recursive_absolute(project_root.path_join("runtime"))
	api.queue.clear()
	api.active={}
	api.suspended=false
	api.http.cancel_request()
	api.base_url="http://127.0.0.1:"+str(port)
	var database:String=project_root.path_join("runtime/playable-r7.sqlite3")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--local-db="):database=argument.trim_prefix("--local-db=")
	local_backend_pid=OS.create_process(python,[project_root.path_join("release/run_backend.py"),"--port",str(port),"--db",database],false)
	if local_backend_pid<0:
		local_starting=false
		play_ui.notice("本版服务未能启动，请使用 Start_Game.bat 查看错误。")
		return
	for attempt in range(80):
		await get_tree().create_timer(0.25).timeout
		if not OS.is_process_running(local_backend_pid):
			local_starting = false
			play_ui.notice("Python 后端启动后立即退出。请在项目根目录运行 Start_Game.bat，查看终端报错。")
			return
		var peer:=StreamPeerTCP.new()
		peer.connect_to_host("127.0.0.1",port)
		peer.poll()
		if peer.get_status()==StreamPeerTCP.STATUS_CONNECTING:
			await get_tree().create_timer(0.05).timeout
			peer.poll()
		var ready:bool=peer.get_status()==StreamPeerTCP.STATUS_CONNECTED
		peer.disconnect_from_host()
		if ready:
			local_starting=false
			play_ui.notice("本版服务已启动，正在建立连接……")
			api.call_api("health","/health")
			return
	local_starting=false
	play_ui.notice("本版服务启动超时。请运行 Start_Game.bat 查看后端错误；原存档未被删除。")

func _exit_tree() -> void:
	if local_backend_pid>0 and OS.is_process_running(local_backend_pid):
		OS.kill(local_backend_pid)

func _unhandled_input(event:InputEvent)->void:
	if event is InputEventKey and event.pressed and event.physical_keycode == KEY_F9:
		api.retry()
		return
	if is_instance_valid(play_ui) and play_ui.modal_open: return
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode == KEY_ESCAPE and not hud.dialog_open and not hud.panel_open and not hud.map_open:
			play_ui.open_pause()
			return
		match event.physical_keycode:
			KEY_F9: api.retry()
			KEY_F8:
				if state.is_empty() and api.connected and api.idle():
					api.call_api("create","/v1/worlds",{"seed":int(Time.get_unix_time_from_system())%2147483647,"player_name":"旅人"},false,true)
			KEY_F6: save_game()
			KEY_F7: load_game()
			KEY_TAB: hud.toggle_inventory()
			KEY_J: play_ui.request_journal()
			KEY_F2: play_ui.request_journal()
			KEY_F3:
				if debug_ui: hud.show_world_status()
			KEY_F4: hud.open_evaluation()
			KEY_ESCAPE: hud.close_panel()
	if hud.dialog_open or hud.panel_open: return
	if event.is_action_pressed("toggle_map"): hud.map_open=not hud.map_open
	elif event.is_action_pressed("interact"): interact()
	elif event.is_action_pressed("appearance") and debug_ui and not player.controls_locked: player.switch_appearance()
	elif event.is_action_pressed("ui_cancel"): hud.map_open=false


func npc_caption(npc) -> String:
	if not is_instance_valid(npc): return "\u65c5\u4eba"
	return str(npc.display_name) if str(npc.entity_id) in state.get("known_npc_ids", []) else "\u964c\u751f\u65c5\u4eba"

func _sync_containers() -> void:
	var present: Dictionary = {}
	for box in state.get("containers", []):
		present[box.id] = true
		if not container_nodes.has(box.id):
			var new_node = preload("res://maps/world_container.gd").new()
			$World/Entities.add_child(new_node)
			container_nodes[box.id] = new_node
		var node = container_nodes[box.id]
		node.data = box
		node.position = Vector2(float(box.tile.x), float(box.tile.y)) * 32
		node.queue_redraw()
	for identifier in container_nodes.keys():
		if not present.has(identifier):
			container_nodes[identifier].queue_free()
			container_nodes.erase(identifier)

func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		if state.is_empty() or not evaluation.is_empty():
			get_tree().quit()
		elif is_instance_valid(api) and api.connected and api.idle():
			play_ui.open_pause()
			play_ui.save_and_leave("quit")
		else:
			play_ui.open_pause()
			play_ui.notice("\u64cd\u4f5c\u5c1a\u672a\u7ed3\u675f\u3002\u8bf7\u5148\u7b49\u5f85\u6216\u91cd\u8fde\uff0c\u518d\u4fdd\u5b58\u9000\u51fa\u3002")

func _sync_resources() -> void:
	var present: Dictionary = {}
	var values: Array = state.get("sites",[]).duplicate()
	for entry in state.get("notices",[]):
		if entry.get("kind")=="board": values.append(entry)
	for value in values:
		var id: String = str(value.id)
		present[id]=true
		if not resource_nodes.has(id):
			var node=preload("res://maps/world_resource.gd").new()
			$World/Entities.add_child(node)
			resource_nodes[id]=node
		resource_nodes[id].data=value
		resource_nodes[id].position=Vector2(value.tile.x,value.tile.y)*32
		resource_nodes[id].queue_redraw()
	for id in resource_nodes.keys():
		if not present.has(id):
			resource_nodes[id].queue_free()
			resource_nodes.erase(id)

func _spawn_scene_props() -> void:
	var path: String = "res://maps/scene_props.json"
	if not FileAccess.file_exists(path): return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary: return
	for info in parsed.get("props", []):
		if not info is Dictionary: continue
		var tile: Dictionary = info.get("tile", {})
		var node := Node2D.new()
		node.set_script(preload("res://maps/world_prop.gd"))
		node.set("data", info)
		node.position = Vector2(float(tile.get("x", 0)), float(tile.get("y", 0))) * 32.0
		node.z_index = 0
		$World/Entities.add_child(node)
		scene_props.append(node)
