extends RefCounted
## In the integrated project D can customize InputMap; these are safe fallbacks.
static func ensure_actions() -> void:
    var controls: Dictionary = {
        "move_left": KEY_A, "move_right": KEY_D,
        "move_up": KEY_W, "move_down": KEY_S,
        "interact": KEY_E, "dodge": KEY_SPACE, "sprint": KEY_SHIFT,
        "slot_melee": KEY_1, "slot_ranged": KEY_2
    }
    for action in controls:
        if not InputMap.has_action(action):
            InputMap.add_action(action)
        var key := InputEventKey.new()
        key.physical_keycode = int(controls[action])
        if not InputMap.action_has_event(action, key):
            InputMap.action_add_event(action, key)
    if not InputMap.has_action("attack"):
        InputMap.add_action("attack")
    var mouse := InputEventMouseButton.new()
    mouse.button_index = MOUSE_BUTTON_LEFT
    if not InputMap.action_has_event("attack", mouse):
        InputMap.action_add_event("attack", mouse)
