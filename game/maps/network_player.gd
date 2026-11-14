extends "res://actors/player.gd"
signal equip_requested(item_id:String)
const Reference=preload("res://maps/reference_frames.gd")
var female:=false
var direction:=0
var camera:Camera2D

func _ready()->void:
	visual_foot_y=2
	hand_offset_y=12
	super._ready()
	collision_mask=3
	$CollisionShape2D.shape=$CollisionShape2D.shape.duplicate()
	$CollisionShape2D.shape.radius=10
	walk_speed=150
	sprint_speed=250
	camera=$Camera2D
	camera.limit_left=0
	camera.limit_top=0
	camera.limit_right=10240
	camera.limit_bottom=7168
	camera.position_smoothing_enabled=false

func _load_visual_frames()->void:
	visual_frame_size=Vector2i(48,64)
	visual.sprite_frames=Reference.build(sprite_skin,true,female)
	visual.texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	_align_visual_to_ground()
	_play_anim("idle0")

func _draw()->void: Reference.draw_actor(self,hp,max_hp,alive,display_name)

func apply_actor_state(actor:Dictionary)->void:
	super.apply_actor_state(actor)
	if alive: collision_mask=3

func play_move_animation(motion:Vector2,_facing:Vector2,sprinting:bool=false)->void:
	if motion.length()>5:
		if absf(motion.x)>absf(motion.y): direction=1 if motion.x<0 else 2
		else: direction=3 if motion.y<0 else 0
	visual.flip_h=false
	if Time.get_ticks_msec()<animation_lock_until_ms: return
	_play_anim(("idle" if motion.length()<5 else ("sprint" if sprinting else "run"))+str(direction))

func play_attack_visual(duration_ms:int=300)->void:
	animation_lock_until_ms=Time.get_ticks_msec()+duration_ms
	visual.play("attack"+str(direction))

func play_dodge_visual(duration_ms:int=220)->void:
	animation_lock_until_ms=Time.get_ticks_msec()+duration_ms
	visual.play("dodge"+str(direction))

func try_attack()->void:
	if controls_locked or not alive or Time.get_ticks_msec()<int(get_meta("attack_ready_at",0)): return
	if get_tree().get_nodes_in_group("world_projectiles").any(func(p): return p.shooter_id==entity_id): return
	super.try_attack()

func try_dodge(motion:Vector2=Vector2.ZERO)->void:
	if not controls_locked and alive: super.try_dodge(motion)

func try_interact()->void: pass # D resolves conversation, landmarks and real ground items.

func set_active_weapon_slot(slot:String)->void:
	if controls_locked: return
	var candidates:Array=[]
	for item in inventory_items:
		if WEAPON_CATALOG.group_for_type(str(item.base_type))==slot: candidates.append(str(item.id))
	if candidates.is_empty(): return
	var current:=str(active_weapon().get("id",""))
	equip_requested.emit(candidates[(candidates.find(current)+1)%candidates.size()])

func switch_appearance()->void:
	female=not female
	_load_visual_frames()

func _update_weapon_visual()->void:
	super._update_weapon_visual()
	if weapon_visual==null: return
	var kind:String=str(active_weapon().get("base_type","sword"))
	var grip:Vector2={"sword":Vector2(16,25),"axe":Vector2(16,25),"hammer":Vector2(16,26),"bow":Vector2(16,16),"crossbow":Vector2(16,23),"staff":Vector2(16,26)}.get(kind,Vector2(16,25))
	weapon_visual.position=Vector2(16,16)-grip
	weapon_visual.scale=Vector2.ONE

func _pose_weapon_idle(_force:bool=false)->void:
	if weapon_pivot==null or Time.get_ticks_msec()<animation_attack_until_ms: return
	if weapon_tween!=null and weapon_tween.is_running(): weapon_tween.kill()
	weapon_pivot.position=[Vector2(10,-18),Vector2(-10,-19),Vector2(10,-19),Vector2(-9,-22)][direction]
	weapon_pivot.z_index=-1 if direction==3 else 3
	weapon_pivot.rotation=-0.3 if direction==1 else 0.3
	var kind:String=str(active_weapon().get("base_type",""))
	if kind=="bow": weapon_pivot.rotation=PI if direction in [0,2] else 0.0

func _animate_weapon_swing(duration_ms:int,ranged:bool=false)->void:
	if weapon_pivot==null: return
	if weapon_tween!=null and weapon_tween.is_running(): weapon_tween.kill()
	weapon_pivot.position=Vector2(0,-18)+facing*10
	weapon_pivot.z_index=-1 if facing.y< -0.5 else 3
	var angle:=facing.angle()+PI/2
	if active_weapon().get("base_type")=="bow": angle=facing.angle()+PI
	weapon_pivot.rotation=angle if ranged else angle-0.9
	weapon_tween=create_tween()
	weapon_tween.tween_property(weapon_pivot,"rotation",angle+(0.10 if ranged else 0.9),float(duration_ms)/1000)
