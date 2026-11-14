extends Node2D
const Layout=preload("res://maps/world_layout.gd")
const Player=preload("res://maps/exploration_player.gd")
const NPC=preload("res://maps/exploration_npc.gd")
const Catalog=preload("res://maps/npc_catalog.gd")
const Hud=preload("res://ui/realm_hud.gd")
const Ambience=preload("res://maps/ambience.gd")
var player:CharacterBody2D
var hud:CanvasLayer
var interactable:Node2D
var near_npc:Node2D
var npcs:Array[Node2D]=[]
var canopies:Array[Node]=[]
var landmarks:Array[Node]=[]
var landmark_data:Array=[]
var update_timer:=0.0

func _ready()->void:
	player=Player.new()
	player.name="ExplorationPlayer"
	player.position=Layout.SPAWN
	$World/Entities.add_child(player)
	var water:=ShaderMaterial.new()
	water.shader=preload("res://maps/water.gdshader")
	$World/Terrain.material=water
	landmark_data=Layout.new().landmarks
	for item in Catalog.entries():
		var npc:=NPC.new()
		npc.name=item.appearance_key.capitalize()
		npc.data=item
		npc.position=item.tile*32
		$World/Entities.add_child(npc)
		npcs.append(npc)
	var ambience:=Ambience.new()
	ambience.player=player
	ambience.z_index=2
	add_child(ambience)
	hud=Hud.new()
	hud.world=self
	add_child(hud)
	canopies=get_tree().get_nodes_in_group("canopies")
	landmarks=get_tree().get_nodes_in_group("landmarks")
	# No fog node or radial/line-of-sight screen mask: the whole viewport is visible.

func _process(delta:float)->void:
	update_timer-=delta
	if update_timer>0: return
	update_timer=0.12
	near_npc=null
	var nearest:=93.0
	for npc in npcs:
		var distance:=player.position.distance_to(npc.position)
		if distance<nearest:
			nearest=distance
			near_npc=npc
	interactable=null
	nearest=75.0
	for place in landmarks:
		var distance:=player.position.distance_to(place.position)
		if distance<nearest:
			nearest=distance
			interactable=place
	for tree in canopies:
		var diff:Vector2=player.position-tree.position
		var obscured:bool=absf(diff.x)<47 and diff.y<0 and diff.y> -133
		tree.get_node("Art").modulate.a=0.42 if obscured else 1.0

func _unhandled_input(event:InputEvent)->void:
	if event.is_action_pressed("toggle_map"):
		if hud.dialog_open: return
		hud.map_open=not hud.map_open
		player.set_controls_locked(hud.map_open)
	elif event.is_action_pressed("ui_cancel"):
		hud.map_open=false
		hud.close_dialogue()
		player.set_controls_locked(false)
	elif event.is_action_pressed("interact") and not hud.dialog_open and not hud.map_open:
		if near_npc: hud.show_npc(near_npc)
		elif interactable: hud.show_place(interactable)
	elif event.is_action_pressed("appearance") and not player.locked: player.switch_appearance()
