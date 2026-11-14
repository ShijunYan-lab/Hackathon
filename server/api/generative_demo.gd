extends SceneTree
var refresh_elapsed := 0.0
var instance_guard := TCPServer.new()

func _initialize() -> void:
    call_deferred("start_demo")

func start_demo() -> void:
    var world_id := ""
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--world="):
            world_id = arg.trim_prefix("--world=")
    # Hold a local socket for the lifetime of this world's client. No network data
    # is exchanged; bind is atomic, unlike checking a PID file before launch.
    var port := 20000 + (world_id.hash() % 40000)
    if instance_guard.listen(port, "127.0.0.1") != OK:
        push_error("This experimental world already has an open game window.")
        quit(2)
        return
    var scene = load("res://main.tscn").instantiate()
    root.add_child(scene)
    current_scene = scene
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--world="):
            scene.session_world = arg.trim_prefix("--world=")
    scene.persistent_session = false

func _process(_delta: float) -> bool:
    # This scenario runner owns turn scheduling while external dialogue is in flight.
    # Actor movement and HTTP task reports still run in the original game scene.
    if "--manual-world-turns" in OS.get_cmdline_user_args() and is_instance_valid(current_scene):
        current_scene.advance_timer = 0.0
        refresh_elapsed += _delta
        if refresh_elapsed >= 1.0 and not current_scene.state.is_empty() and current_scene.api.idle():
            refresh_elapsed = 0.0
            current_scene.api.call_api("refresh", "/v1/worlds/{world}/state")
    return false
