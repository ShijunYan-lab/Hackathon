extends SceneTree
## Run with: godot --headless --path game --script res://tests/verify_sprite_profile.gd
## Confirms the new loader builds all action animations for every available skin.
const SHEET = preload("res://actors/sprite_sheet_profile.gd")
const ACTIONS = ["idle", "run", "attack", "hurt", "death", "dodge", "sprint"]

func _initialize() -> void:
    var skins := ["knight", "merchant", "healer", "wanderer", "wolf", "wisp"]
    var failures: int = 0
    for skin in skins:
        var result: Dictionary = SHEET.build(skin)
        if result.is_empty():
            push_error("Cannot load skin: " + skin)
            failures += 1
            continue
        var sprite_frames: SpriteFrames = result["frames"]
        var frame_size: Vector2i = result["frame_size"]
        for action in ACTIONS:
            if not sprite_frames.has_animation(action) or sprite_frames.get_frame_count(action) < 1:
                push_error("Missing animation: %s/%s" % [skin, action])
                failures += 1
                continue
            var atlas: AtlasTexture = sprite_frames.get_frame_texture(action, 0) as AtlasTexture
            if atlas == null or atlas.region.size != Vector2(frame_size):
                push_error("Bad atlas crop: %s/%s" % [skin, action])
                failures += 1
        print("Skin:", skin, " single frame:", frame_size)
    if failures > 0:
        push_error("Sprite test failed: %d issue(s)" % failures)
        quit(1)
    else:
        print("All default sprite skins passed")
        quit(0)
