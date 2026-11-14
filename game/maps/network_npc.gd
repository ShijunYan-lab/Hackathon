extends "res://actors/npc.gd"
const Reference=preload("res://maps/reference_frames.gd")
var data:Dictionary={}
var portrait:Texture2D
var reported:Dictionary={}
var home_position:=Vector2.ZERO
var speech:Label
var speech_box:PanelContainer
var speech_until:=0
var combat_started:=0
var corpse_cleanup_started: bool = false
var safe_zones: Array = []
var monster_home: Vector2 = Vector2.INF
var monster_roam: Vector2 = Vector2.ZERO
var monster_cooldown: float = 0.0
var monster_refresh: float = 0.0
var monster_target = null
var monster_cry_at: int = -60000

func _ready()->void:
	visual_foot_y=2
	hand_offset_y=12
	super._ready()
	collision_mask=3
	$CollisionShape2D.shape=$CollisionShape2D.shape.duplicate()
	$CollisionShape2D.shape.radius=10
	speech_box=PanelContainer.new()
	speech_box.position=Vector2(-107,-119)
	speech_box.custom_minimum_size=Vector2(214,40)
	speech_box.mouse_filter=Control.MOUSE_FILTER_IGNORE
	speech_box.z_index=100
	var bubble_style:=StyleBoxFlat.new()
	bubble_style.bg_color=Color("24201e")
	bubble_style.border_color=Color("b29963")
	bubble_style.set_border_width_all(1)
	bubble_style.content_margin_left=8; bubble_style.content_margin_right=8
	bubble_style.content_margin_top=4; bubble_style.content_margin_bottom=4
	speech_box.add_theme_stylebox_override("panel",bubble_style)
	add_child(speech_box)
	if Reference.font==null:
		Reference.font=SystemFont.new()
		Reference.font.font_names=PackedStringArray(["Microsoft YaHei","sans-serif"])
	speech=Label.new()
	speech.add_theme_font_override("font",Reference.font)
	speech.add_theme_font_size_override("font_size",11)
	speech.add_theme_color_override("font_color",Color("f2dfbc"))
	speech.add_theme_color_override("font_shadow_color",Color("171316"))
	speech.add_theme_constant_override("shadow_offset_x",1)
	speech.add_theme_constant_override("shadow_offset_y",1)
	speech.custom_minimum_size=Vector2(196,30)
	speech.max_lines_visible=2
	speech.horizontal_alignment=HORIZONTAL_ALIGNMENT_CENTER
	speech.vertical_alignment=VERTICAL_ALIGNMENT_CENTER
	speech.autowrap_mode=TextServer.AUTOWRAP_ARBITRARY
	speech_box.add_child(speech)
	speech_box.hide()

func say(value:String)->void:
	if not alive: return
	var lines:PackedStringArray=[]
	var line:=""
	for character in value.left(110):
		if character=="\n" or line.length()>=17 or Reference.font.get_string_size(line+character,HORIZONTAL_ALIGNMENT_LEFT,-1,11).x>190:
			lines.append(line)
			line="" if character=="\n" else character
		else: line+=character
	lines.append(line)
	speech.text="\n".join(lines.slice(0,2))+("…" if lines.size()>2 else "")
	speech_until=Time.get_ticks_msec()+7500
	speech.show()
	speech_box.show()
	set_meta("speech_active",true)

func _load_visual_frames()->void:
	if sprite_skin.begins_with("guard_"):
		_build_guard_visual()
		return
	if sprite_skin.begins_with("elite_") or sprite_skin.begins_with("hostile_") or sprite_skin in ["wolf", "boar", "spider", "ghoul", "swamp", "raven"]:
		var art_key: String = sprite_skin
		if art_key.begins_with("elite_"):
			art_key = art_key.trim_prefix("elite_") + "_1"
		elif art_key in ["wolf", "boar", "spider", "ghoul", "swamp", "raven"]:
			art_key += "_0"
		_build_creature_visual(art_key)
		return
	if sprite_skin in ["wisp"]:
		super._load_visual_frames()
		data = {"name":"", "role":"", "place":"", "greeting":""}
		portrait = load("res://actors/assets/sprites/wisp.png")
		return
	data=Reference.descriptor(sprite_skin)
	var portrait_atlas := AtlasTexture.new()
	portrait_atlas.atlas=Reference.texture_for(sprite_skin,false)
	portrait_atlas.region=Rect2(0,0,48,64)
	portrait=portrait_atlas
	visual_frame_size=Vector2i(48,64)
	visual.sprite_frames=Reference.build(sprite_skin,false)
	visual.texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	_align_visual_to_ground()
	_play_anim("idle")

