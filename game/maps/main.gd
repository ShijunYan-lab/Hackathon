extends Node2D
const Player = preload("res://maps/exploration_player.gd")
const Fog = preload("res://maps/field_of_view.gd")
const Hud = preload("res://ui/exploration_hud.gd")
const Layout = preload("res://maps/world_layout.gd")
const Ambience = preload("res://maps/ambience.gd")
var player: CharacterBody2D
var fog: Node2D
var hud: CanvasLayer
var interactable: Node2D
var canopy_timer := 0.0
var canopy_candidates: Array[Node] = []

func _ready() -> void:
	player = Player.new()
	player.name = "ExplorationPlayer"
	player.position = Layout.SPAWN
	$World/Entities.add_child(player)
	var water := ShaderMaterial.new()
	water.shader=preload("res://maps/water.gdshader")
	$World/Terrain.material=water
	var ambience:=Ambience.new()
	ambience.player=player
	ambience.z_index=2
	add_child(ambience)
	fog = Fog.new()
	fog.name = "FieldOfView"
	fog.player = player
	add_child(fog)
	hud = Hud.new()
	hud.world = self
	add_child(hud)
	canopy_candidates = get_tree().get_nodes_in_group("canopies")

func _process(delta: float) -> void:
	canopy_timer -= delta
	if canopy_timer>0: return
	canopy_timer=0.1
	interactable=null
	var nearest:=62.0
	for place in get_tree().get_nodes_in_group("landmarks"):
		var d: float = player.global_position.distance_to(place.global_position)
		if d<nearest and (not fog.enabled or fog.visible_from_player(place.global_position+Vector2(0,-10))):
			nearest=d
			interactable=place
	for tree in canopy_candidates:
		var diff: Vector2 = player.global_position-tree.global_position
		var obscured: bool = absf(diff.x)<31 and diff.y<0 and diff.y> -83
		tree.get_node("Art").modulate.a=0.42 if obscured else 1.0

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_map"):
		hud.map_open = not hud.map_open
		player.set_controls_locked(hud.map_open or hud.dialog_open)
	elif event.is_action_pressed("ui_cancel"):
		hud.map_open=false
		hud.dialog_open=false
		player.set_controls_locked(false)
	elif event.is_action_pressed("interact"):
		if hud.dialog_open:
			hud.dialog_open=false
			player.set_controls_locked(hud.map_open)
		elif interactable and not hud.map_open:
			hud.show_place(str(interactable.get_meta("title")),str(interactable.get_meta("description")))
			player.set_controls_locked(true)
	elif event.is_action_pressed("appearance") and not player.locked:
		player.switch_appearance()
