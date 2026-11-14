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
	data=Reference.descriptor(sprite_skin)
	portrait=Reference.texture_for(sprite_skin,false)
	visual_frame_size=Vector2i(48,64)
	visual.sprite_frames=Reference.build(sprite_skin,false)
	visual.texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
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
	if not actor.alive or actor.get("task_id")==null:
		current_task_id=""
		active_task={}
	# Snapshot positions lag the locally executing controller. Restore live motion.
	var before:=global_position
	super.apply_actor_state(actor)
	if alive: collision_mask=3
	if alive and (not reported.is_empty() or npc_type in ["wolf","wisp"]): global_position=before
	data.id=entity_id
	data.name=display_name

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
