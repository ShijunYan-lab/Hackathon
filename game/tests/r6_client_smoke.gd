extends SceneTree
## Run with --headless --path game --script res://tests/r6_client_smoke.gd.
## This is a local UI resource smoke test, not a live-model or combat test.
class FakeAPI:
	extends RefCounted
	var connected: bool = true
	func idle() -> bool: return true
	func call_api(_op: String, _path: String, _body: Dictionary = {}, _versioned: bool = false, _switch: bool = false) -> void: pass
class FakeHUD:
	extends Node
	var map_open: bool = false
	var panel_open: bool = false
	func close_dialogue() -> void: pass
	func close_panel() -> void: pass
	func notice(_text: String, _duration: float = 0) -> void: pass
	func render_inventory() -> void: pass
class FakeWorld:
	extends Node
	var hud
	var api = FakeAPI.new()
	var state: Dictionary = {}
	var actors: Dictionary = {}
	func save_game() -> void: pass
func _initialize() -> void:
	call_deferred("run_checks")
func run_checks() -> void:
	var scene = load("res://main.tscn")
	if scene == null:
		push_error("Main scene cannot load")
		quit(1)
		return
	var instance = scene.instantiate()
	instance.free()
	var world = FakeWorld.new()
	world.hud = FakeHUD.new()
	world.add_child(world.hud)
	root.add_child(world)
	var windows = load("res://ui/play_windows.gd").new()
	windows.world = world
	world.add_child(windows)
	await process_frame
	if windows.screen != "title" or windows.appearance.item_count != 2:
		push_error("Title / appearance setup failed")
		quit(1)
		return
	windows.open_pause()
	await process_frame
	windows.open_settings()
	await process_frame
	windows.show_saves({"saves": []})
	await process_frame
	windows.show_shop({"gold": 12, "discount_percent": 0, "merchant_id": "test", "quote_id": "test", "stock": []})
	await process_frame
	windows.show_container({"container": {"id": "test", "label": "Chest", "gold": 0}, "items": []})
	await process_frame
	windows.show_journal({"entries": [], "quests": [], "has_more": false, "next_after_seq": 0})
	await process_frame
	windows.open_title()
	await process_frame
	print("R6 client UI/resource smoke checks passed. Visual and backend integration still need manual tests.")
	world.queue_free()
	await process_frame
	quit(0)
