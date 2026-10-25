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
const CLOSED_DOOR_TEXTURE_PATHS := {
    "N": "res://assets/experience/doors/stoneWallDoorClosed_N.png",
    "E": "res://assets/experience/doors/stoneWallDoorClosed_E.png",
    "S": "res://assets/experience/doors/stoneWallDoorClosed_S.png",
    "W": "res://assets/experience/doors/stoneWallDoorClosed_W.png"
}
const STAIRS_TEXTURE_PATHS := {
    "N": "res://assets/experience/stairs/stairs_N.png",
    "E": "res://assets/experience/stairs/stairs_E.png",
    "S": "res://assets/experience/stairs/stairs_S.png",
    "W": "res://assets/experience/stairs/stairs_W.png"
}
# Explicit ascent convention: N=screen NE, E=SE, S=SW, W=NW, like the character.
# The source stairs filenames describe model rotation, NOT the uphill end.
# Both reviewers inspected original treads: raw N/E/S/W ascend SW/NW/NE/SE.
const STAIRS_SOURCE_FOR_ASCENT := {"N": "S", "E": "W", "S": "N", "W": "E"}
# Static alignment candidate, calibrated to the existing N closed-door placement.
# Closed masonry bounds have a common bottom after these orientation offsets.
# Use the SAME offset for Closed/Open: an opened leaf can extend the alpha bbox.
# This is not an engine/pixel-accepted architectural pivot or a world-axis map.
const DOOR_SPRITE_OFFSETS := {
    "N": Vector2(-80.0, -448.0),
    "E": Vector2(-80.0, -400.0),
    "S": Vector2(-176.0, -400.0),
    "W": Vector2(-176.0, -448.0)
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


static func get_closed_door_texture_path(direction: String = "N") -> String:
    return str(CLOSED_DOOR_TEXTURE_PATHS.get(direction.strip_edges().to_upper(), ""))


static func get_closed_door_texture(direction: String = "N") -> Texture2D:
    var path: String = get_closed_door_texture_path(direction)
    if path.is_empty():
        return null
    return ResourceLoader.load(path) as Texture2D


static func get_door_sprite_offset(direction: String = "N", centered: bool = false) -> Vector2:
    var key: String = direction.strip_edges().to_upper()
    if not DOOR_SPRITE_OFFSETS.has(key):
        return Vector2.ZERO
    var sprite_offset: Vector2 = DOOR_SPRITE_OFFSETS[key]
    return sprite_offset + Vector2(128.0, 256.0) if centered else sprite_offset


static func get_stairs_texture_path(direction: String = "N") -> String:
    # Raw source-file direction; callers needing an uphill target use ascent APIs.
    return str(STAIRS_TEXTURE_PATHS.get(direction.strip_edges().to_upper(), ""))


static func get_stairs_texture(direction: String = "N") -> Texture2D:
    var path: String = get_stairs_texture_path(direction)
    if path.is_empty():
        return null
    return ResourceLoader.load(path) as Texture2D


static func get_stairs_source_direction_for_ascent(ascent_direction: String = "N") -> String:
    return str(STAIRS_SOURCE_FOR_ASCENT.get(ascent_direction.strip_edges().to_upper(), ""))


static func get_stairs_ascent_texture(ascent_direction: String = "N") -> Texture2D:
    return get_stairs_texture(get_stairs_source_direction_for_ascent(ascent_direction))


static func get_stairs_sprite_offset(direction: String = "N", centered: bool = false) -> Vector2:
    # All four source stairs share a full-width canvas and last opaque row 511.
    # Candidate baseline aligns the bottom with the closed-door masonry (row 63).
    # Original PNGs and their differing upper silhouettes remain unchanged.
    if not STAIRS_TEXTURE_PATHS.has(direction.strip_edges().to_upper()):
        return Vector2.ZERO
    return Vector2(0.0, -192.0) if centered else Vector2(-128.0, -448.0)


static func get_hero_sprite_offset(centered: bool = false) -> Vector2:
    # Apply to a full 256x512 Sprite2D/AnimatedSprite2D; do not crop individual frames.
    return Vector2(0.0, -200.0) if centered else Vector2(-128.0, -456.0)


static func get_direction_info(direction_id: int) -> Dictionary:
    return DIRECTION_INFO.get(direction_id, {}).duplicate(true)
