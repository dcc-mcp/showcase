"""Read-only observer validation. None of these helpers sends or injects gameplay state."""
from __future__ import annotations
import json
import math


def observer_receipts(console, prefix, start=0):
    """Parse only exact event-prefixed console lines after the caller's event boundary."""
    records = []
    marker = prefix + " "
    for line in console[start:]:
        text = line.get("text", "")
        if text.startswith(marker):
            try:
                record = json.loads(text[len(marker):])
            except (ValueError, TypeError) as error:
                raise ValueError(f"Malformed {prefix} receipt") from error
            if not isinstance(record, dict):
                raise ValueError(f"{prefix} receipt must be an object")
            records.append(record)
    return records


def positive_integer(value, field):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def finite_vector(value, length, field):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{field} must contain {length} numeric coordinates")
    if any(type(item) not in (int, float) or not math.isfinite(item) for item in value):
        raise ValueError(f"{field} must contain only finite numeric coordinates")
    return value


def validate_touch_release(receipt, previous_gesture_id=0, expected_touch_index=0):
    if type(receipt.get("schema")) is not int or receipt["schema"] != 1:
        raise ValueError("Unsupported touch receipt schema")
    gesture = positive_integer(receipt.get("gesture_id"), "gesture_id")
    if gesture <= previous_gesture_id:
        raise ValueError("Touch receipt is stale")
    index = receipt.get("touch_index")
    if type(index) is not int or index != expected_touch_index:
        raise ValueError("Touch receipt does not match the actual finger")
    before = finite_vector(receipt.get("before"), 3, "before")
    after = finite_vector(receipt.get("after"), 3, "after")
    positive_integer(receipt.get("physics_frames_elapsed"), "physics_frames_elapsed")
    positive_integer(receipt.get("drag_events"), "drag_events")
    for field in ("canceled", "demo", "active_after"):
        if receipt.get(field) is not False:
            raise ValueError(f"Touch receipt requires {field}=false")
    if finite_vector(receipt.get("move_after"), 2, "move_after") != [0, 0]:
        raise ValueError("Touch movement was not cleared on release")
    displacement = math.hypot(after[0] - before[0], after[2] - before[2])
    if displacement <= .25:
        raise ValueError("Actual horizontal touch displacement must exceed 0.25")
    return displacement


CHINESE_LABELS = {
    "title": "潮 汐 圣 所",
    "subtitle": "海图就在岸边的石台上。",
    "objective": "阅读岸边的海图",
    "footer": "方向键行走或游泳 · E 互动 · J 手记 · M 声音",
    "action": "阅读海图",
}
# Language acceptance runs at the untouched fresh spawn, outside chart reach.
CHINESE_PROMPTS = ("靠近后即可互动",)


def validate_language_frame(receipt, previous_change_id=0):
    if type(receipt.get("schema")) is not int or receipt["schema"] != 1:
        raise ValueError("Unsupported language receipt schema")
    change = positive_integer(receipt.get("change_id"), "change_id")
    if change <= previous_change_id:
        raise ValueError("Language receipt is stale")
    if (receipt.get("previous"), receipt.get("language"), receipt.get("trigger")) != ("en", "zh", "key_L"):
        raise ValueError("Expected actual physical-L en-to-zh transition")
    labels = receipt.get("labels")
    if not isinstance(labels, dict):
        raise ValueError("Language receipt must expose actual rendered labels")
    for field, expected in CHINESE_LABELS.items():
        if labels.get(field) != expected:
            raise ValueError(f"Rendered Chinese {field} label differs from the expected current scene")
    if labels.get("prompt") not in CHINESE_PROMPTS:
        raise ValueError("Rendered Chinese prompt is missing, untranslated, or unexpected")
    if receipt.get("missing_codepoints") != []:
        raise ValueError("Rendered language labels have missing or unverified font codepoints")
    return labels