func _build_guard_visual()->void:
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	var rows: Array = ["idle", "run", "attack", "death"]
	var counts: Array = [3, 4, 5, 4]
	for row in range(rows.size()):
		var action: String = str(rows[row])
		frames.add_animation(action)
		frames.set_animation_loop(action, row < 2)
		frames.set_animation_speed(action, 7.0 if row < 2 else 10.0)
		for index in range(int(counts[row])):
			var path: String = "res://assets/r7/%s_%d_%d.png" % [sprite_skin, row, index]
			if ResourceLoader.exists(path):
				frames.add_frame(action, load(path))
	for alias in ["hurt", "sprint", "dodge"]:
		frames.add_animation(alias)
		var origin: String = "idle" if alias == "hurt" else "run"
		frames.set_animation_loop(alias, alias == "sprint")
		frames.set_animation_speed(alias, 9)
		for index in range(frames.get_frame_count(origin)):
			frames.add_frame(alias, frames.get_frame_texture(origin, index))
	visual_frame_size = Vector2i(48, 64)
	visual.sprite_frames = frames
	portrait = frames.get_frame_texture("idle", 0) if frames.get_frame_count("idle") > 0 else null
	data = {"name":"", "role":"", "place":"", "greeting":""}
	visual.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_align_visual_to_ground()
	_play_anim("idle")

func _build_creature_visual(key:String)->void:
	var frames := SpriteFrames.new()
	frames.remove_animation("default")
	var actions: Array = ["idle", "run", "sprint", "attack", "hurt", "death", "dodge"]
	var counts: Array = [3, 4, 4, 5, 2, 4, 3]
	for i in range(actions.size()):
		var action: String = str(actions[i])
		frames.add_animation(action)
		frames.set_animation_loop(action, action in ["idle", "run", "sprint"])
		frames.set_animation_speed(action, 11.0 if action in ["run", "sprint", "attack"] else 7.0)
		for index in range(int(counts[i])):
			var path: String = "res://assets/r7/animations/%s_%s_%d.png" % [key, action, index]
			if ResourceLoader.exists(path):
				frames.add_frame(action, load(path))
			elif frames.get_frame_count(action) == 0:
				var base_path: String = "res://assets/r7/" + key + ".png"
				if ResourceLoader.exists(base_path): frames.add_frame(action, load(base_path))
	visual_frame_size = Vector2i(80, 80)
	visual.sprite_frames = frames
	var portrait_path: String = "res://assets/r7/" + key + ".png"
	portrait = load(portrait_path) if ResourceLoader.exists(portrait_path) else null
	data = {"name":"", "role":"", "place":"", "greeting":""}
	visual.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	_align_visual_to_ground()
	_play_anim("idle")

func _draw()->void: Reference.draw_actor(self,hp,max_hp,alive,display_name)

func _update_weapon_visual()->void:
	super._update_weapon_visual()
	# The supplied NPC action frames already contain their tools/weapons.
	# Avoid drawing a second floating icon through the reference character's face.
	if weapon_visual: weapon_visual.visible=false

func _physics_process(delta:float)->void:
	if speech:
		speech.visible=alive and Time.get_ticks_msec()<speech_until
		speech_box.visible=speech.visible
		set_meta("speech_active",speech.visible)
	if controls_locked:
		velocity=Vector2.ZERO
		return
	super._physics_process(delta)
	if alive: collision_mask=3

func _monster_species()->String:
	if sprite_skin.begins_with("elite_"):
		return sprite_skin.trim_prefix("elite_")
	if sprite_skin.begins_with("hostile_"):
		return "bandit"
	return sprite_skin

func _is_safe(tile_position:Vector2)->bool:
	for zone in safe_zones:
		if not zone is Dictionary: continue
		var center:Dictionary = zone.get("tile", {})
		if tile_position.distance_to(Vector2(float(center.get("x",0)), float(center.get("y",0)))*32.0) <= float(zone.get("radius",0))*32.0:
			return true
	return false

