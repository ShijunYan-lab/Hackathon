extends RefCounted
## Shared SpriteFrames builder for player, NPC and humanoid enemies.
## Visual pixels are NOT world tiles: a 48x64 character still walks on a 32x32 grid.
## The default sheet is four columns, with one animation per row.
## D may remap rows/frame counts per skin in sprite_sheet_layouts.json.

const LAYOUT_FILE: String = "res://actors/assets/sprite_sheet_layouts.json"
const SPRITE_DIR: String = "res://actors/assets/sprites/"
const PRIMARY_FRAME_SIZE: Vector2i = Vector2i(48, 64)
const LEGACY_FRAME_SIZE: Vector2i = Vector2i(32, 32)
const ACTION_NAMES = ["idle", "run", "attack", "hurt", "death", "dodge", "sprint"]
const DEFAULT_ANIMATIONS = {
    "idle": {"row": 0, "frames": 2, "fps": 3.0, "loop": true},
    "run": {"row": 1, "frames": 4, "fps": 10.0, "loop": true},
    "attack": {"row": 2, "frames": 4, "fps": 13.0, "loop": false},
    "hurt": {"row": 3, "frames": 2, "fps": 9.0, "loop": false},
    "death": {"row": 4, "frames": 4, "fps": 6.0, "loop": false},
    "dodge": {"row": 5, "frames": 4, "fps": 15.0, "loop": false},
    "sprint": {"row": 6, "frames": 4, "fps": 14.0, "loop": true}
}

static func build(skin: String) -> Dictionary:
    var manifest: Dictionary = _read_manifest()
    var skins: Dictionary = manifest.get("skins", {})
    var options: Dictionary = {}
    if skins.get(skin) is Dictionary:
        options = skins[skin]

    var path: String = str(options.get("path", skin if skin.begins_with("res://") else SPRITE_DIR + skin + ".png"))
    var texture: Texture2D = load(path) as Texture2D
    if texture == null:
        push_warning("Actor sprite missing: " + path + "; trying merchant fallback")
        path = SPRITE_DIR + "merchant.png"
        texture = load(path) as Texture2D
    if texture == null:
        push_error("Actor sprite fallback also missing: " + path)
        return {}

    var frame_size: Vector2i = _resolve_frame_size(texture, options)
    if frame_size.x <= 0 or frame_size.y <= 0:
        push_error("Invalid sprite frame size for " + path)
        return {}
    var texture_width: int = texture.get_width()
    var texture_height: int = texture.get_height()
    if texture_width % frame_size.x != 0 or texture_height % frame_size.y != 0:
        push_error("Sprite sheet dimensions must be exact multiples of frame size: " + path)
        return {}

    var available_columns: int = texture_width / frame_size.x
    var available_rows: int = texture_height / frame_size.y
    if available_columns < 1 or available_rows < 1:
        push_error("Empty sprite sheet: " + path)
        return {}

    var manifest_animations: Dictionary = manifest.get("animations", {})
    var skin_animations: Dictionary = options.get("animations", {})
    var frame_set := SpriteFrames.new()
    if frame_set.has_animation("default"):
        frame_set.remove_animation("default")

    for action_name in ACTION_NAMES:
        var config: Dictionary = DEFAULT_ANIMATIONS[action_name].duplicate()
        if manifest_animations.get(action_name) is Dictionary:
            config.merge(manifest_animations[action_name], true)
        if skin_animations.get(action_name) is Dictionary:
            config.merge(skin_animations[action_name], true)

        var row: int = int(config.get("row", 0))
        if row < 0 or row >= available_rows:
            # Old 5-row sprites can still play sprint/dodge without out-of-bounds atlases.
            row = 1 if action_name in ["dodge", "sprint"] and available_rows > 1 else 0
        var count: int = clampi(int(config.get("frames", 4)), 1, available_columns)
        var fps: float = maxf(float(config.get("fps", 8.0)), 0.1)
        frame_set.add_animation(action_name)
        frame_set.set_animation_speed(action_name, fps)
        frame_set.set_animation_loop(action_name, bool(config.get("loop", true)))
        for col in range(count):
            var atlas := AtlasTexture.new()
            atlas.atlas = texture
            atlas.region = Rect2(
                float(col * frame_size.x), float(row * frame_size.y),
                float(frame_size.x), float(frame_size.y)
            )
            frame_set.add_frame(action_name, atlas)

    return {"frames": frame_set, "frame_size": frame_size, "path": path}

static func _read_manifest() -> Dictionary:
    if not FileAccess.file_exists(LAYOUT_FILE):
        return {}
    var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(LAYOUT_FILE))
    if parsed is Dictionary:
        return parsed
    push_warning("Invalid sprite sheet layout JSON: " + LAYOUT_FILE)
    return {}

static func _resolve_frame_size(texture: Texture2D, options: Dictionary) -> Vector2i:
    var requested: Variant = options.get("frame_size", null)
    if requested is Array and requested.size() == 2:
        var explicit_size := Vector2i(int(requested[0]), int(requested[1]))
        if explicit_size.x > 0 and explicit_size.y > 0:
            return explicit_size
    # Prefer the new D-art format; keep existing A sprites working until replaced.
    if texture.get_width() % PRIMARY_FRAME_SIZE.x == 0 and texture.get_height() % PRIMARY_FRAME_SIZE.y == 0:
        return PRIMARY_FRAME_SIZE
    if texture.get_width() % LEGACY_FRAME_SIZE.x == 0 and texture.get_height() % LEGACY_FRAME_SIZE.y == 0:
        return LEGACY_FRAME_SIZE
    return Vector2i.ZERO
