"""Validated JSON plan contract for the legacy planner mode."""
from __future__ import annotations


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _frame(value, field: str, frames: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= frames:
        raise ValueError(f"{field} must be an integer in 1..{frames}")
    return value


def parse_json_plan(value: dict, frames: int) -> dict:
    """Validate the old parts/keys/gaps idea and normalize it for the SVG pipeline."""
    if not isinstance(value, dict):
        raise ValueError("Plan must be one JSON object")
    concept = _text(value.get("concept"), "concept")
    action = _text(value.get("action"), "action")
    layout_notes = _text(value.get("layout_notes"), "layout_notes")

    parts = value.get("parts")
    if not isinstance(parts, list) or not parts:
        raise ValueError("parts must be a non-empty array")
    normalized_parts = []
    seen_parts = set()
    for index, part in enumerate(parts):
        if not isinstance(part, dict):
            raise ValueError(f"parts[{index}] must be an object")
        part_id = _text(part.get("id"), f"parts[{index}].id")
        if part_id in seen_parts:
            raise ValueError(f"Duplicate semantic part id: {part_id}")
        seen_parts.add(part_id)
        normalized_parts.append({
            "id": part_id,
            "role": _text(part.get("role"), f"parts[{index}].role"),
            "motion": _text(part.get("motion"), f"parts[{index}].motion"),
            "appearance": _text(part.get("appearance"), f"parts[{index}].appearance"),
        })

    keys = value.get("keys")
    if not isinstance(keys, list) or len(keys) < 2:
        raise ValueError("keys must contain at least the initial and final key")
    normalized_keys = []
    for index, key in enumerate(keys):
        if not isinstance(key, dict):
            raise ValueError(f"keys[{index}] must be an object")
        normalized_keys.append({
            "frame": _frame(key.get("frame"), f"keys[{index}].frame", frames),
            "name": _text(key.get("name"), f"keys[{index}].name"),
            "state": _text(key.get("state"), f"keys[{index}].state"),
        })
    key_indices = [key["frame"] for key in normalized_keys]
    if key_indices != sorted(set(key_indices)):
        raise ValueError("Key frames must be unique and strictly increasing")
    if key_indices[0] != 1 or key_indices[-1] != frames:
        raise ValueError(f"Keys must start at frame 1 and end at frame {frames}")

    intervals = value.get("gaps")
    if not isinstance(intervals, list) or len(intervals) != len(normalized_keys) - 1:
        raise ValueError("gaps must contain exactly one interval between every adjacent key")
    normalized_gaps = []
    for index, (item, left, right) in enumerate(zip(intervals, normalized_keys, normalized_keys[1:])):
        if not isinstance(item, dict):
            raise ValueError(f"gaps[{index}] must be an object")
        start = _frame(item.get("from"), f"gaps[{index}].from", frames)
        end = _frame(item.get("to"), f"gaps[{index}].to", frames)
        if (start, end) != (left["frame"], right["frame"]):
            raise ValueError(f"gaps[{index}] must connect adjacent keys {left['frame']}->{right['frame']}")
        normalized_gaps.append({
            "from": start,
            "to": end,
            "indices": list(range(start + 1, end)),
            "beat": {
                "start": start,
                "end": end,
                "event": _text(item.get("event"), f"gaps[{index}].event"),
                "exit": _text(item.get("exit"), f"gaps[{index}].exit"),
            },
        })

    canonical = {
        "concept": concept,
        "action": action,
        "layout_notes": layout_notes,
        "parts": normalized_parts,
        "keys": normalized_keys,
        "gaps": [{
            "from": gap["from"],
            "to": gap["to"],
            "event": gap["beat"]["event"],
            "exit": gap["beat"]["exit"],
        } for gap in normalized_gaps],
    }
    return {
        "action": action,
        "notes": layout_notes,
        "parts": normalized_parts,
        "beats": [gap["beat"] for gap in normalized_gaps],
        "key_indices": key_indices,
        "intervals": normalized_gaps,
        "json_plan": canonical,
    }