func _monster_logic(delta:float)->void:
	if sprite_skin == "wisp":
		super._monster_logic(delta)
		return
	if monster_home == Vector2.INF:
		monster_home = global_position
	var species: String = _monster_species()
	var elite: bool = sprite_skin.begins_with("elite_")
	var sight: float = (250.0 if species in ["ghoul", "bandit"] else 185.0) + (60.0 if elite else 0.0)
	monster_refresh -= delta
	if monster_refresh <= 0.0 or not is_instance_valid(monster_target) or not monster_target.alive:
		monster_refresh = 0.35
		monster_target = null
		var best: float = sight
		for other in get_tree().get_nodes_in_group("world_actors"):
			if other == self or not other.alive or other.actor_kind == "monster" or other.region_id != region_id or other.get_meta("observer",false): continue
			if _is_safe(other.global_position): continue
			var dis: float = global_position.distance_to(other.global_position)
			if dis < best:
				best = dis
				monster_target = other
	if monster_target != null and is_instance_valid(monster_target):
		var difference:Vector2 = monster_target.global_position-global_position
		var hp_ratio:float = float(hp)/float(maxi(1,max_hp))
		if hp_ratio < (0.20 if elite else 0.32) and species in ["raven", "wolf", "bandit"]:
			move_speed = 115.0
			_move_toward(delta, global_position-difference.normalized()*110.0, 16.0)
			return
		move_speed = 105.0 if species in ["wolf", "boar", "spider", "raven"] else 76.0
		if elite: move_speed *= 1.18
		var weapon:Dictionary = active_weapon()
		var attack_distance:float = 125.0 if active_weapon_slot == "ranged" and not weapon.is_empty() else 30.0
		if species == "boar" and difference.length() < 90.0: move_speed = 170.0
		if species == "spider" and difference.length() < 75.0: move_speed = 130.0
		if difference.length() > attack_distance:
			_move_toward(delta,monster_target.global_position,attack_distance*0.76)
		else:
			velocity = knockback_velocity
			move_and_slide()
			decay_knockback(delta)
			play_move_animation(Vector2.ZERO,difference)
		if difference.length() < (attack_distance+15.0): _attack_target(monster_target)
		if elite and Time.get_ticks_msec()-monster_cry_at>14000:
			monster_cry_at=Time.get_ticks_msec()
			say("危险的精英敌人逼近了！")
		return
	# Idle wildlife explore locally rather than standing still; avoid large path solves off-screen.
	var player_node = get_tree().get_first_node_in_group("world_players")
	if player_node == null:
		for node in get_tree().get_nodes_in_group("world_actors"):
			if node.actor_kind == "player":player_node=node;break
	if player_node != null and global_position.distance_to(player_node.global_position)>1100.0:
		velocity=knockback_velocity
		move_and_slide()
		decay_knockback(delta)
		return
	monster_cooldown -= delta
	if monster_cooldown <= 0.0 or global_position.distance_to(monster_roam)<20.0:
		monster_cooldown = 3.0 + randf()*4.0
		var angle:float = randf()*TAU
		monster_roam = monster_home + Vector2(cos(angle),sin(angle))*randf_range(35.0,145.0)
		if _is_safe(monster_roam):monster_roam=monster_home
	move_speed=53.0 if species in ["ghoul", "swamp", "spider"] else 68.0
	_move_toward(delta,monster_roam,18.0)

func _execute_active_task(delta:float)->void:
	if active_task.get("kind")=="ATTACK":
		var target=_actor_by_id(str(active_task.get("target_id","")))
		if target and (target.position.distance_to(position)>260 or Time.get_ticks_msec()-combat_started>18000):
			_finish_task("failed","self_defense_ended")
			return
	super._execute_active_task(delta)

func _move_to_position(delta:float)->void:
	# Physical actors occupy a 20px footprint; arrival remains within C's 24px tolerance.
	if global_position.distance_to(target_position)<=23:
		velocity=Vector2.ZERO
		completed_move=true
		_finish_task("succeeded","")
		return
	_move_toward(delta,target_position,22)

func _nearest_nonmonster(max_distance:float):
	var result=null
	var closest:=max_distance
	for actor in get_tree().get_nodes_in_group("world_actors"):
		if actor==self or not actor.alive or actor.region_id!=region_id or actor.actor_kind=="monster" or actor.get_meta("observer",false): continue
		var distance:float=position.distance_to(actor.position)
		if distance<closest:
			closest=distance
			result=actor
	return result

func apply_actor_state(actor:Dictionary)->void:
	npc_type="wolf" if actor.kind=="monster" else "civilian"
	if actor.get("appearance_key")=="wisp": npc_type="wisp"
	if not actor.alive or actor.get("task_id")==null:
		current_task_id=""
		active_task={}
	# Snapshot positions lag the locally executing controller. Restore live motion.
	var before:=global_position
	super.apply_actor_state(actor)
	if actor.kind=="monster" and monster_home==Vector2.INF: monster_home=global_position
	if alive: collision_mask=3
	if alive and (not current_task_id.is_empty() or not reported.is_empty() or npc_type in ["wolf","wisp"]): global_position=before
	data.id=entity_id
	data.name=display_name
	if not alive and not corpse_cleanup_started:
		corpse_cleanup_started = true
		collision_layer = 0
		collision_mask = 0
		speech_box.hide()
		var fade = create_tween()
		fade.tween_interval(0.7)
		fade.tween_property(self, "modulate:a", 0.0, 0.7)
		fade.tween_callback(hide)

func execute_task(task:Dictionary)->void:
	if reported.has(str(task.id)): return
	if task.get("kind")=="ATTACK" and str(task.id)!=current_task_id: combat_started=Time.get_ticks_msec()
	super.execute_task(task)

func _attack_target(target)->void:
	if controls_locked or Time.get_ticks_msec()<int(get_meta("attack_ready_at",0)): return
	if get_tree().get_nodes_in_group("world_projectiles").any(func(p): return p.shooter_id==entity_id): return
	super._attack_target(target)

func _finish_task(status:String,reason:String)->void:
	if not current_task_id.is_empty(): reported[current_task_id]=true
	super._finish_task(status,reason)
