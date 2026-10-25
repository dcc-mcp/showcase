extends RefCounted
## Candidate resource-only facade. No movement, rules, input, audio or persistence.
## Original Kenney CC0 PNG bytes; direction IDs retain the pack's own numbering.

const HERO_FRAMES: SpriteFrames = preload("res://fifty/view/hero_frames.tres")
const HERO_CANVAS_SIZE := Vector2i(256, 512)
# Common logical pivot: original Male_0_Idle0 last nontransparent row = 456.
# Alpha feet bounds vary during stride/crouch. Frames have not been recropped.
const HERO_FOOT_ANCHOR := Vector2i(128, 456)
const OPEN_DOOR_TEXTURE_PATHS := {
    "N": "res://assets/experience/doors/stoneWallDoorOpen_N.png",
    "E": "res://assets/experience/doors/stoneWallDoorOpen_E.png",
    "S": "res://assets/experience/doors/stoneWallDoorOpen_S.png",
    "W": "res://assets/experience/doors/stoneWallDoorOpen_W.png"
}
# Source pack legend is not a claim about the current grid/D4 world orientation.
# Screen headings were checked from original Idle PNGs; precise angles unmeasured.
const DIRECTION_INFO := {
    0: {"source_id": 0, "source_heading": "N", "screen_heading": "upper_right", "view": "back_right"},
    1: {"source_id": 1, "source_heading": "NE", "screen_heading": "right", "view": "right_side"},
    2: {"source_id": 2, "source_heading": "E", "screen_heading": "lower_right", "view": "front_right"},
    3: {"source_id": 3, "source_heading": "SE", "screen_heading": "down", "view": "front"},
    4: {"source_id": 4, "source_heading": "S", "screen_heading": "lower_left", "view": "front_left"},
    5: {"source_id": 5, "source_heading": "SW", "screen_heading": "left", "view": "left_side"},
    6: {"source_id": 6, "source_heading": "W", "screen_heading": "upper_left", "view": "back_left"},
    7: {"source_id": 7, "source_heading": "NW", "screen_heading": "up", "view": "back"}
}


static func get_hero_frames() -> SpriteFrames:
    return HERO_FRAMES


static func get_open_door_texture_path(direction: String = "N") -> String:
    return str(OPEN_DOOR_TEXTURE_PATHS.get(direction.strip_edges().to_upper(), ""))


static func get_open_door_texture(direction: String = "N") -> Texture2D:
    var path: String = get_open_door_texture_path(direction)
    if path.is_empty():
        return null
    return ResourceLoader.load(path) as Texture2D


static func get_hero_sprite_offset(centered: bool = false) -> Vector2:
    # Apply to a full 256x512 Sprite2D/AnimatedSprite2D; do not crop individual frames.
    return Vector2(0.0, -200.0) if centered else Vector2(-128.0, -456.0)


static func get_direction_info(direction_id: int) -> Dictionary:
    return DIRECTION_INFO.get(direction_id, {}).duplicate(true)
